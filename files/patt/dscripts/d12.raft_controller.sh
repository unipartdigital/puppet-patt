#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; } | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} || true ; rm -f $0 ; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

raft_controller_user="raft"

selinux_policy () {
    pe_file="${1}"
    module=`awk '/^[[:space:]]*module[[:space:]]/{print $2}' ${pe_file}`
    selinux_packages="/usr/local/share/selinux/packages/"
    {
        test -x /usr/sbin/semodule && test -x /usr/bin/checkmodule && test -x /usr/bin/semodule_package
    } || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                dnf -q -y install checkpolicy policycoreutils
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install policycoreutils checkpolicy semodule-utils selinux-policy-default
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }

    test -d "${selinux_packages}" || mkdir -p -m 755 "${selinux_packages}"
    { semodule -l | grep -q "^${module}$" && \
          test "`md5sum ${pe_file} | cut -d' ' -f1`" == \
               "`md5sum ${selinux_packages}/${module}.te  2> /dev/null | cut -d' ' -f1`"
    } || {
        # Build a MLS/MCS-enabled non-base policy module.
        checkmodule -M -m ${srcdir}/${module}.te -o ${srcdir}/${module}.mod
        semodule_package -o ${srcdir}/${module}.pp -m ${srcdir}/${module}.mod
        semodule -X 300 -i ${srcdir}/${module}.pp && {
            cp -f ${srcdir}/${module}.pp ${selinux_packages}/${module}.pp
            cp -f ${srcdir}/${module}.te ${selinux_packages}/${module}.te
        }
        rm -f ${srcdir}/${module}.te ${srcdir}/${module}.mod ${srcdir}/${module}.pp
    }
}

init () {
    patroni_version=${1:-"2.0.2"}
    data_dir=${2:-"/var/lib/raft"}
    raft_user=${3:-"${raft_controller_user}"}
    raft_home=$(getent passwd ${raft_controller_user} | cut -d':' -f 6)
    dcs="raft"
    test "$(getent passwd  ${raft_user} | cut -d: -f1)" == "${raft_user}" || {
        useradd --home-dir "${data_dir}" --user-group  \
                --comment "Patroni Raft Controller" \
                --system --no-log-init \
                --shell /bin/false ${raft_user}
    }
    test -d ${data_dir} || mkdir -p -m 711 ${data_dir}
    test `stat -c "%a" ${data_dir}` == "711" || {
        chmod 711 ${data_dir}
    }
    test `stat -c "%U.%G" ${data_dir}` == "${raft_user}.${raft_user}" || {
        chown ${raft_user}.${raft_user} ${data_dir}
    }
    for i in ".cache" ".local"; do
        test -d ${raft_home}/${i} || {
            mkdir -p -m 700 ${raft_home}/${i}
            chown ${raft_user}.${raft_user} ${raft_home}/${i}
        }
        test `stat -c "%U.%G" ${raft_home}/${i}` == "${raft_user}.${raft_user}" || {
            chown  ${raft_user}.${raft_user} ${raft_home}/${i}
        }
        test `stat -c "%a" ${raft_home}/${i}` == "700" || {
            chmod 700 ${raft_home}/${i}
        }
    done
    touch /tmp/patroni_pip.stamp
    cat <<EOF | su ${raft_user} -s /bin/bash
PATH=$PATH:~/.local/bin
#python3 -m pip -q install --user -U requests
python3 -m pip -q install --user patroni[${dcs}]==${patroni_version}
EOF

    test -d ${data_dir} || mkdir -p -m 711 ${data_dir}
    test `stat -c "%U.%G" ${data_dir}` == "${raft_user}.${raft_user}" || {
        chown ${raft_user}.${raft_user} ${data_dir}
    }
}

configure () {
    systemd_raft_controller=${1:-"patroni_raft_controller.service.tmpl"}
    raft_user=${2:-"${raft_controller_user}"}
    pe_file=${3:-"patroni_raft.te"}

    raft_home=$(getent passwd ${raft_user} | cut -d ':' -f 6)
    raft_controller_config_file="${raft_home}/raft.yaml"

    python3 ${srcdir}/tmpl2file.py -t ${srcdir}/${systemd_raft_controller}                    \
            -o /etc/systemd/system/patroni_raft_controller.service                            \
            --dictionary_key_val "raft_user=${raft_user}"                                     \
            --dictionary_key_val "raft_group=${raft_user}"                                    \
            --dictionary_key_val "raft_bin=${raft_home}/.local/bin"                           \
            --dictionary_key_val "raft_controller_config_file=${raft_controller_config_file}" \
            --chmod 644                                                                       \
            --touch /var/tmp/$(basename $0 .sh).systemd-reload
    test -f /var/tmp/$(basename $0 .sh).systemd-reload && {
        systemctl daemon-reload
        rm -f /var/tmp/$(basename $0 .sh).systemd-reload
    }

    selinux_policy "${srcdir}/${pe_file}"
}

enable () {
    systemd_service=${1:-"patroni_raft_controller.service"}
    raft_user=${2:-"${raft_controller_user}"}
    raft_home=$(getent passwd ${raft_user} | cut -d ':' -f 6)
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            if ! systemctl is-active --quiet ${systemd_service} ; then
                systemctl start ${systemd_service} && systemctl enable ${systemd_service}
            elif [ "x" != "x$(find -L ${raft_home}/.local/bin/patroni_raft_controller -newer /tmp/patroni_pip.stamp)" ]; then
                systemctl restart ${systemd_service}
            elif [ -f "/tmp/patroni_raft_controller.reload" ]; then
                systemctl reload ${systemd_service}
                rm -f /tmp/patroni_raft_controller.reload
            fi
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    rm -f /tmp/patroni_pip.stamp
}

pg_node_configure () {
    data_dir=${1:-"/var/lib/raft"}
    pe_file=${2:-"patroni_raft.te"}
    postgres_user="postgres"
    pg_user=`id -n -u ${postgres_user}`
    pg_group=`id -n -g ${postgres_user}`

    test -d ${data_dir} || mkdir -p -m 711 ${data_dir}
    test `stat -c "%a" ${data_dir}` == "711" || {
        chmod 711 ${data_dir}
    }
    test `stat -c "%U.%G" ${data_dir}` == "${pg_user}.${pg_group}" || {
        chown ${pg_user}.${pg_group} ${data_dir}
    }

    selinux_policy "${srcdir}/${pe_file}"
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # must be run at least on each raft only peer
    'init')
        shift 1
        { flock -w 10 8 || exit 1
          init "$@"
        } 8< ${lock_file}
        ;;
    'configure')
        shift 1
        { flock -w 10 8 || exit 1
          configure "$@"
        } 8< ${lock_file}
        ;;
    'enable')
        shift 1
        { flock -w 10 8 || exit 1
          enable "$@"
        } 8< ${lock_file}
        ;;
    # must be run at least on each postgres peer
    'pg_node_configure')
        shift 1
        { flock -w 10 8 || exit 1
          pg_node_configure "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 init
EOF
            exit 1
        } >&2
        ;;
esac

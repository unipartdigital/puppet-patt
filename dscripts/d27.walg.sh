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

init () {
    walg_release=${1:-"v0.2.19"}
    prefix=/usr/local

    downloader=""
    wget --version > /dev/null 2>&1 && {
        downloader="wget -q -L"
    } || {
        curl --version > /dev/null 2>&1 && {
            downloader="curl -f -s -O -L"
        }
    }

    download_url="https://github.com/wal-g/wal-g/releases/download/${walg_release}/wal-g.linux-amd64.tar.gz"
    { test -x ${prefix}/bin/wal-g && test "`${prefix}/bin/wal-g --version | awk '{print $3}'`" == "${walg_release}" > /dev/null 2>&1 ;} || {
        tmp=$(mktemp -d)
        test -d ${tmp} &&  {
            (cd $tmp && ${downloader} ${download_url} && tar xvf `basename ${download_url}`
             chmod 755 wal-g
             test "`./wal-g --version | awk '{print $3}'`" == "${walg_release}" && {
                 sudo install -o root -g root -m 755 wal-g ${prefix}/bin/wal-g
             }
            ) > /dev/null
            rm -f ${tmp}/wal-g ${tmp}/`basename ${download_url}`
            rmdir ${tmp}
        }
    }
    for i in 1 2 3 4 5; do
        { ${prefix}/bin/wal-g --version && break ; } || sleep 1
    done
}

ssh_archiving_init () {
    /sbin/semanage -h > /dev/null 2>&1 || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                if dnf --version > /dev/null 2>&1; then
                    dnf install -y policycoreutils-python-utils
                elif yum --version > /dev/null 2>&1; then
                    yum install -y policycoreutils-python-utils
                fi
                ;;
            'debian' | 'ubuntu')
                apt-get install -y policycoreutils-python-utils
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }
}

ssh_archive_keygen() {
    cluster_name="${1}"
    user_name="${2:-postgres}"
    group="$(id -ng ${user_name})"
    home="$(getent passwd  ${user_name} | cut -d: -f6)"
    test -d ${home}/.ssh/ || mkdir -m 700 ${home}/.ssh/
    test `stat -c "%U.%G" ${home}/.ssh/` == "${user_name}.${group}" || \
        chown "${user_name}.${group}" ${home}/.ssh/
    test -f ${home}/.ssh/walg_rsa.pub || {
        cat <<EOF | su - ${user_name}
/usr/bin/ssh-keygen -q -t rsa -b 4096 -f ~/.ssh/walg_rsa -N "" -C "walg_${cluster_name}_`hostname -f`"
EOF
    }
    test -f ${home}/.ssh/walg_rsa.pub && cat ${home}/.ssh/walg_rsa.pub
    test -s  ${home}/.ssh/config || {
        cat <<EOF > ${home}/.ssh/config
Host *
IdentityFile  ~/.ssh/walg_rsa
IdentityFile  ~/.ssh/id_rsa
EOF
        chown "${user_name}.${group}" "${home}/.ssh/config"
    }
}

ssh_archive_user_add () {
    user_name=${1}
    archive_base_dir=${2}
    initial_login_group=${3:-"walg"}
    test -d "${archive_base_dir}" || mkdir -p -m 711 "${archive_base_dir}"
    test -d "${archive_base_dir}/${user_name}" || {
        mkdir -p -m 711 "${archive_base_dir}/${user_name}"
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
                cat <<EOF | sudo su -
/sbin/semanage fcontext -a -t user_home_dir_t "${archive_base_dir}/${user_name}"
/sbin/restorecon -R "${archive_base_dir}/${user_name}"
EOF
                ;;
        esac
    }
    test "$(getent group ${initial_login_group} | cut -d':' -f1)" == "${initial_login_group}" || {
        groupadd --system "${initial_login_group}"
    }
    test "$(getent passwd  ${user_name} | cut -d: -f1)" == "${user_name}" || {
        useradd --home-dir "${archive_base_dir}/${user_name}" --gid "${initial_login_group}" \
                --comment "sftp chroot user" \
                --system \
                --no-log-init --no-create-home --no-user-group \
                --shell /bin/false ${user_name}
        chown "${user_name}"."${initial_login_group}" "${archive_base_dir}/${user_name}"
    }
}

sshd_conf_tmpl () {
    chroot_dir="$1"
    group=${2:-"walg"}
    cat <<EOF | sed -e "/\(^[[:space:]]*#.*\|^$\)/d"
Match Group "${group}"
      ForceCommand internal-sftp
      ChrootDirectory "${chroot_dir}"
EOF
}

sshd_configure () {
    chroot_dir="$1"
    group=${2:-"walg"}
    sshd_config_old="/etc/ssh/sshd_config"
    sshd_config_new="/etc/ssh/sshd_config.$$"
    tmpl=`sshd_conf_tmpl "${chroot_dir}" "${group}"`
    l1=$(echo "$tmpl" | head -n 1 | sed -e "s|^[[:space:]]*||")
    l2=$(echo "$tmpl" | tail -n 1 | sed -e "s|^[[:space:]]*||")

    test -n "$(sed -n -e "\@^[[:space:]]*${l1}@,\@^[[:space:]]*${l2}@p" ${sshd_config_old})" || {
        cp --preserve=all ${sshd_config_old} ${sshd_config_new}
        echo "$tmpl" >> ${sshd_config_new}
        sshd -t -f ${sshd_config_new} && {
            mv ${sshd_config_new} ${sshd_config_old}
            pidfile=$(sshd -T -C user=root | sed -n -e "/pidfile/p" | cut -d' ' -f2)
            kill -HUP $(cat $pidfile)
        }
    }
}

sftpd_configure () {
    command=${1}
    sftpd_port=${2:-22}
    sftpd_service="sftpd.service"
    cache_dir="/var/cache/sftpd"
    case "${command}" in
        'enable')
            test -d ${cache_dir} || mkdir ${cache_dir}
            test -f ${cache_dir}/port || echo "2222" > ${cache_dir}/port
            #
            test "$(nft list set ip6 postgres_patroni sftp_archiving_port | awk '/elements/ {print $4}')" \
                 == "${sftpd_port}" || {
                nft flush set ip6 postgres_patroni sftp_archiving_port
                nft add element ip6 postgres_patroni sftp_archiving_port { "${sftpd_port}" }
            }
            test -f ${cache_dir}/port && {
                prev_port="$(cat ${cache_dir}/port)"
                if test "${sftpd_port}" == "${prev_port}" ; then
                    :
                else
                    test "$(semanage port -lC | awk '/ssh_port_t/{print $NF}')" == "${prev_port}" && {
                        semanage port -d -t ssh_port_t -p tcp ${prev_port}
                    }
                    semanage port -a -t ssh_port_t -p tcp ${sftpd_port}
                    echo "${sftpd_port}" > ${cache_dir}/port
                    systemctl restart ${sftpd_service}
                fi
            }
            systemctl -q is-enabled ${sftpd_service} || systemctl enable --now ${sftpd_service}
            ;;
        'disable')
            systemctl disable --now ${sftpd_service}
            nft flush set ip6 postgres_patroni sftp_archiving_port
            test -f ${cache_dir}/port && {
                prev_port="$(cat ${cache_dir}/port)"
                test "$(semanage port -lC | awk '/ssh_port_t/{print $NF}')" == "${prev_port}" && {
                    semanage port -d -t ssh_port_t -p tcp ${prev_port}
                }
                rm -f ${cache_dir}/port
                rmdir ${cache_dir} || true
            }
            ;;
    esac
}

ssh_archiving_add () {
    cluster_name=${1}
    sftpd_port=${2}
    archive_base_dir=/var/lib/walg
    group="walg"
    if [ "${sftpd_port}" == 22 ]; then
        sshd_configure "${archive_base_dir}" "${group}"
        sftpd_configure "disable"
    else
        sftpd_configure "enable" "${sftpd_port}"
    fi
    ssh_archive_user_add "${cluster_name}" "${archive_base_dir}" "walg"
    cat <<EOF | sudo su
stat -c "%A %U.%G %n" "${archive_base_dir}/${cluster_name}"
EOF
}

ssh_authorize_keys () {
    cluster_name="${1}"
    keys_file="${2}"
    group="walg"
    archive_base_dir=/var/lib/walg
    test -d ${archive_base_dir}/${cluster_name}/.ssh/ || {
        mkdir -p -m 700 ${archive_base_dir}/${cluster_name}/.ssh/
        chown ${cluster_name}.${group} ${archive_base_dir}/${cluster_name}/.ssh/
    }
    test -s "${srcdir}/${keys_file}" || { echo "error: ${srcdir}/${keys_file}" ; exit 1 ; }
    if [ -f "${archive_base_dir}/${cluster_name}/.ssh/authorized_keys" ]; then
        test "`sort -u ${srcdir}/${keys_file} | md5sum  | cut -d' ' -f1`" == "`sort -u ${archive_base_dir}/${cluster_name}/.ssh/authorized_keys | md5sum | cut -d' ' -f1`" || {
            cat "${srcdir}/${key_files}" > ${archive_base_dir}/${cluster_name}/.ssh/authorized_keys
        }
    else
        cat "${srcdir}/${keys_file}" > "${archive_base_dir}/${cluster_name}/.ssh/authorized_keys"
    fi
    chown "${cluster_name}" "${archive_base_dir}/${cluster_name}/.ssh/authorized_keys"
    chmod 600 "${archive_base_dir}/${cluster_name}/.ssh/authorized_keys"
}

ssh_known_hosts () {
    cluster_name="${1}"
    archive_host="${2}"
    archive_port="${3:-22}"
    user_name="${4:-postgres}"
    group="$(id -ng ${user_name})"
    home="$(getent passwd  ${user_name} | cut -d: -f6)"
    known_hosts="${home}/.ssh/known_hosts"
    if test -s ${known_hosts} ; then
        ssh-keyscan -t rsa -p ${archive_port} "${archive_host}" > "${known_hosts}.tmp"
        if [ "${archive_port}" -eq 22 ]; then
            match="^${archive_host}[[:space:]]"
        else
            match="^\[${archive_host}\]:${archive_port}[[:space:]]"
        fi
        new_md5=`grep "${match}" ${known_hosts}.tmp | sort -u | md5sum | cut -d' ' -f1`
        old_md5=`grep "${match}" ${known_hosts} | sort -u | md5sum | cut -d' ' -f1`
        if test "${new_md5}" == "${old_md5}" ; then
            :
            # no change
        elif test "${old_md5}" == "d41d8cd98f00b204e9800998ecf8427e" ; then
            cat ${known_hosts}.tmp > "${known_hosts}"
            # new archiving server
        else
            echo "error: known_hosts keys ${archive_host}" >&2
            exit 1
        fi
        rm -f ${known_hosts}.tmp
    else
        ssh-keyscan -t rsa -p ${archive_port} "${archive_host}" > "${known_hosts}"
        chown "${user_name}"."${group}" "${known_hosts}"
    fi
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # must be run on each postgres peer
    'init')
        shift 1
        { flock -w 10 8 || exit 1
          init "$@"
        } 8< ${lock_file}
        ;;
    # must be run on the archive server
    'ssh_archiving_init')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_archiving_init "$@"
        } 8< ${lock_file}
        ;;
    'ssh_archiving_add')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_archiving_add "$@"
        } 8< ${lock_file}
        ;;
    'ssh_authorize_keys')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_authorize_keys "$@"
        } 8< ${lock_file}
        ;;
    # must be run on each postgres peer
    'ssh_archive_keygen')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_archive_keygen "$@"
        } 8< ${lock_file}
        ;;
    'ssh_known_hosts')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_known_hosts "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 init <wal-g release version> ['v0.2.19']
 $0 ssh_archiving_init
 $0 ssh_archiving_add <cluster name>
 $0 ssh_archive_keygen
 $0 ssh_known_hosts <cluster name> <archive host IP>
EOF
            exit 1
        } >&2
        ;;
esac

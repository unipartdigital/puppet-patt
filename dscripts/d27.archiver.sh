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

ssh_archiving_init () {
    /sbin/semanage -h > /dev/null 2>&1 || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                dnf -q -y install policycoreutils-python-utils
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install policycoreutils-python-utils
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
    tag=${2}
    user_name="${3:-postgres}"
    group="$(id -ng ${user_name})"
    home="$(getent passwd  ${user_name} | cut -d: -f6)"
    test -d ${home}/.ssh/ || mkdir -m 700 ${home}/.ssh/
    test `stat -c "%U.%G" ${home}/.ssh/` == "${user_name}.${group}" || \
        chown "${user_name}.${group}" ${home}/.ssh/
    test -f ${home}/.ssh/${tag}_rsa.pub || {
        cat <<EOF | su ${user_name}
/usr/bin/ssh-keygen -q -t rsa -b 4096 -f ~/.ssh/${tag}_rsa -N "" -C "${tag}_${cluster_name}_`hostname -f`"
EOF
    }
    test -f ${home}/.ssh/${tag}_rsa.pub && cat ${home}/.ssh/${tag}_rsa.pub
    grep -q "${tag}_rsa"  ${home}/.ssh/config > /dev/null 2>&1 || {
        cat <<EOF > ${home}/.ssh/config
Host *
IdentityFile  ~/.ssh/${tag}_rsa
IdentityFile  ~/.ssh/id_rsa
EOF
        chown "${user_name}.${group}" "${home}/.ssh/config"
    }
}

ssh_archive_user_add () {
    user_name=${1}
    archive_base_dir=${2}
    initial_login_group=${3:-"archiver"}
    user_shell=${4:-"/bin/false"}
    test -d "${archive_base_dir}" || mkdir -p -m 711 "${archive_base_dir}"
    test -d "${archive_base_dir}/${user_name}" || {
        mkdir -p -m 711 "${archive_base_dir}/${user_name}"
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
                /sbin/semanage fcontext -a -t user_home_dir_t "${archive_base_dir}/${user_name}"
                /sbin/restorecon -R "${archive_base_dir}/${user_name}"
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
                --shell ${user_shell} ${user_name}
        chown "${user_name}"."${initial_login_group}" "${archive_base_dir}/${user_name}"
    }
    stat -c "%A %U.%G %n" "${archive_base_dir}/${user_name}"
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

sftpd_command () {
    command=${1}
    sftpd_port=${2:-2222}
    sftpd_service="sftpd.service"
    cache_dir="/var/cache/sftpd"
    case "${command}" in
        'enable')
            test -d ${cache_dir} || mkdir ${cache_dir}
            test -f ${cache_dir}/port || echo "${sftpd_port}" > ${cache_dir}/port
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
            systemctl -q is-active ${sftpd_service} || systemctl restart ${sftpd_service}
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


ssh_authorize_keys () {
    user_name="${1}"
    keys_file="${2}"
    group=${3:-"`id -n -g ${user_name}`"}
    home_dir=$(getent passwd ${user_name} | cut -d: -f6)
    test -d ${home_dir}/.ssh/ || {
        mkdir -p -m 700 ${home_dir}/.ssh/
        chown ${user_name}.${group} ${home_dir}/.ssh/
    }
    test -s "${srcdir}/${keys_file}" || { echo "error: ${srcdir}/${keys_file}" ; exit 1 ; }
    if [ -f "${home_dir}/.ssh/authorized_keys" ]; then
        test "`sort -u ${srcdir}/${keys_file} | md5sum  | cut -d' ' -f1`" == "`sort -u ${home_dir}/.ssh/authorized_keys | md5sum | cut -d' ' -f1`" || {
            cat "${srcdir}/${keys_file}" > ${home_dir}/.ssh/authorized_keys
        }
    else
        cat "${srcdir}/${keys_file}" > "${home_dir}/.ssh/authorized_keys"
    fi

    test `-c "%U" "${home_dir}/.ssh/authorized_keys"` == "${user_name}" || \
        chown "${user_name}" "${home_dir}/.ssh/authorized_keys"
    test `stat -c "%a" "${home_dir}/.ssh/authorized_keys"` == "600" || \
        chmod 600 "${home_dir}/.ssh/authorized_keys"
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
            cat ${known_hosts}.tmp >> "${known_hosts}"
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

aws_credentials () {
    comd=${1:-"tmpl2file.py"}
    awc=${2:-""}
    pg_home=$(getent passwd postgres | cut -d':' -f 6)
    test "x${pg_home}" != "x" || { echo "pg_home not found"     >&2 ; rm -f "${srcdir}/${awc}" ; exit 1 ; }
    test -d ${pg_home} || { echo "${pg_home} not directory"     >&2 ; rm -f "${srcdir}/${awc}" ; exit 1 ; }
    test -f ${srcdir}/${comd} || { echo "script file not found" >&2 ; rm -f "${srcdir}/${awc}" ; exit 1 ; }
    test -f ${srcdir}/${awc} || { echo "credential file not found" >&2 ; exit 1 ; }

    test -d ${pg_home}/.aws || {
        mkdir -m 700 ${pg_home}/.aws && chown postgres.postgres ${pg_home}/.aws
    }

    python3 ${srcdir}/${comd} -t ${srcdir}/${awc} -o ${pg_home}/.aws/credentials \
            --skip '#'                                                           \
            --chmod 640
    test "`stat -c '%U' ${pg_home}/.aws/credentials`" == "postgres" || {
        chown "postgres" ${pg_home}/.aws/credentials
    }
    rm -f "${srcdir}/${awc}"
}

aws_credentials_dump () {
    comd=${1:-"tmpl2file.py"}
    pg_home=$(getent passwd postgres | cut -d':' -f 6)
    test -f ${pg_home}/.aws/credentials && {
        python3 ${srcdir}/${comd} -t ${pg_home}/.aws/credentials
    }
}

s3_create_bucket () {
    comd=$1
    endpoint_url=$2
    bucket=$3
    aws_profile=$4
    aws_region=$5
    aws_force_path=$6
    user_name=$7

    chown "${user_name}" "${srcdir}"
    chown "${user_name}" "${srcdir}/${comd}"

    cat <<EOF | su ${user_name} > /dev/null
python3 -c "import boto3" 2> /dev/null || python3 -m pip -q install --user boto3
EOF

    cat <<EOF | su ${user_name} | tail -n 1
python3 ${srcdir}/${comd} --endpoint_url ${endpoint_url} \
 --bucket ${bucket} \
 --aws_profile ${aws_profile} \
 --aws_region ${aws_region} \
 --aws_force_path ${aws_force_path}
EOF

}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # must be run on the archive server
    'ssh_archiving_init')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_archiving_init "$@"
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
    'aws_credentials')
        shift 1
        { flock -w 10 8 || exit 1
          aws_credentials "$@"
        } 8< ${lock_file}
        ;;
    'aws_credentials_dump')
        shift 1
        { flock -w 10 8 || exit 1
          aws_credentials_dump "$@"
        } 8< ${lock_file}
        ;;
    's3_create_bucket')
        shift 1
        { flock -w 10 8 || exit 1
          s3_create_bucket "$@"
        } 8< ${lock_file}
        ;;
    'ssh_archive_user_add')
        shift 1
        { flock -w 10 8 || exit 1
          ssh_archive_user_add "$@"
        } 8< ${lock_file}
        ;;
    'sshd_configure')
        shift 1
        { flock -w 10 8 || exit 1
          sshd_configure "$@"
        } 8< ${lock_file}
        ;;
    'sftpd_command')
        shift 1
        { flock -w 10 8 || exit 1
          sftpd_command "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 ssh_archiving_init
 $0 ssh_archive_keygen
 $0 ssh_known_hosts <cluster name> <archive host IP>
 $0 aws_credentials
 $0 aws_credentials_dump
 $0 s3_create_bucket
 $0 ssh_archive_user_add user_name archive_base_dir initial_login_group (archiver) user_shell (/bin/false)
 $0 sshd_configure chroot_dir group
 $0 sftpd_command enable port | disable
EOF
            exit 1
        } >&2
        ;;
esac

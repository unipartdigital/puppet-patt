#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

init() {
    postgresql_version=${1:-"13"}

    case "${os_id}" in
        'redhat' | 'centos')
            rel_repo="https://download.postgresql.org/pub/repos/yum/reporpms/EL-${os_major_version_id}-${os_arch}/pgdg-redhat-repo-latest.noarch.rpm"
            rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"

            if [ "${os_major_version_id}" -lt 8 ]; then
                yum install -y ${rel_repo} ${rel_epel}
                yum install -y \
                    postgresql${postgresql_version} \
                    postgresql${postgresql_version}-server \
                    postgresql${postgresql_version}-contrib
                #postgresql${postgresql_version}-devel
            else
                dnf install -y ${rel_repo} epel-release
                dnf -qy module disable postgresql
                # disable default shipped version
                dnf install -y \
                    postgresql${postgresql_version} \
                    postgresql${postgresql_version}-server \
                    postgresql${postgresql_version}-contrib
                #postgresql${postgresql_version}-devel
            fi

            pg_home=$(getent passwd postgres | cut -d':' -f 6)
            if [ -n "${pg_home}" ]; then
                chown postgres.postgres ${pg_home}
                chmod 711 ${pg_home}
            fi
            # ensure sane permission

            sed -i -e "/#[[:space:]]*TYPE[[:space:]]\+DATABASE[[:space:]]\+USER[[:space:]]\+ADDRESS[[:space:]]\+METHOD.*/q" /usr/pgsql-${postgresql_version}/share/pg_hba.conf.sample
            cat <<EOF >> /usr/pgsql-${postgresql_version}/share/pg_hba.conf.sample
 local  all             all                                     ident
EOF
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

{
    flock -n 9 || exit 1

    case "${1:-""}" in
        'init')
            shift 1
            init "$@"
            ;;
        *)
            echo "usage: $0 init <postgres version: 9.6 | 10 | 11* | 12 ...>"
            exit 1
            ;;
    esac
} 9> ${lock_file}

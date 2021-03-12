#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0 ; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

case "${os_id}" in
    'debian' | 'ubuntu')
        export DEBIAN_FRONTEND=noninteractive
        ;;
esac

init() {
    postgresql_version=${1:-"13"}

    case "${os_id}" in

        'rhel' | 'centos' | 'fedora')
            /usr/pgsql-${postgresql_version}/bin/postgres --version > /dev/null 2>&1 || {
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
                    # dnf update -y
                    dnf -qy module disable postgresql
                    # disable default shipped version
                    dnf install -y \
                        postgresql${postgresql_version} \
                        postgresql${postgresql_version}-server \
                        postgresql${postgresql_version}-contrib
                    #postgresql${postgresql_version}-devel
                fi
            }
            pg_hba_conf_sample="/usr/pgsql-${postgresql_version}/share/pg_hba.conf.sample"
            ;;

        'debian' | 'ubuntu')
            /usr/lib/postgresql/${postgresql_version}/bin/postgres --version > /dev/null 2>&1 || {
                apt-get install -qq -y gnupg wget
                if ! /usr/bin/test -s /etc/apt/sources.list.d/pgdg.list; then
                    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
                fi
                if ! apt-key list 2>&1 | grep -q "PostgreSQL.*Repository" ; then
                    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
                        sudo apt-key add -
                fi
                apt-get update -q
                test -d /etc/postgresql-common/ || mkdir -p   /etc/postgresql-common/
                test -f /etc/postgresql-common/createcluster.conf || \
                    cat <<EOF > /etc/postgresql-common/createcluster.conf
create_main_cluster = false
start_conf = 'disabled'
data_directory = /dev/null
ssl = off
EOF
                test -x /usr/lib/postgresql/${postgresql_version}/bin/postgres || \
                    apt-get install -qq -y postgresql-${postgresql_version}
                #postgresql-server-dev-${postgresql_version}
            }
            pg_hba_conf_sample="/usr/share/postgresql/${postgresql_version}/pg_hba.conf.sample"
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

    test -f ${pg_hba_conf_sample} && {
        sed -i -e "/#[[:space:]]*TYPE[[:space:]]\+DATABASE[[:space:]]\+USER[[:space:]]\+ADDRESS[[:space:]]\+METHOD.*/q" ${pg_hba_conf_sample}
        cat <<EOF >> ${pg_hba_conf_sample}
 local  all             all                                     ident
EOF
    }

    pg_home=$(getent passwd postgres | cut -d':' -f 6)
    test "x${pg_home}" != "x" && test -d ${pg_home} && {
            test "$(stat -c '%U.%G' ${pg_home})" == "postgres.postgres" || chown postgres.postgres ${pg_home}
            test "$(stat -c '%a' ${pg_home})" == "711" || chmod 711 ${pg_home}
            # ensure sane permission
        }
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            /usr/pgsql-${postgresql_version}/bin/postgres --version
            ;;
        'debian' | 'ubuntu')
            /usr/lib/postgresql/${postgresql_version}/bin/postgres --version
            ;;
    esac
}

{
    flock -w 10 7 || exit 1

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
} 7> ${lock_file}

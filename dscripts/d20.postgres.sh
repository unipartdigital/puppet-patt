#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f $0; }" EXIT

# Catch unitialized variables:
set -u

# arch | vendor | major
get_system_release () {
    query=$1
    if [ "x$query" == "xarch" ]; then uname -m; return $?; fi
    if [ -f /etc/redhat-release ]; then
        release=$(rpm -q --whatprovides /etc/redhat-release)
        case $query in
            'major')
                echo $release | rev |  cut -d '-' -f 2 | rev
                ;;
            'vendor')
                echo $release | rev |  cut -d '-' -f 4 | rev
                ;;
            *)
                echo "query not implemented: $query" 1>&2
                exit 1
        esac
    fi
}

init() {
    postgresql_version=${1:-"11"}

    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    release_arch=$(get_system_release "arch")

    rel_repo="https://download.postgresql.org/pub/repos/yum/reporpms/EL-${release_major}-${release_arch}/pgdg-redhat-repo-latest.noarch.rpm"
    rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${release_major}.noarch.rpm"

    case "${release_vendor}" in
        'redhat' | 'centos')
            if [ "${release_major}" -lt 8 ]; then
                yum install -y ${rel_repo} ${rel_epel}
                yum install -y \
                    postgresql${postgresql_version} \
                    postgresql${postgresql_version}-server \
                    postgresql${postgresql_version}-contrib
                #postgresql${postgresql_version}-devel
            else
                dnf install -y ${rel_repo} ${rel_epel}
                dnf install -y \
                    postgresql${postgresql_version} \
                    postgresql${postgresql_version}-server \
                    postgresql${postgresql_version}-contrib
                #postgresql${postgresql_version}-devel
            fi

            sed -i -e "/#[[:space:]]*TYPE[[:space:]]\+DATABASE[[:space:]]\+USER[[:space:]]\+ADDRESS[[:space:]]\+METHOD.*/q" /usr/pgsql-${postgresql_version}/share/pg_hba.conf.sample
            cat <<EOF >> /usr/pgsql-${postgresql_version}/share/pg_hba.conf.sample
 local  all             all                                     ident
EOF
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
}


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

#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; } | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0 ; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

wait_pg_isready () {
    postgresql_version=${1:-"13"}
    timeout=${2:-360}
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            PATH=$PATH:/usr/pgsql-${postgresql_version}/bin
        ;;
        'debian' | 'ubuntu')
            PATH=$PATH:/usr/lib/postgresql/${postgresql_version}/bin
        ;;
    esac
    start=$(date +"%s")
    while [ 0 ]; do
        test pg_isready && { echo "pg is ready" ; break ; }
        test $(($start + $timeout)) -lt $(date +"%s") || { echo "timeout" >&2 ; exit 1; }
        sleep 3
    done
}

case "${1}" in
    'wait_pg_isready')
        shift 1
        wait_pg_isready "$@"
        ;;
    *)
        echo "usage: $0 <postgres version: 11 | 12 | 13 ...> timeout (default 360s)"
        exit 1
        ;;
esac

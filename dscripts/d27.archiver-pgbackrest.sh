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

pgbackrest_version () {
    for i in 1 2 3; do
        { pgbackrest version | awk '{print $2}' && break ; } || sleep 1
    done
}

pkg_init () {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            pkg="pgbackrest"
            dnf -q -y install $pkg
            ;;
        "debian" | "ubuntu")
            pkg="pgbackrest"
            apt-get -qq -y install $pkg
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    for i in 1 2 3; do
        { pgbackrest version && break ; } || sleep 1
    done
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # get pgbackrest version on postgres peer
    'pgbackrest_version')
        shift 1
        { flock -w 10 8 || exit 1
          pgbackrest_version "$@"
        } 8< ${lock_file}
        ;;
    # must be run on each postgres peer
    'pkg_init')
        shift 1
        { flock -w 10 8 || exit 1
          pkg_init "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 pgbackrest_version
 $0 pkg_init
EOF
            exit 1
        } >&2
        ;;
esac

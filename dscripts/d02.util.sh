#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; rm -f $0 ; } | tee ${srcdir}/$(basename $0).log' ERR
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

    {
        xfs_growfs -V > /dev/null 2>&1
        cryptsetup -V > /dev/null 2>&1
        lvextend --version > /dev/null 2>&1
    } || {

        case "${os_id}" in
            'rhel' | 'centos' | 'fedora' | 'rocky')
                pkg="util-linux xfsprogs lvm2 cryptsetup psmisc"
                dnf -q -y install $pkg
                ;;
            "debian" | "ubuntu")
                pkg="util-linux xfsprogs lvm2 cryptsetup-bin psmisc"
                apt-get -qq -y install $pkg
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }
}


{
    flock -n 9 || exit 1

    case "$1" in
        'init')
            shift 1
            init "$@"
            ;;
        *)
            echo "$0 error : $1" 1>&2 ; exit 1
            ;;
    esac
} 9> ${lock_file}

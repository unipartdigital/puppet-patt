#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO! ; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0 ; }" EXIT

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
    test "`${prefix}/bin/wal-g --version | awk '{print $3}'`" == "${walg_release}" > /dev/null 2>&1 || {
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

    ${prefix}/bin/wal-g --version
}

case "${1:-''}" in
    'init')
        shift 1
        init "$@"
        ;;
    *)
        echo "usage: $0 <wal-g release version> ['v0.2.19']"
        exit 1
        ;;
esac

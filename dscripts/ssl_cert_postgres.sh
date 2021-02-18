#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
#trap "{ rm -f ${lock_file} ; rm -f $0; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

copy_ca() {
    src="$1"
    dst="$2"

    cd $srcdir
    case "${os_id}" in
        'redhat' | 'centos' | 'debian' | 'ubuntu')
            postgres_home=$(getent passwd postgres | cut -d: -f6)
            if [  ! -d "${postgres_home}/.postgresql/" ]; then
                mkdir -m 700 "${postgres_home}/.postgresql/"
                chown postgres.postgres "${postgres_home}/.postgresql/"
            fi
            md5_src=$(md5sum ${src} | cut -d' ' -f 1)
            md5_dst=""
            if [ -r "${postgres_home}/.postgresql/${dst}" ]; then
                md5_dst=$(md5sum ${dst} | cut -d' ' -f 1)
            fi
            if [ "x${md5_src}" != "x${md5_dst}" ]; then
                cp "${src}" "${postgres_home}/.postgresql/${dst}"
                chown postgres.postgres "${postgres_home}/.postgresql/${dst}"
                if file "${postgres_home}/.postgresql/${dst}" |  grep -q "private key" ; then
                    chmod 600 "${postgres_home}/.postgresql/${dst}"
                elif file "${postgres_home}/.postgresql/${dst}" |  grep -q "PEM certificate" ; then
                    chmod 644 "${postgres_home}/.postgresql/${dst}"
                fi
            fi
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

{
    flock -n 9 || exit 1

    case "${1}" in
        'copy_ca')
            shift 1
            copy_ca "$@"
            ;;
        *)
            echo "usage: $0 copy source_cert destination_base_name"
            exit 1
            ;;
    esac
} 9> ${lock_file}

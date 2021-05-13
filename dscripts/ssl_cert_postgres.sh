#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
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

case "${os_id}" in
    'debian' | 'ubuntu')
        export DEBIAN_FRONTEND=noninteractive
        ;;
esac

init() {
    py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
    test "${py_ver}" -ge 38 || {
        dnf -q -y install python38
        alternatives --set python3 /usr/bin/python3.8
    }
    py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
    test "${py_ver}" -ge 38 || { echo "python3 < 38" >&2 ; exit 1 ; }
    python3 -c "import yaml" || { dnf -q -y install python${py_ver}-pyyaml ; }
    python3 -c "import cryptography.hazmat,cryptography.x509" || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                dnf -q -y install python${py_ver}-cryptography
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install python3-cryptography
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }
}

copy_ca() {
    src="$1"
    dst="$2"

    cd $srcdir
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
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
    flock -n 6 || exit 1

    case "${1}" in
        'init')
            shift 1
            init "$@"
            ;;
        'copy_ca')
            shift 1
            copy_ca "$@"
            ;;
        *)
            echo "usage: $0 copy source_cert destination_base_name"
            exit 1
            ;;
    esac
} 6> ${lock_file}

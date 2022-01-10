#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!" ; } | tee ${srcdir}/$(basename $0).log' ERR
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

tune () {
    tuned --version > /dev/null 2>&1 || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora' | 'rocky')
                dnf -q -y install tuned
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install tuned
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }
    mkdir -p /etc/tuned/postgresql
    cat <<EOF > /etc/tuned/postgresql/tuned.conf.$$
[main]
$(if cat /proc/cpuinfo | grep -q hypervisor ; then echo "include=virtual-guest" ; else echo "include=throughput-performance" ; fi)
[vm]
transparent_hugepages=never
EOF

        if [ -f /etc/tuned/postgresql/tuned.conf ] ; then
            ta_md5=$(md5sum /etc/tuned/postgresql/tuned.conf | cut -d' ' -f1)
            tb_md5=$(md5sum /etc/tuned/postgresql/tuned.conf.$$ | cut -d' ' -f1)
            if [ "x${ta_md5}" == "x${tb_md5}" ]; then
                rm -f /etc/tuned/postgresql/tuned.conf.$$
            else
                mv /etc/tuned/postgresql/tuned.conf.$$ /etc/tuned/postgresql/tuned.conf
                # reload
                tuned-adm off
                tuned-adm profile postgresql
            fi
        else
            mv /etc/tuned/postgresql/tuned.conf.$$ /etc/tuned/postgresql/tuned.conf
            tuned-adm profile postgresql
            systemctl enable --now tuned
        fi
}

case "${1}" in
    'enable')
        shift 1
        { flock -w 10 8 || exit 1
          tune "$@"
        } 8> ${lock_file}
        ;;
    *)
        echo "usage: $0 copy source_cert destination_base_name"
        exit 1
        ;;
esac

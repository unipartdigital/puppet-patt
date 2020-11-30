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

# arch | vendor | major
get_system_release () {
    query=$1
    if [ "x$query" == "xarch" ]; then uname -m; return $?; fi
    if [ -f /etc/redhat-release ]; then
        release=$(rpm -q --whatprovides /etc/redhat-release)
        case $query in
            'major')
                echo $release | rev | cut -d '-' -f 2 | rev | cut -d '.' -f1
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

tune () {
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    release_arch=$(get_system_release "arch")

    case "${release_vendor}" in
        'redhat' | 'centos')
            dnf install -y tuned
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
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
}

{
    flock -n 9 || exit 1

    case "${1}" in
        'enable')
            shift 1
                tune "$@"
            ;;
        *)
            echo "usage: $0 copy source_cert destination_base_name"
            exit 1
            ;;
    esac
} 9> ${lock_file}

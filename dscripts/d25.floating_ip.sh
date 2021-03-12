#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
touch ${lock_file} 2> /dev/null; chmod o+r+w ${lock_file}
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ; exit 1 ; }" | tee ${srcdir}/$(basename $0).log' ERR
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
    ip_takeover_version=${1:-"0.9"}
    test "$(sudo /usr/local/sbin/ip_takeover --version)" == "${ip_takeover_version}" || {

        rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"

        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                test "${py_ver}" -ge 38 || exit 1
                # python36 use python3-pip 9.0.3 which start to be quiet old.
                if [ "${os_major_version_id}" -lt 8 ]; then
                    rpm_pkg="python${py_ver}-psycopg2 python${py_ver}-pip gcc python${py_ver}-devel python${py_ver}-Cython python3-scapy make"
                    # psycopg2 is shipped by epel on centos 7
                    yum install -y ${rel_epel} ${rpm_pkg}
                else
                    rpm_pkg="python${py_ver}-psycopg2 python${py_ver}-pip gcc python${py_ver}-devel python${py_ver}-Cython python3-scapy make"
                    # psycopg2 is shipped by epel on centos 7
                    dnf install -y epel-release
                    # ensure that config-manager is installed
                    dnf config-manager --help > /dev/null 2>&1 || dnf install 'dnf-command(config-manager)' -y
                    # EPEL packages assume that the 'PowerTools' repository is enabled
                    dnf config-manager --set-enabled PowerTools
                    dnf install -y ${rpm_pkg}
                fi
                ;;
            'debian' | 'ubuntu')
                apt-get install -qq -y python3-pip gcc libpython3-all-dev cython3 python3-scapy make
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }

}

build () {
    ip_takeover_version=${1:-"0.9"}
    test "$(sudo /usr/local/sbin/ip_takeover --version)" == "${ip_takeover_version}" || {
        make -f ip_takeover.make install || exit 1
        make -f ip_takeover.make distclean
    }
}

enable () {
    fconf=/usr/local/etc/patroni_floating_ip.conf
    floating_ip=$*
    for i in ${floating_ip[@]}; do
        echo $i >> ${fconf}.$$
    done
    chmod 0644  ${fconf}.$$
    if [ -f "${fconf}" ]; then
        if diff ${fconf} ${fconf}.$$; then
            rm -f ${fconf}.$$
        else
            mv ${fconf}.$$ ${fconf}
        fi
    else
        mv ${fconf}.$$ ${fconf}
    fi
}

{
    flock -n 9 || exit 1

    case "${1:-""}" in
        'init')
            shift 1
            init "$@"
            ;;
        'build')
            cd ${srcdir}
            shift 1
            build "$@"
            ;;
        'enable')
            shift 1
            enable "$@"
            ;;
        *)
            echo "usage: $0 init|build|enable <list of floating_ip>"
            exit 1
            ;;
    esac
} 9> ${lock_file}

#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; rm -f $0 ; exit 1 ; } | tee ${srcdir}/$(basename $0).log' ERR
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
    test "$(sudo /usr/local/sbin/ip_takeover --version 2> /dev/null)" == "${ip_takeover_version}" || {

        rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"

        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                test "${py_ver}" -ge 38 || {
                    dnf -q -y install python38
                    alternatives --set python3 /usr/bin/python3.8
                }
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                test "${py_ver}" -ge 38 || { echo "python3 < 38" >&2 ; exit 1 ; }
                # python36 use python3-pip 9.0.3 which start to be quiet old.
                rpm_pkg="python${py_ver}-psycopg2 python${py_ver}-pip gcc python${py_ver}-devel python${py_ver}-Cython python3-scapy make"
                # psycopg2 is shipped by epel on centos 7
                dnf -q -y install epel-release
                # ensure that config-manager is installed
                dnf config-manager --help > /dev/null 2>&1 || dnf -y install 'dnf-command(config-manager)'
                # EPEL packages assume that the 'PowerTools' repository is enabled
                dnf config-manager --set-enabled PowerTools || true
                dnf -q -y install ${rpm_pkg}
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install python3-pip gcc libpython3-all-dev cython3 python3-scapy make
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
    test "$(sudo /usr/local/sbin/ip_takeover --version 2> /dev/null)" == "${ip_takeover_version}" || {
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

touch ${lock_file} 2> /dev/null || true

case "${1:-""}" in
    'init')
        shift 1
        { flock -n 9 || exit 1
          init "$@"
        } 9< ${lock_file}
        ;;
    'build')
        { flock -n 9 || exit 1
          cd ${srcdir}
          shift 1
          build "$@"
        } 9< ${lock_file}
        ;;
    'enable')
        shift 1
        { flock -n 9 || exit 1
          enable "$@"
        } 9< ${lock_file}
        ;;
    *)
        echo "usage: $0 init|build|enable <list of floating_ip>"
        exit 1
        ;;
esac

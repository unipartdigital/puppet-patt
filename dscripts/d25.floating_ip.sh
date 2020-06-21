#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ; exit 1; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f $0; }" EXIT

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

init() {
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    # release_arch=$(get_system_release "arch")

    rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${release_major}.noarch.rpm"

    case "${release_vendor}" in
        'redhat' | 'centos')
            if [ "${release_major}" -lt 8 ]; then
                rpm_pkg="python36-psycopg2 python36-pip gcc python36-devel python36-Cython python3*-scapy make"
                # psycopg2 is shipped by epel on centos 7
                yum install -y ${rel_epel} ${rpm_pkg}
            else
                rpm_pkg="python3-psycopg2 python3-pip gcc python3-devel python3-Cython python3-scapy make"
                # psycopg2 is shipped by epel on centos 7
                dnf install -y epel-release
                # ensure that config-manager is installed
                dnf config-manager || dnf install 'dnf-command(config-manager)' -y
                # EPEL packages assume that the 'PowerTools' repository is enabled
                dnf config-manager --set-enabled PowerTools
                dnf install -y ${rpm_pkg}

            fi
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac

}

build () {

    cat <<'EOF' > ./Makefile

CYTHON3 := $(shell which cython3 2> /dev/null || which cython 2> /dev/null || which cython3.8 2> /dev/null || which cython3.6 2> /dev/null)
PYTHON := python3

main: ip_takeover

scapy:
# install from pip if no system module
	-$(shell $(PYTHON) -c "import scapy" || pip3 install --user scapy[basic])

ip_takeover.py: scapy

ip_takeover.c: ip_takeover.py
	$(CYTHON3) -3 --embed ip_takeover.py

ip_takeover: ip_takeover.c
	gcc `python3-config --cflags --ldflags` -o ip_takeover ip_takeover.c
	strip --strip-unneeded ip_takeover

install: ip_takeover
	sudo install -o root -g postgres -m 4750 ip_takeover /usr/local/sbin/

uninstall:
	sudo $(RM) /usr/local/sbin/ip_takeover

clean:
	$(RM) ip_takeover.c

distclean: clean
	$(RM) ip_takeover

EOF

    make install || exit 1
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

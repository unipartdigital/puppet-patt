#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
touch ${lock_file} 2> /dev/null; chmod o+r+w ${lock_file}
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ; exit 1; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0; }" EXIT

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

    rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            if [ "${os_major_version_id}" -lt 8 ]; then
                rpm_pkg="python36-psycopg2 python36-pip gcc python36-devel python36-Cython python3*-scapy make"
                # psycopg2 is shipped by epel on centos 7
                yum install -y ${rel_epel} ${rpm_pkg}
            else
                rpm_pkg="python3-psycopg2 python3-pip gcc python3-devel python3-Cython python3-scapy make"
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
            apt-get install -y python3-pip gcc libpython3-all-dev cython3 python3-scapy make
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
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
	gcc -fPIC -o ip_takeover ip_takeover.c `{ python3-config --embed > /dev/null && python3-config --cflags --ldflags --embed ; } || python3-config --cflags --ldflags`
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
    rm -f ./Makefile ./ip_takeover ./ip_takeover.c
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

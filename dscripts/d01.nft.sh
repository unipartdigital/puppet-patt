#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ; }" | tee ${srcdir}/$(basename $0).log' ERR
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

    pkg="python3 nftables"
    rule_file='"/etc/nftables/postgres_patroni"'

    {
        python3 --version > /dev/null 2>&1
        nft --version > /dev/null 2>&1
    } || {

        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                if [ "${os_major_version_id}" -lt 8 ]; then
                    yum install -y $pkg
                else
                    dnf install -y $pkg
                fi
                nftables_conf="/etc/sysconfig/nftables.conf"
                ;;
            "debian" | "ubuntu")
                apt-get install -y $pkg
                test -d /etc/nftables/ || mkdir -p /etc/nftables/
                nftables_conf="/etc/nftables.conf"
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            nftables_conf="/etc/sysconfig/nftables.conf"
            ;;
        "debian" | "ubuntu")
            nftables_conf="/etc/nftables.conf"
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

    if [ ! -f /etc/nftables/postgres_patroni ]; then
        touch /etc/nftables/postgres_patroni || exit 1
    fi
    if grep  -q "include[[:space:]]*$rule_file" ${nftables_conf} ; then
        if ! grep  -q "^[[:space:]]*${rule_file}" ${nftables_conf} ; then
            sed -i -e "s|.*\("include[[:space:]]*$rule_file"\)|\1|" ${nftables_conf}
        fi
    else
        cat <<EOF >> ${nftables_conf}
#
# Postgresql Patroni nftables rules
include "/etc/nftables/postgres_patroni"
EOF

    fi

}

nftables_enable() {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            systemctl is-enabled nftables || systemctl enable --now nftables
            if [ -f /etc/nftables/postgres_patroni.nft ]; then
                if nft -c 'flush ruleset; include "/etc/nftables/postgres_patroni.nft";'; then
                    if [ "$(md5sum /etc/nftables/postgres_patroni.nft | cut -d ' ' -f 1)" == "$(md5sum /etc/nftables/postgres_patroni | cut -d ' ' -f 1)" ]; then
                        rm -f /etc/nftables/postgres_patroni.nft
                    else
                        mv /etc/nftables/postgres_patroni.nft /etc/nftables/postgres_patroni
                        systemctl reload nftables
                    fi
                else
                    rm -f /etc/nftables/postgres_patroni.nft
                    exit 1
                fi
                systemctl status nftables
            fi
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

disable_firewalld () {
    if systemctl is-enabled nftables; then
        if systemctl is-enabled firewalld; then
            systemctl stop firewalld
            systemctl disable firewalld
        fi
    else
        if ! systemctl is-enabled firewalld; then
            systemctl enable firewalld
        fi
    fi
}

{
    flock -w 10 9 || exit 1

    case "$1" in
        'init')
            shift 1
            init "$@"
            ;;
        'nftables_enable')
            shift 1
            nftables_enable "$@"
            # disable firewalld if nftables is enabled
            # and re enable firewalld if nftables is disabled
            disable_firewalld
            ;;
        *)
            echo "$0 error : $1" 1>&2 ; exit 1
            ;;
    esac
} 9> ${lock_file}

#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

init() {
    case "${os_id}" in
        'redhat' | 'centos')

            pkg="python3 nftables"

            if [ "${os_major_version_id}" -lt 8 ]; then
                yum install -y $pkg
            else
                dnf install -y $pkg
            fi
            if [ ! -f /etc/nftables/postgres_patroni ]; then
                touch /etc/nftables/postgres_patroni || exit 1
            fi

            rule_file='"/etc/nftables/postgres_patroni"'
            if grep  -q $rule_file /etc/sysconfig/nftables.conf ; then
                sed -i -e "s|.*\("include[[:space:]]*$rule_file"\)|\1|" /etc/sysconfig/nftables.conf
            else
                cat <<EOF >> /etc/sysconfig/nftables.conf
#
# Postgresql Patroni nftables rules
include "/etc/nftables/postgres_patroni"
EOF

            fi

            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

nftables_enable() {
    case "${os_id}" in
        'redhat' | 'centos')
            if ! systemctl is-enabled nftables; then
                systemctl enable --now nftables
            fi
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
            return $?
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
    flock -n 9 || exit 1

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

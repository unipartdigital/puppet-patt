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
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"
            rpm_pkg="haproxy policycoreutils"
            if [ "${os_major_version_id}" -lt 8 ]; then
                yum install -y ${rel_epel} ${rpm_pkg}
            else
                dnf install -y epel-release ${rpm_pkg}
            fi
            ;;
        'debian' | 'ubuntu')
            haproxy -v || (cd /etc/systemd/system && ln -sf /dev/null haproxy.service)
            # don't let dpkg start the service during install
            apt-get update
            apt-get install -y haproxy policycoreutils

            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

enable () {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            test "$(readlink /etc/systemd/system/haproxy.service)" == "/dev/null" && \
                rm -f /etc/systemd/system/haproxy.service && systemctl daemon-reload
            if haproxy -f /etc/haproxy/haproxy.cfg -c; then
                /usr/sbin/setsebool -P haproxy_connect_any 1
                # let haproxy bind to any port even if SELinux is enforcing
                if systemctl status haproxy; then
                    # haproxy is running
                    systemctl reload haproxy
                else
                    systemctl enable --now haproxy
                    systemctl status haproxy
                fi
            else
                echo "haproxy config check error" 1>&2
                exit 1
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

    case "${1:-""}" in
        'init')
            shift 1
            init "$@"
            ;;
        'enable')
            shift 1
            enable "$@"
            ;;
        *)
            echo "usage: $0 init"
            exit 1
            ;;
    esac
} 9> ${lock_file}

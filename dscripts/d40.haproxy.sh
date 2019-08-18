#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
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
                echo $release | rev |  cut -d '-' -f 2 | rev
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

    rel_epel="yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-${release_major}.noarch.rpm"
    rpm_pkg="haproxy policycoreutils"

    case "${release_vendor}" in
        'redhat' | 'centos')
            if [ "${release_major}" -lt 8 ]; then
                yum install -y ${rel_epel}
                yum install -y ${rpm_pkg}
            else
                dnf install -y ${rel_epel}
                dnf install -y ${rpm_pkg}
            fi
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
}

enable () {
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    # release_arch=$(get_system_release "arch")

    case "${release_vendor}" in
        'redhat' | 'centos')
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
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
}

case "${1:-""}" in
    'init')
        shift 1
        init $*
        ;;
    'enable')
        shift 1
        enable $*
        ;;
    *)
        echo "usage: $0 init"
        exit 1
        ;;
esac
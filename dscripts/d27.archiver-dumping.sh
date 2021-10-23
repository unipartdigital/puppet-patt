#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; } | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} || true ; rm -f $0 ; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

pg_dump_version () {
    for i in 1 2 3; do
        { pg_dump --version | awk '{print $2}' && break ; } || sleep 1
    done
}

pkg_init () {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | "debian" | "ubuntu")
            :
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    for i in 1 2 3; do
        { pg_dump --version && break ; } || sleep 1
    done
}

systemd_service () {
    command="$1" ; shift 1
    systemd_service="$1" ; shift 1
    test -f /var/tmp/systemd-reload && {
        systemctl daemon-reload
        rm -f /var/tmp/systemd-reload
    }
    test -f "/etc/systemd/system/${systemd_service}" || {
        echo "systemd_service: /etc/systemd/system/${systemd_service} not found" >&2
        exit 1
    }
    case "${command}" in
        'enable')
            systemctl is-active ${systemd_service} || systemctl enable --now "${systemd_service}"
            ;;
        'disable')
            systemctl is-enabled ${systemd_service} && systemctl disable --now "${systemd_service}"
            ;;
        *)
            echo "`basename $0` unrecognized arguments: ${command}" >&2
            exit 1
            ;;
    esac
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # get pg_dump version on postgres peer
    'pg_dump_version')
        shift 1
        { flock -w 10 8 || exit 1
          pg_dump_version "$@"
        } 8< ${lock_file}
        ;;
    # must be run on each postgres peer
    'pkg_init')
        shift 1
        { flock -w 10 8 || exit 1
          pkg_init "$@"
        } 8< ${lock_file}
        ;;
    'systemd_service')
        shift 1
        { flock -w 10 8 || exit 1
          systemd_service "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 pg_dump_version
 $0 pkg_init
 $0 systemd_service [enable|disable] <service_name>
EOF
            exit 1
        } >&2
        ;;
esac

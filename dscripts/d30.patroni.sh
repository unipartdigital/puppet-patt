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

bashrc_setup () {
cat <<EOF | su - postgres
if [ -f /etc/bashrc -a ! -f ~/.bashrc ]; then
cat <<eof >  ~/.bashrc
# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions
eof
fi
EOF
}

bashprofile_setup() {
cat <<EOF | su - postgres
if [ ! -f ~/.pgsql_profile ]; then
cat <<\eof >  ~/.pgsql_profile
# .pgsql_profile
# not overridden
#
# Get the aliases and functions
if [ -f ~/.bashrc ]; then
   . ~/.bashrc
fi

# User specific environment and startup programs

PATH=\$PATH:\$HOME/.local/bin:\$HOME/bin

export PATH

if [ -f ~/patroni.yaml ]; then
   alias patronictl='patronictl -c ~/patroni.yaml'
fi
eof
fi
EOF
}

systemd_setup () {
    postgres_version=${1:-"11"}
    postgres_home=$(getent passwd postgres | cut -d ':' -f 6)
    release_vendor=$(get_system_release "vendor")

    default_postgres_path=$(su - postgres -c "echo $PATH")

    case "${release_vendor}" in
        'redhat' | 'centos')
            if [ -f /etc/systemd/system/postgresql-${postgres_version}_patroni.service ]; then return 0; fi
            systemd_service=/lib/systemd/system/postgresql-${postgres_version}.service
            sed -e "/ExecStartPre=.*check-db-dir.*/d" \
                -e "s|\(Type=\).*|\1simple|" -e "s|\(KillMode=\).*|\1process|" \
                -e "/TimeoutSec=/a\\\nRestart=no" \
                -e "/Environment=PGDATA/aEnvironment=PATH=/usr/pgsql-11/bin/:${default_postgres_path}" \
                -e "s|\(ExecStart=\).*|\1${postgres_home}/.local/bin/patroni ${postgres_home}/patroni.yaml|" \
                ${systemd_service} > /etc/systemd/system/postgresql-${postgres_version}_patroni.service
            systemctl daemon-reload
            ;;
        *)
            echo "${release_vendor} not implemented" 1>&2
            exit 1
            ;;
    esac
}

softdog_setup () {
    if [ "x$(cat /proc/1/cgroup  | cut -d '/' -f 2 | sed -e '/^$/d')" != "x" ]; then
        echo "softdog_setup skipped" 2>&1
        return 0
    fi
    # skip all if we are inside a container, lxc, docker ...

    watchdog_gid=$(stat -c "%G" /dev/watchdog 2> /dev/null)
    if [ "x$watchdog_gid" == "xpostgres" ]; then
        if [ "$(stat -c "%a" /dev/watchdog)" -eq "660" ]; then return 0 ; fi
    fi

    cat <<EOF > /etc/udev/rules.d/99-patroni-softdog.rules
KERNEL=="watchdog", GROUP="postgres", MODE="0660"
EOF
    cat <<EOF > /etc/modules-load.d/99-patroni-softdog.conf
# load linux software watchdog
softdog
EOF
    if [ -r /dev/watchdog ]; then
        rmmod softdog || true
    fi
    modprobe softdog || true
    watchdog_gid=$(stat -c "%G" /dev/watchdog)
    if [ "x$watchdog_gid" != "xpostgres" ]; then
        echo "softdog_setup error" 2>&1
        exit 1
    fi
}

init() {
    postgres_version=${1:-"11"}
    shift 1
    patroni_version=${1:-"1.6.0"}
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    # release_arch=$(get_system_release "arch")

    rel_epel="yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-${release_major}.noarch.rpm"
    rpm_pkg="python36-psycopg2 python36-pip gcc python36-devel haproxy python36-PyYAML"
    # psycopg2 is shipped by epel on centos 7

    case "${release_vendor}" in
        'redhat' | 'centos')
            if [ "${release_major}" -lt 8 ]; then
                yum install -y ${rel_epel}
                yum install -y ${rpm_pkg}
            else
                dnf install -y ${rel_epel}
                dnf install -y "${rpm_pkg}"
            fi
            softdog_setup
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
    cat <<EOF | su - postgres
pip3 install --user patroni[etcd]==${patroni_version}
EOF

    bashrc_setup
    bashprofile_setup
    systemd_setup ${postgres_version}
}

enable() {
    postgres_version=${1:-"11"}
    shift 1
    patroni_version=${1:-"1.6.0"}
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    # release_arch=$(get_system_release "arch")

    case "${release_vendor}" in
        'redhat' | 'centos')
            systemctl enable --now postgresql-${postgres_version}_patroni
            if systemctl status postgresql-${postgres_version}_patroni; then
                systemctl reload postgresql-${postgres_version}_patroni
            else
                systemctl start postgresql-${postgres_version}_patroni
            fi
            ;;
        *)
            echo "unsupported release vendor: ${release_vendor}" 1>&2
            exit 1
            ;;
    esac
}

check() {
cat <<EOF | su - postgres
patronictl -c ~/patroni.yaml list
EOF
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
    'check')
        shift 1
        check $*
        ;;
    *)
        echo "usage: $0 init|enable <postgres version 11|12...> <patroni version: 1.6.0* https://github.com/zalando/patroni/releases>"
        exit 1
        ;;
esac

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

init() {
    postgres_version=${1:-"11"}
    shift 1
    patroni_version=${1:-"1.6.0"}
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    # release_arch=$(get_system_release "arch")

    rel_epel="yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-${release_major}.noarch.rpm"
    rpm_pkg="python36-psycopg2 python36-pip gcc python36-devel haproxy"
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
    systemd_setup ${postgres_version}
}



case "${1:-""}" in
    'init')
        shift 1
        init $*
        ;;
    *)
        echo "usage: $0 init <postgres version 11|12...> <patroni version: 1.6.0* https://github.com/zalando/patroni/releases>"
        exit 1
        ;;
esac

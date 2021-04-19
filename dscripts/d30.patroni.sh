#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; rm -f $0 ; } | tee ${srcdir}/$(basename $0).log' ERR
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
[ -f ~/.bash_profile ] || cat <<\eof >  ~/.bash_profile
[ -f ~/.pgsql_profile ] && source ~/.pgsql_profile
eof
EOF
}

systemd_patroni_tmpl () {
    postgres_version=${1}
    postgres_bin=${2}
    postgres_home=$(getent passwd postgres | cut -d ':' -f 6)

    cat <<EOF
[Unit]
Description=Patroni PostgreSQL ${postgres_version} database server
Documentation=https://www.postgresql.org/docs/${postgres_version}/static/
After=syslog.target
After=network.target

[Service]
Type=simple
User=postgres
Group=postgres
Environment=PGDATA=${postgres_home}/${postgres_version}/data/
Environment=PATH=${postgres_bin}:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin
OOMScoreAdjust=-1000
Environment=PG_OOM_ADJUST_FILE=/proc/self/oom_score_adj
Environment=PG_OOM_ADJUST_VALUE=0
ExecStart=${postgres_home}/.local/bin/patroni ${postgres_home}/patroni.yaml
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
KillSignal=SIGINT
TimeoutSec=0
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
EOF
}

systemd_setup () {
    postgres_version=${1}
    postgres_home=$(getent passwd postgres | cut -d ':' -f 6)

    default_postgres_path=$(su - postgres -c "echo $PATH")

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            systemd_service="postgresql-${postgres_version}.service"
            postgres_bin="/usr/pgsql-${postgres_version}/bin/"
            ;;
        'debian' | 'ubuntu')
            systemd_service="postgresql.service"
            postgres_bin="/usr/lib/postgresql/${postgres_version}/bin/"
            ;;
        *)
            echo "${os_id} not implemented" 1>&2
            exit 1
            ;;
    esac

    test -f /etc/systemd/system/postgresql-${postgres_version}_patroni.service && {
        test "`systemd_patroni_tmpl ${postgres_version} ${postgres_bin} | md5sum | cut -d' ' -f1`" == \
             "`md5sum /etc/systemd/system/postgresql-${postgres_version}_patroni.service | cut -d' ' -f1`" || {
            echo "OVERWRITE /etc/systemd/system/postgresql-${postgres_version}_patroni.service"
            systemd_patroni_tmpl "${postgres_version}" "${postgres_bin}" > \
                                 /etc/systemd/system/postgresql-${postgres_version}_patroni.service
            systemctl daemon-reload
        }
    }

    test -f /etc/systemd/system/postgresql-${postgres_version}_patroni.service || {

        if systemctl is-enabled --quiet ${systemd_service} ; then systemctl disable  ${systemd_service}; fi
        if systemctl is-active --quiet ${systemd_service} ; then systemctl stop  ${systemd_service}; fi
        systemd_patroni_tmpl "${postgres_version}" "${postgres_bin}" > \
                             /etc/systemd/system/postgresql-${postgres_version}_patroni.service
        systemctl daemon-reload
    }
}

softdog_setup () {
    if [ "x$(cat /proc/1/cgroup  | cut -d '/' -f 2 | sed -e '/^$/d')" != "x" ]; then
        echo "softdog_setup skipped" 2>&1
        return 0
    fi
    # skip all if we are inside a container, lxc, docker ...

    watchdog_gid=""
    if [ -r "/dev/watchdog" ]; then
        watchdog_gid=$(stat -c "%G" /dev/watchdog 2> /dev/null)
    fi
    if [ -r "/dev/watchdog" -a "x$watchdog_gid" == "xpostgres" ]; then
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
        echo "$watchdog_gid: ${watchdog_gid}" 2>&1
        return 1
    fi
}

selinux_policy () {
    pe_file="${1}"
    module=`awk '/^[[:space:]]*module[[:space:]]/{print $2}' ${pe_file}`
    selinux_packages="/usr/local/share/selinux/packages/"

    {
        test -x /usr/sbin/semodule && test -x /usr/bin/checkmodule && test -x /usr/bin/semodule_package
    } || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                if dnf --version > /dev/null 2>&1 ; then
                    dnf install -q -y checkpolicy policycoreutils
                else
                    yum install -q -y checkpolicy policycoreutils
                fi
                ;;
            'debian' | 'ubuntu')
                apt-get install -qq -y policycoreutils checkpolicy semodule-utils selinux-policy-default
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }

    test -d "${selinux_packages}" || mkdir -p -m 755 "${selinux_packages}"
    { semodule -l | grep -q "^${module}$" && \
          test "`md5sum ${pe_file} | cut -d' ' -f1`" == \
               "`md5sum ${selinux_packages}/${module}.te  2> /dev/null | cut -d' ' -f1`"
    } || {
        # Build a MLS/MCS-enabled non-base policy module.
        checkmodule -M -m ${srcdir}/${module}.te -o ${srcdir}/${module}.mod
        semodule_package -o ${srcdir}/${module}.pp -m ${srcdir}/${module}.mod
        semodule -X 300 -i ${srcdir}/${module}.pp && {
            cp -f ${srcdir}/${module}.pp ${selinux_packages}/${module}.pp
            cp -f ${srcdir}/${module}.te ${selinux_packages}/${module}.te
        }
        rm -f ${srcdir}/${module}.te ${srcdir}/${module}.mod ${srcdir}/${module}.pp
    }
}

init() {
    postgres_version=${1:-"13"}
    patroni_version=${2:-"2.0.2"}
    pe_file="${3}"

    rel_epel="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${os_major_version_id}.noarch.rpm"

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
            test "${py_ver}" -ge 38 || {
                echo "python36 use python3-pip 9.0.3 which start to be quiet old." >&2; exit 1 ; }
            rpm_pkg="python${py_ver}-psycopg2 python${py_ver}-pip gcc python${py_ver}-devel haproxy python${py_ver}-PyYAML python${py_ver}-requests"
            if dnf --version > /dev/null 2>&1 ; then
                dnf install -y epel-release ${rpm_pkg}
            else
                # psycopg2 is shipped by epel on centos 7
                yum install -y ${rel_epel} ${rpm_pkg}
            fi
            softdog_setup || softdog_setup || { echo "warning: watchdog setup error" 1>&2 ; }
            ;;
        'debian' | 'ubuntu')
            apt-get install -qq -y python3-psycopg2 python3-pip python3-dev python3-yaml gcc haproxy
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

    touch /tmp/patroni_pip.stamp
    cat <<EOF | su - postgres
PATH=$PATH:~/.local/bin
pip3 -q install --user patroni[etcd]==${patroni_version}
EOF

    test -f "${srcdir}/${pe_file}" || { echo "error ${pe_file}" >&2 ; exit 1 ; }
    selinux_policy "${srcdir}/${pe_file}"

    bashrc_setup
    bashprofile_setup
    systemd_setup ${postgres_version}
}

enable() {
    postgres_version=${1:-"13"}
    postgres_home=$(getent passwd postgres | cut -d ':' -f 6)

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            if [ "x$(ps --no-header -C patroni -o pid)" == "x" ]; then
                systemctl start postgresql-${postgres_version}_patroni && {
                    systemctl enable postgresql-${postgres_version}_patroni; }
            elif [ "x" != "x$(find -L ${postgres_home}/.local/bin/patroni -newer /tmp/patroni_pip.stamp)" ]
            then
                systemctl restart postgresql-${postgres_version}_patroni
            elif [ -f "/tmp/patroni.reload" ]; then
                systemctl reload postgresql-${postgres_version}_patroni && \
                    rm -f "/tmp/patroni.reload"
            fi
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    rm -f /tmp/patroni_pip.stamp
}

check() {
    cat <<EOF | su - postgres
patronictl -c ~/patroni.yaml list
EOF
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
        'check')
            shift 1
            check "$@"
            ;;
        *)
            cat <<EOF
usage:
$0 init
$0 enable <postgres version 11|12...> <patroni version: 2.0.2*
   *https://github.com/zalando/patroni/releases>
EOF
            exit 1
            ;;
    esac
} 9> ${lock_file}

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

cluster_health_user="cluster-health"

selinux_policy () {
    pe_file="${1}"
    module=`awk '/^[[:space:]]*module[[:space:]]/{print $2}' ${pe_file}`
    selinux_packages="/usr/local/share/selinux/packages/"
    {
        test -x /usr/sbin/semodule && test -x /usr/bin/checkmodule && test -x /usr/bin/semodule_package
    } || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                dnf -q -y install checkpolicy policycoreutils
                ;;
            'debian' | 'ubuntu')
                apt-get -qq -y install policycoreutils checkpolicy semodule-utils selinux-policy-default
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

init () {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            { test -x /usr/sbin/httpd && test -f /usr/lib64/httpd/modules/mod_wsgi_python3.so ; } || {
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                dnf -q -y install python${py_ver}-mod_wsgi httpd
                systemctl mask httpd.service
            }
            ;;
        'debian' | 'ubuntu')
            { test -x /usr/sbin/apache2 && test -f /usr/lib/apache2/modules/mod_wsgi.so ; } || {
                (cd /etc/systemd/system ;  ln -sf /dev/null apache2.service)
                apt-get -qq -y install libapache2-mod-wsgi-py3 apache2
                rm -f /etc/systemd/system/apache2.service
                systemctl mask apache2.service
            }
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
}

configure () {
    httpd_instance=${1:-"patt_health"}
    comd=${2:-"tmpl2file.py"}
    tmpl=${3:-"monitoring-httpd.conf"}
    monitoring=${4:-"patt_monitoring.py"}
    wsgi_file=${5:-"cluster-health.wsgi"}
    pe_file=${6-:"cluster_health.te"}
    wsgi_user=${7:-$cluster_health_user}
    test "$(getent passwd  ${wsgi_user} | cut -d: -f1)" == "${wsgi_user}" || {
        useradd --home-dir "/home/${wsgi_user}" --user-group  \
                --comment "cluster health user" \
                --system --no-log-init \
                --shell /bin/false ${wsgi_user}
    }
    test -d /home/${wsgi_user} || {
        mkdir -m 711 -p /home/${wsgi_user}
        chown ${wsgi_user}.${wsgi_user} /home/${wsgi_user}
    }
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            test -d /etc/httpd/conf/conf.minimal.d || mkdir -p /etc/httpd/conf/conf.minimal.d
            python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl} -o /etc/httpd/conf/${httpd_instance}.conf \
                    --dictionary_key_val "defaultruntimedir=/run/httpd/instance-\${HTTPD_INSTANCE}"  \
                    --dictionary_key_val "pidfile=/run/httpd/instance-\${HTTPD_INSTANCE}.pid"        \
                    --dictionary_key_val "user=apache"                                               \
                    --dictionary_key_val "group=apache"                                              \
                    --dictionary_key_val "errorlog=logs/\${HTTPD_INSTANCE}_error_log"                \
                    --dictionary_key_val "customlog=logs/\${HTTPD_INSTANCE}_access_log"              \
                    --dictionary_key_val "mimemagicfile=conf/magic"                                  \
                    --dictionary_key_val "config_dir=conf/conf.minimal.d"                            \
                    --dictionary_key_val "wsgi_user=${wsgi_user}"                                    \
                    --chmod 644                                                                      \
                    --touch /var/tmp/$(basename $0 .sh).reload
            test -f /etc/httpd/conf/conf.minimal.d/00.conf || {
                cat <<EOF > /etc/httpd/conf/conf.minimal.d/00.conf
LoadModule mpm_event_module modules/mod_mpm_event.so
LoadModule systemd_module modules/mod_systemd.so
LoadModule log_config_module modules/mod_log_config.so
LoadModule mime_module modules/mod_mime.so
LoadModule dir_module modules/mod_dir.so
LoadModule authz_core_module modules/mod_authz_core.so
LoadModule unixd_module modules/mod_unixd.so
LoadModule wsgi_module modules/mod_wsgi_python3.so
EOF
            }
            ;;
        'debian' | 'ubuntu')
            test -d /etc/apache2-${httpd_instance} || mkdir -p /etc/apache2-${httpd_instance}
            test -d /etc/apache2-${httpd_instance}/conf.minimal.d || \
                mkdir -p /etc/apache2-${httpd_instance}/conf.minimal.d
            {
                cd /etc/apache2-${httpd_instance}
                test -d mods-available || ln -sf ../apache2/mods-available mods-available
                test -f envvars || cat ../apache2/envvars > envvars
                test -f magic || ln -sf ../apache2/magic magic
            }
            python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl} -o /etc/apache2-${httpd_instance}/apache2.conf \
                    --dictionary_key_val "defaultruntimedir=\${APACHE_RUN_DIR}"    \
                    --dictionary_key_val "pidfile=\${APACHE_PID_FILE}"             \
                    --dictionary_key_val "user=\${APACHE_RUN_USER}"                \
                    --dictionary_key_val "group=\${APACHE_RUN_GROUP}"              \
                    --dictionary_key_val "errorlog=\${APACHE_LOG_DIR}/error.log"   \
                    --dictionary_key_val "customlog=\${APACHE_LOG_DIR}/access_log" \
                    --dictionary_key_val "mimemagicfile=magic"                     \
                    --dictionary_key_val "confid_dir=conf.minimal.d"               \
                    --dictionary_key_val "wsgi_user=${wsgi_user}"                  \
                    --chmod 644                                                    \
                    --touch /var/tmp/$(basename $0 .sh).reload
            test -f /etc/apache2-${httpd_instance}/conf.minimal.d/00.conf || {
                cat <<EOF > /etc/apache2-${httpd_instance}/conf.minimal.d/00.conf
LoadModule mpm_event_module /usr/lib/apache2/modules/mod_mpm_event.so
LoadModule mime_module /usr/lib/apache2/modules/mod_mime.so
LoadModule dir_module /usr/lib/apache2/modules/mod_dir.so
LoadModule authz_core_module /usr/lib/apache2/modules/mod_authz_core.so
LoadModule wsgi_module /usr/lib/apache2/modules/mod_wsgi.so
EOF
            }
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    test -d /usr/local/share/patt/monitoring/wsgi/ || mkdir -p /usr/local/share/patt/monitoring/wsgi/
    python3 ${srcdir}/${comd} -t ${srcdir}/${monitoring} \
            -o /usr/local/share/patt/monitoring/${monitoring} \
            --chmod 644 \
            --touch /var/tmp/$(basename $0 .sh).reload

    python3 ${srcdir}/${comd} -t ${srcdir}/${wsgi_file} \
            -o /usr/local/share/patt/monitoring/wsgi/${wsgi_file} \
            --chmod 644 \
            --touch /var/tmp/$(basename $0 .sh).reload

    test -f "${srcdir}/${pe_file}" || { echo "error ${pe_file}" >&2 ; exit 1 ; }
    selinux_policy "${srcdir}/${pe_file}"

}

enable () {
    httpd_instance=${1:-"patt_health"}
    if ! systemctl is-enabled -q httpd\@${httpd_instance} ; then
        test -f /var/tmp/$(basename $0 .sh).reload && {
            systemctl is-active httpd@patt_health.service || {
                systemctl restart httpd\@${httpd_instance} && rm -f /var/tmp/$(basename $0 .sh).reload
            }
        }
        systemctl enable --now  httpd\@${httpd_instance}
    elif test -f /var/tmp/$(basename $0 .sh).reload ; then
        systemctl restart httpd\@${httpd_instance} && rm -f /var/tmp/$(basename $0 .sh).reload
    elif ! systemctl -q is-active httpd\@patt_health.service ; then
        systemctl start httpd\@${httpd_instance}
    fi
    systemctl status httpd\@${httpd_instance} > /dev/null ||  {
        systemctl status  httpd\@${httpd_instance}  >&2 ; exit 1
    }
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # must be run on each postgres peer
    'init')
        shift 1
        { flock -w 10 8 || exit 1
          init "$@"
        } 8< ${lock_file}
        ;;
    'configure')
        shift 1
        { flock -w 10 8 || exit 1
          configure "$@"
        } 8< ${lock_file}
        ;;
    'enable')
        shift 1
        { flock -w 10 8 || exit 1
          enable "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 init
EOF
            exit 1
        } >&2
        ;;
esac

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


init () {
    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            { test -x /usr/sbin/httpd && test -f /usr/lib64/httpd/modules/mod_wsgi_python3.so ; } || {
                py_ver=$(python3 -c 'import sys; print ("".join(sys.version.split()[0].split(".")[0:2]))')
                dnf install -q -y python${py_ver}-mod_wsgi httpd
                systemctl mask httpd.service
            }
            ;;
        'debian' | 'ubuntu')
            { test -x /usr/sbin/apache2 && test -f /usr/lib/apache2/modules/mod_wsgi.so ; } || {
                (cd /etc/systemd/system ;  ln -sf /dev/null apache2.service)
                apt-get install -qq -y libapache2-mod-wsgi-py3 apache2
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
    comd=${1:-"tmpl2file.py"}
    tmpl=${2:-"monitoring-httpd.conf"}
    httpd_instance=${3:-"patt_health"}
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
                    --chmod 644
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
                    --chmod 644
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

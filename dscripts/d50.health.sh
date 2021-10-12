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
            { /usr/bin/gnuplot --version || dnf -q -y install gnuplot ; }
            ;;
        'debian' | 'ubuntu')
            { test -x /usr/sbin/apache2 && test -f /usr/lib/apache2/modules/mod_wsgi.so ; } || {
                (cd /etc/systemd/system ;  ln -sf /dev/null apache2.service)
                apt-get -qq -y install libapache2-mod-wsgi-py3 apache2
                rm -f /etc/systemd/system/apache2.service
                systemctl mask apache2.service
            }
            { /usr/bin/gnuplot --version || apt-get -qq -y install gnuplot-nox ; }
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
    tmpl1=${3:-"monitoring-httpd.conf"}
    tmpl2=${4:-"df-recorder.service"}
    monitoring1=${5:-"patt_monitoring.py"}
    monitoring2=${6:-"df_recorder.py"}
    wsgi_file1=${7:-"cluster-health.wsgi"}
    wsgi_file2=${8:-"cluster-health-mini.wsgi"}
    wsgi_file3=${9:-"df_plot.wsgi"}
    wsgi_file4=${10:-"df_monitor.wsgi"}
    pe_file=${11:-"cluster_health.te"}
    cluster_config=${12:-"cluster_config.yaml"}
    wsgi_user=${cluster_health_user}

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
    test -d /home/${wsgi_user}/.cache || {
        mkdir -m 700 -p /home/${wsgi_user}/.cache
        chown ${wsgi_user}.${wsgi_user} /home/${wsgi_user}/.cache
    }

    # gnuplot
    mkdir -m 755 -p /var/www/gnuplot/{scripts,icons,plots}
    test `stat -c '%U' /var/www/gnuplot/plots/` == "${wsgi_user}" || {
        chown ${wsgi_user}.${wsgi_user} /var/www/gnuplot/plots/
    }
    test -f /var/www/gnuplot/index.html || touch /var/www/gnuplot/index.html
    test -f /var/www/gnuplot/favicon.ico || touch /var/www/gnuplot/favicon.ico
    # used by moz
    share_gnuplot_js=`find /usr/share/gnuplot/*/js -maxdepth 1 -type d`
    for js in ${share_gnuplot_js}/*.{js,css}
    do
        python3 ${srcdir}/${comd} -t ${js} -o /var/www/gnuplot/scripts/$(basename ${js}) --chmod 644
    done

    for i in ${share_gnuplot_js}/*.png
    do
        dst=/var/www/gnuplot/icons/$(basename ${i})
        test -f ${dst} || cp ${i} ${dst}
        dst=/var/www/gnuplot/scripts/$(basename ${i})
        test -f ${dst} || cp ${i} ${dst}
        # copy to jsdir too to keep compatibility with gnuplot generated html file
    done

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            test -d /etc/httpd/conf/conf.minimal.d || mkdir -p /etc/httpd/conf/conf.minimal.d
            share_gnuplot_js=`find /usr/share/gnuplot/*/js -maxdepth 1 -type d`
            python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl1} -o /etc/httpd/conf/${httpd_instance}.conf \
                    --dictionary_key_val "defaultruntimedir=/run/httpd/instance-\${HTTPD_INSTANCE}"  \
                    --dictionary_key_val "pidfile=/run/httpd/instance-\${HTTPD_INSTANCE}.pid"        \
                    --dictionary_key_val "user=apache"                                               \
                    --dictionary_key_val "group=apache"                                              \
                    --dictionary_key_val "errorlog=logs/\${HTTPD_INSTANCE}_error_log"                \
                    --dictionary_key_val "customlog=logs/\${HTTPD_INSTANCE}_access_log"              \
                    --dictionary_key_val "mimemagicfile=conf/magic"                                  \
                    --dictionary_key_val "apache_cfg_dir=conf/conf.minimal.d"                        \
                    --dictionary_key_val "wsgi_user=${wsgi_user}"                                    \
                    --chmod 644                                                                      \
                    --touch /var/tmp/$(basename $0 .sh)-httpd.reload
            python3 ${srcdir}/${comd} -t ${srcdir}/monitoring-httpd-00.conf.dnf \
                    -o /etc/httpd/conf/conf.minimal.d/00.conf                   \
                    --chmod 644                                                 \
                    --touch /var/tmp/$(basename $0 .sh)-httpd.reload
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
            python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl1} -o /etc/apache2-${httpd_instance}/apache2.conf \
                    --dictionary_key_val "defaultruntimedir=\${APACHE_RUN_DIR}"                           \
                    --dictionary_key_val "pidfile=\${APACHE_PID_FILE}"                                    \
                    --dictionary_key_val "user=\${APACHE_RUN_USER}"                                       \
                    --dictionary_key_val "group=\${APACHE_RUN_GROUP}"                                     \
                    --dictionary_key_val "errorlog=/var/log/apache2/${httpd_instance}_error.log"          \
                    --dictionary_key_val "customlog=/var/log/apache2/${httpd_instance}_access_log"        \
                    --dictionary_key_val "mimemagicfile=magic"                                            \
                    --dictionary_key_val "apache_cfg_dir=conf.minimal.d"                                  \
                    --dictionary_key_val "wsgi_user=${wsgi_user}"                                         \
                    --chmod 644                                                                           \
                    --touch /var/tmp/$(basename $0 .sh)-httpd.reload
            python3 ${srcdir}/${comd} -t ${srcdir}/monitoring-httpd-00.conf.apt \
                    -o /etc/apache2-${httpd_instance}/conf.minimal.d/00.conf    \
                    --chmod 644                                                 \
                    --touch /var/tmp/$(basename $0 .sh)-httpd.reload
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
    test -d /usr/local/share/patt/monitoring/wsgi/ || mkdir -p /usr/local/share/patt/monitoring/wsgi/

    for monitoring_files in ${monitoring1} ${monitoring2} "xhtml.py"
    do
        python3 ${srcdir}/${comd} -t ${srcdir}/${monitoring_files} \
                -o /usr/local/share/patt/monitoring/${monitoring_files} \
                --chmod 644 \
                --touch /var/tmp/$(basename $0 .sh)-httpd.reload
    done

    for wsgi_files in  ${wsgi_file1} ${wsgi_file2} ${wsgi_file3} ${wsgi_file4}
    do
        python3 ${srcdir}/${comd} -t ${srcdir}/${wsgi_files} \
                -o /usr/local/share/patt/monitoring/wsgi/${wsgi_files} \
                --chmod 644 \
                --touch /var/tmp/$(basename $0 .sh)-httpd.reload
    done

    python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl2} -o /etc/systemd/system/${tmpl2}             \
            --dictionary_key_val "user=${wsgi_user}"                                            \
            --dictionary_key_val "group=${wsgi_user}"                                           \
            --dictionary_key_val "df_recorder=/usr/local/share/patt/monitoring/${monitoring2}"  \
            --chmod 644                                                                         \
            --touch /var/tmp/$(basename $0 .sh)-df-recorder.reload

    test -f "${srcdir}/${pe_file}" || { echo "error ${pe_file}" >&2 ; exit 1 ; }
    echo selinux_policy "${srcdir}/${pe_file}"
    selinux_policy "${srcdir}/${pe_file}"

    chgrp `id -n -g ${wsgi_user}` ${srcdir} && chmod 750 ${srcdir}
    cat <<EOF | su "${wsgi_user}" -s /bin/bash
cd ${srcdir}
python3 -c "import yaml" > /dev/null 2>&1 || python3 -m pip install --user pyyaml
python3 df_monitor.wsgi -f ${cluster_config}
EOF
}

enable () {
    httpd_instance=${1:-"patt_health"}

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            httpd_service="httpd@${httpd_instance}"
            ;;
        'debian' | 'ubuntu')
            httpd_service="apache2@${httpd_instance}"
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

    for services in "${httpd_service}" "df-recorder.service"
    do
        pre=""
        case "${services}" in
            "${httpd_service}")
                pre="-httpd"
                ;;
            "df-recorder.service")
                pre="-df-recorder"
                ;;
        esac
        if ! systemctl is-enabled -q "${services}" ; then
            test -f /var/tmp/$(basename $0 .sh)${pre}.reload && {
                systemctl is-active "${services}" || {
                    systemctl restart "${services}" && \
                        rm -f /var/tmp/$(basename $0 .sh)${pre}.reload
                }
            }
            systemctl enable --now "${services}"
        elif test -f /var/tmp/$(basename $0 .sh)${pre}.reload ; then
            systemctl restart "${services}" && rm -f /var/tmp/$(basename $0 .sh)${pre}.reload
        elif ! systemctl -q is-active "${services}" ; then
            systemctl start "${services}"
        fi
        systemctl status "${services}" > /dev/null ||  {
            systemctl status "${services}"  >&2 ; exit 1
        }
    done

}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # must be run at least on each postgres and archiving peer
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

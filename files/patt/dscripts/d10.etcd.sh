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
        ETCD_CONF="/etc/default/etcd"
        ;;
    'rhel' | 'centos' | 'fedora')
        ETCD_CONF="/etc/etcd/etcd.conf"
        ;;
esac

faketty () {
    script -e -qfc "$(printf "%q " "$@")"
}

init() {

    etcd --version > /dev/null 2>&1 || {
        case "${os_id}" in
            'rhel' | 'centos' | 'fedora')
                # centos8 don't provide etcd yet
                dnf -q -y --nogpgcheck install etcd
                ;;
            'debian' | 'ubuntu')
                etcd --version > /dev/null 2>&1 || (cd /etc/systemd/system && ln -sf /dev/null etcd.service)
                # don't let dpkg start the service during install
                apt-get -q update
                apt-get -qq -y install etcd
                ;;
            *)
                echo "unsupported release vendor: ${os_id}" 1>&2
                exit 1
                ;;
        esac
    }
    # extend etcd.service
     faketty EDITOR="/bin/tee" systemctl edit etcd <<'EOF'
[Service]
ExecStartPost=-/bin/bash -c "/bin/ionice -c2 -n0 -p $(/bin/pgrep etcd)"
Nice=-10
EOF
}

check_healthy () {
    # ETCDCTL_API=3 etcdctl endpoint --cluster health 2>&1 | grep "is healthy" | cut -d ' ' -f 1
    ep=""
    for e in $(ETCDCTL_API=3 etcdctl member list -w fields | grep "ClientURL" | cut -d: -f2-); do
        ep=$ep,$e;
    done
    ep="${ep/,/}"
    ETCDCTL_API=3 etcdctl --endpoints=$ep endpoint health  2>&1 | grep "is healthy" | cut -d' ' -f1
}

check_unhealthy () {
    # ETCDCTL_API=3 etcdctl endpoint --cluster health 2>&1 | grep "is unhealthy" | cut -d ' ' -f 1
    ep=""
    for e in $(ETCDCTL_API=3 etcdctl member list -w fields | grep "ClientURL" | cut -d: -f2-); do
        ep=$ep,$e;
    done
    ep="${ep/,/}"
    ETCDCTL_API=3 etcdctl --endpoints=$ep endpoint health  2>&1 | grep "is unhealthy" | cut -d' ' -f1
}

check () {
    ETCDCTL_API=3 etcdctl member list -w table
    # ETCDCTL_API=3 etcdctl endpoint --cluster health -w table  2>&1
    ep=""
    for e in $(ETCDCTL_API=3 etcdctl member list -w fields | grep "ClientURL" | cut -d: -f2-); do
        ep=$ep,$e;
    done
    ep="${ep/,/}"
    ETCDCTL_API=3 etcdctl --endpoints=$ep endpoint health -w table

}

cluster_health () {
    etcdctl cluster-health | sed -n -e "/^cluster is/p"
}

config () {
    config_type=$1
    shift 1
    cluster_name=$1
    shift 1
    etcd_template=$1
    shift 1
    cluster_nodes=$*

    #self_id=$(hostid)
    self_id=$(< /etc/machine-id)

    self_node=""
    for n in ${cluster_nodes}; do
        self_node=$(echo $n | grep $self_id) && break
    done

    self_ip=$(echo "$self_node" | cut -d '_' -f 2)

    # validate
    if [ "x${self_id}" != "x$(echo "$self_node" | cut -d '_' -f 1)" ]; then
        echo "id error ${self_id} != $(echo $self_node | cut -d '_' -f 1)" 1>&2
        exit 1
    elif ! ip -6 addr show | grep "${self_ip}"; then
        exit 1
    else
        ping6 -c 1 "${self_ip}"
    fi

    ETCD_DATA_DIR=/var/lib/etcd/${self_id}
    test -d ${ETCD_DATA_DIR} || mkdir -p -m 700 ${ETCD_DATA_DIR}
    test "$(stat -c '%a' /var/lib/etcd/)" == '755' || chmod 755 "/var/lib/etcd/"
    test "$(stat -c '%a' ${ETCD_DATA_DIR})" == '700' || chmod 700 ${ETCD_DATA_DIR}
    test "$(stat -c "%U.%G" ${ETCD_DATA_DIR})" == "etcd.etcd" || \
        {
            cat <<EOF | su -
chown etcd.etcd "${ETCD_DATA_DIR}"
EOF
        }
    etcd_initial_cluster=""
    for n in ${cluster_nodes}; do
        ID=$(echo ${n} | cut -d '_' -f 1)
        IP=$(echo ${n} | cut -d '_' -f 2)
        etcd_initial_cluster="${etcd_initial_cluster},${ID}=https://[${IP}]:2380"
    done
    etcd_initial_cluster=$(echo ${etcd_initial_cluster} | sed -e 's|^,||')

    if [ ! -f "${ETCD_CONF}.ori" -a -f "${ETCD_CONF}" ]; then
        cp -a "${ETCD_CONF}" "${ETCD_CONF}.ori"
    fi

    if [ "x$config_type" == "xexisting" ]; then
        init_state=''
    else
        init_state="#"
    fi
    python3 ${srcdir}/tmpl2file.py -t ${srcdir}/${etcd_template} -o /etc/etcd/etcd.conf   \
                    --dictionary_key_val "ETCD_DATA_DIR=${ETCD_DATA_DIR}"               \
                    --dictionary_key_val "self_id=${self_id}"                           \
                    --dictionary_key_val "self_ip=${self_ip}"                           \
                    --dictionary_key_val "etcd_initial_cluster=${etcd_initial_cluster}" \
                    --dictionary_key_val "cluster_name=${cluster_name}"                 \
                    --dictionary_key_val "init_state=${init_state}"                     \
                    --chmod 644                                                         \
                    --touch /var/tmp/$(basename $0 .sh).reload
}

enable() {
    cluster_name=$1
    shift
    cluster_nodes=$*

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            test "$(readlink /etc/systemd/system/etcd.service)" == "/dev/null" && \
                rm -f /etc/systemd/system/etcd.service && systemctl daemon-reload
            systemctl reload-or-restart etcd
            for i in 1 2 3 4 5 6 7 8 9 10; do
                etcdctl cluster-health
                if [ "$?" -eq 0 ]; then
                    systemctl enable --now etcd
                    if [ -r ${ETCD_CONF} ]; then
                        . ${ETCD_CONF}
                        find "$(dirname ${ETCD_DATA_DIR})" -name "$(basename ${ETCD_DATA_DIR}).back-*" -delete
                    fi
                    break;
                fi
                if [ "$i" -gt 9 ]; then
                    systemctl stop etcd
                    exit 1;
                fi
                sleep 3
            done
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

}

disable() {
    cluster_name=$1
    shift
    cluster_nodes=$*

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora' | 'debian' | 'ubuntu')
            systemctl stop etcd
            if [ -r ${ETCD_CONF} ]; then
                . ${ETCD_CONF}
                if [ -d "${ETCD_DATA_DIR}" ]; then
                    mv "${ETCD_DATA_DIR}" "${ETCD_DATA_DIR}".back-`date "+%s"`
                fi
            fi
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac

}

member_add() {
    cluster_name=$1
    shift
    cluster_nodes=$*
    for n in ${cluster_nodes}; do
        ID=$(echo ${n} | cut -d '_' -f 1)
        IP=$(echo ${n} | cut -d '_' -f 2)
        if ETCDCTL_API=3 etcdctl member list | grep -q "${ID}"; then
            echo "member ${ID} already exist"
        else
            ETCDCTL_API=3 etcdctl member add ${ID} --peer-urls="https://[${IP}]:2380"
        fi
    done
}

member_remove() {
    cluster_name=$1
    shift
    cluster_nodes=$*
    for n in ${cluster_nodes[*]}; do
        if ping6 -c 1 "${n}"; then
            echo "$n alive not removing"
            continue
        fi
        m_id=$(etcdctl member list 2>&1 | grep "$n" | cut -d ':' -f 1)
        ETCDCTL_API=3 etcdctl member remove "${m_id}" || true
    done
}

version() {
    etcd --version | sed -nr -e "0,/etcd/s|^.*:[[:space:]]*||p"
}

case "$1" in
    'init')
        shift 1
        { flock -w 10 9 || exit 1
          init "$@"
        } 9> ${lock_file}
        ;;
    'check_healthy')
        shift 1
        check_healthy "$@"
        ;;
    'check_unhealthy')
        shift 1
        check_unhealthy "$@"
        ;;
    'check')
        shift 1
        check "$@"
        ;;
    'cluster_health')
        shift 1
        cluster_health "$@"
        ;;
    'config')
        shift 1
        { flock -w 10 9 || exit 1
          config "$@"
        } 9> ${lock_file}
        ;;
    'enable')
        shift 1
        { flock -w 10 9 || exit 1
          enable "$@"
        } 9> ${lock_file}
        ;;
    'member_add')
        shift 1
        { flock -w 10 9 || exit 1
          member_add "$@"
        } 9> ${lock_file}
        ;;
    'member_remove')
        shift 1
        { flock -w 10 9 || exit 1
          member_remove "$@"
        } 9> ${lock_file}
        ;;
    'version')
        shift 1
        version "$@"
        ;;
esac

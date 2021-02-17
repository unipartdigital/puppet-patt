#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0; }" EXIT

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
    'redhat' | 'centos')
        ETCD_CONF="/etc/etcd/etcd.conf"
        ;;
    esac

init() {
    case "${os_id}" in
        'redhat' | 'centos')
            if [ "${os_major_version_id}" -lt 8 ]; then
                yum install -y etcd
            else
                # centos8 don't provide etcd yet
                dnf install --nogpgcheck -y etcd
            fi
            ;;
        'debian' | 'ubuntu')
            etcd --version || (cd /etc/systemd/system && ln -sf /dev/null etcd.service)
            # don't let dpkg start the service during install
            apt-get update
            apt-get install -y etcd
            ;;
        *)
            echo "unsupported release vendor: ${os_id}" 1>&2
            exit 1
            ;;
    esac
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

config () {
    config_type=$1
    shift 1
    cluster_name=$1
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
    mkdir -p -m 700 "${ETCD_DATA_DIR}"
    chown etcd.etcd "${ETCD_DATA_DIR}"

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

    cat <<EOF > $ETCD_CONF
#[Member]
ETCD_DATA_DIR="${ETCD_DATA_DIR}"
ETCD_LISTEN_PEER_URLS="https://[::]:2380"
ETCD_LISTEN_CLIENT_URLS="http://[::]:2379"
ETCD_NAME="${self_id}"
#[Clustering]
ETCD_INITIAL_ADVERTISE_PEER_URLS="https://[${self_ip}]:2380"
ETCD_ADVERTISE_CLIENT_URLS="http://[${self_ip}]:2379"
ETCD_INITIAL_CLUSTER="${etcd_initial_cluster}"
ETCD_INITIAL_CLUSTER_TOKEN="${cluster_name}"
${init_state}ETCD_INITIAL_CLUSTER_STATE="existing"
#[Security]
#ETCD_CERT_FILE=""
#ETCD_KEY_FILE=""
#ETCD_CLIENT_CERT_AUTH="false"
#ETCD_TRUSTED_CA_FILE=""
#ETCD_AUTO_TLS="false"
#ETCD_PEER_CERT_FILE=""
#ETCD_PEER_KEY_FILE=""
#ETCD_PEER_CLIENT_CERT_AUTH="false"
#ETCD_PEER_TRUSTED_CA_FILE=""
ETCD_PEER_AUTO_TLS="true"
#
#[Logging]
#ETCD_DEBUG="false"
#ETCD_LOG_PACKAGE_LEVELS=""
#ETCD_LOG_OUTPUT="default"
EOF
}

enable() {
    cluster_name=$1
    shift
    cluster_nodes=$*

    case "${os_id}" in
        'redhat' | 'centos' | 'debian' | 'ubuntu')
            test "$(readlink /etc/systemd/system/etcd.service)" == "/dev/null" && \
                rm -f /etc/systemd/system/etcd.service && systemctl daemon-reload
            systemctl start etcd
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
        'redhat' | 'centos' | 'debian' | 'ubuntu')
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
        ETCDCTL_API=3 etcdctl member add ${ID} --peer-urls="https://[${IP}]:2380" || true
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

{
    flock -n 9 || exit 1

    case "$1" in
        'init')
            shift 1
            init "$@"
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
        'config')
            shift 1
            config "$@"
            ;;
        'enable')
            shift 1
            enable "$@"
            ;;
        'member_add')
            shift 1
            member_add "$@"
            ;;
        'member_remove')
            shift 1
            member_remove "$@"
            ;;
    esac
} 9> ${lock_file}

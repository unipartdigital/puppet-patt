#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f $0; }" EXIT

# Catch unitialized variables:
set -u

#
ETCD_CONF="/etc/etcd/etcd.conf"
#

# return self from list of ip:node_name
# ipv6 only
get_self_node () {
    cluster_nodes=$*
    for i in $(ip -6 addr show scope global | grep inet6 | awk '{print $2}' | cut -d '/' -f 1); do
        for j in ${cluster_nodes}; do
            if echo ${j} | grep -q ${i}; then
                echo ${j}
                return 0
            fi
        done
    done
    echo ""
    return 1
}

# param
# 1: cluster_name: <string>
# 2,n cluster_nodes: <machineID | HostID>_<Hostname | IPV4 | [IPV6]>
init() {
    cluster_name="$1"
    shift 1
    cluster_nodes=$*

    SELF_ID=$(hostid || cat /etc/machine-id 2> /dev/null)

    # exit if etcd already running
    if systemctl status etcd; then
        exit 1
    fi
    sudo yum install -y etcd

    self_node=$(get_self_node "${cluster_nodes}")
    self_id=$(echo "$self_node" | cut -d '_' -f 1)
    self_ip=$(echo "$self_node" | cut -d '_' -f 2)
    if [ "x${self_id}" != "x${SELF_ID}" ]; then
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
        etcd_initial_cluster="${etcd_initial_cluster},${ID}=http://[${IP}]:2380"
    done
    etcd_initial_cluster=$(echo ${etcd_initial_cluster} | sed -e 's|^,||')

    if [ ! -f "/etc/etcd/etcd.conf.ori" -a -f "/etc/etcd/etcd.conf" ]; then
        cp -a "/etc/etcd/etcd.conf" "/etc/etcd/etcd.conf.ori"
    fi

    cat <<EOF > /etc/etcd/etcd.conf
#[Member]
ETCD_DATA_DIR="${ETCD_DATA_DIR}"
ETCD_LISTEN_PEER_URLS="http://[::]:2380"
ETCD_LISTEN_CLIENT_URLS="http://[::]:2379"
ETCD_NAME="${self_id}"
#[Clustering]
ETCD_INITIAL_ADVERTISE_PEER_URLS="http://[${self_ip}]:2380"
ETCD_ADVERTISE_CLIENT_URLS="http://[${self_ip}]:2379"
ETCD_INITIAL_CLUSTER="${etcd_initial_cluster}"
ETCD_INITIAL_CLUSTER_TOKEN="${cluster_name}"
EOF

    systemctl start etcd && etcdctl cluster-health
    return $?
}

check () {
    :
}

case "$1" in
    'init')
        shift 1; init "$@"
        ;;
    'check')
        shift 1; check "$@"
        ;;
    *)
        echo "usage $0 [init cluster_name cluster_nodes (id_ipv6)]"
        ;;
esac

#!/bin/sh

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{echo "$0 FAILED on line $LINENO!; rm -f $0}" | tee $srcdir/$(basename $0).log' ERR
# clean up on exit
#trap "{ rm -f $0; }" EXIT

# Catch unitialized variables:
set -u
P1=${1:-1}

#
ETCD_CONF="/etc/etcd/etcd.conf"
#

# param
# 1: cluster_name <string>
# 2,n cluster_nodes <machineID | HostID>:<Hostname | IPV4 | [IPV6]>
init() {
    cluster_name=$1
    shift
    cluster_nodes=($@)
    (
        if [ -r "${ETCD_CONF}" ]; then
            . /etc/etcd/etcd.conf
            if find ${ETCD_DATA_DIR} -mindepth 1 -print -quit 2>/dev/null | grep -q ""; then
                echo "error: ${ETCD_DATA_DIR} not empty" 1>&2
                exit 1
            fi
        fi
    )

    sudo yum install -y etcd

    # ETCD_LISTEN_CLIENT_URLS all
    sed -i -e "s|^[[:space:]]*\(ETCD_LISTEN_CLIENT_URLS=\).*|\1\"http://0.0.0.0:2379,http://[::]:2379\"|" "${ETCD_CONF}"
    # ETCD_LISTEN_PEER_URLS
    sed -i -e "s|^#*\(ETCD_LISTEN_PEER_URLS=\).*|\1\"http://0.0.0.0:2380,http://[::]:2380\"|"  "${ETCD_CONF}"
    # ETCD_INITIAL_CLUSTER_TOKEN
    sed -i -e "s|^#*\(ETCD_INITIAL_CLUSTER_TOKEN=\).*|\1\"${cluster_name}\"|" "${ETCD_CONF}"
    # ETCD_INITIAL_CLUSTER_STATE
    sed -i -e "s|^#*\(ETCD_INITIAL_CLUSTER_STATE=\).*|\1\"new\"|" "${ETCD_CONF}"

    # ETCD_NAME
    SELF_ID=$(cat /etc/machine-id 2> /dev/null || hostid)
    sed -i -e "s|^#*\(ETCD_NAME=\).*|\1\"${SELF_ID}\"|" "${ETCD_CONF}"

    # ETCD_INITIAL_CLUSTER
    initial_cluster=""
    for n in ${cluster_nodes[@]}; do
        ID=$(echo ${n} | cut -d ':' -f 1)
        HT=$(echo ${n} | cut -d ':' -f 2)
        initial_cluster+="${ID}=http://${HT}:2380,"
    done
    initial_cluster=$(echo ${initial_cluster} | sed 's/,$//')
    sed -i -e "s|^#*\(ETCD_INITIAL_CLUSTER=\).*|\1\"${initial_cluster}\"|" "${ETCD_CONF}"

    systemctl restart etcd
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        sleep 1
        if etcdctl cluster-health; then
            break
        fi
    done
    return etcdctl cluster-health
}

finit () {

    # ETCD_INITIAL_CLUSTER_STATE
    sed -i -e "s|^#*\(ETCD_INITIAL_CLUSTER_STATE=\).*|\1\"existing\"|" "${ETCD_CONF}"

    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        sleep 1
        if etcdctl cluster-health; then
            break
        fi
    done
    if etcdctl cluster-health; then
        systemctl enable etcd
        systemctl restart etcd
    fi
    for i in 1 2 3 4 5 6 7 8 9 10; do
        sleep 1
        if etcdctl cluster-health; then
            break
        fi
    done
    return etcdctl cluster-health
}

check () {
    :
}

case "$1" in
    'init')
        shift
        init $*
        ;;
    'finit')
        shift
        finit $*
        ;;
    'check')
        shift
        check $*
        ;;
    *)
        echo "usage $0 [init cluster_name cluster_nodes]"
        ;;
esac

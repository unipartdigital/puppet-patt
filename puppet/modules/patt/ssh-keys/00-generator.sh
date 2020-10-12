#!/bin/sh

cluster_name=$1
keytype=$2
keydir=${3:-`pwd`}

case "$keytype" in
    'private')
        if [ ! -f "${keydir}/${cluster_name}_rsa" ]; then
            /usr/bin/ssh-keygen -t rsa -b 4096 -f ${keydir}/${cluster_name}_rsa -N "" -C ${cluster_name}
            /usr/bin/cat ${keydir}/${cluster_name}_rsa
        else
            /usr/bin/cat ${keydir}/${cluster_name}_rsa
        fi
        ;;
    'public')
        if [ ! -f "${keydir}/${cluster_name}_rsa.pub" ]; then
            /usr/bin/ssh-keygen -t rsa -b 4096 -f ${keydir}/${cluster_name}_rsa -N "" -C ${cluster_name}
            /usr/bin/cat ${keydir}/${cluster_name}_rsa.pub
        else
            /usr/bin/cat ${keydir}/${cluster_name}_rsa.pub
        fi
        ;;
esac

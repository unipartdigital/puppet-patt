#!/bin/sh

src_dir=$(cd $(dirname $0) && pwd)

cluster_name=$1
query=$2
user=$3
cert_dir=${src_dir}

mk_ca_cert () {
    ${cert_dir}/self_signed_certificate.py cli                        \
               --ca_country_name           "UK"                       \
               --ca_state_or_province_name "United Kingdom"           \
               --ca_locality_name          "Cambridge"                \
               --ca_organization_name      "Patroni Postgres Cluster" \
               --ca_common_name            "CA ${cluster_name}"       \
               --ca_not_valid_after        "3650"                     \
               --ca_path                   "${cert_dir}/${cluster_name}_ca.pem" \
               --ca_key_path               "${cert_dir}/${cluster_name}_ca.key"
}

mk_user_cert() {
    ${cert_dir}/self_signed_certificate.py cli                                  \
               --ca_path                   "${cert_dir}/${cluster_name}_ca.pem" \
               --ca_key_path               "${cert_dir}/${cluster_name}_ca.key" \
               --cert_country_name           "UK"                       \
               --cert_state_or_province_name "United Kingdom"           \
               --cert_locality_name          "Cambridge"                \
               --cert_organization_name      "Patroni Postgres Cluster" \
               --cert_common_name            "${user}"                  \
               --cert_not_valid_after        "547"                      \
               --cert_path                   "${cert_dir}/${cluster_name}_${user}.pem" \
               --cert_key_path               "${cert_dir}/${cluster_name}_${user}.key"
}

case "$query" in
    'root_cert')
        if [ -f "${cert_dir}/${cluster_name}_ca.pem" ]; then
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.pem
        else
            mk_ca_cert
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.pem
        fi
        ;;
    'root_key')
        if [ -f "${cert_dir}/${cluster_name}_ca.pem" ]; then
          /usr/bin/cat ${cert_dir}/${cluster_name}_ca.key
        else
            mk_ca_cert
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.key
        fi
        ;;
    'user_cert')
        if [ -f "${cert_dir}/${cluster_name}_${user}.pem" ]; then
            /usr/bin/cat ${cert_dir}/${cluster_name}_${user}.pem
        else
            if [ ! -f "${cert_dir}/${cluster_name}_ca.pem" ]; then mk_ca_cert; fi
            mk_user_cert
            /usr/bin/cat ${cert_dir}/${cluster_name}_${user}.pem
        fi
        ;;
    'user_key')
        if [ -f "${cert_dir}/${cluster_name}_${user}.key" ]; then
            /usr/bin/cat ${cert_dir}/${cluster_name}_${user}.key
        else
            if [ ! -f "${cert_dir}/${cluster_name}_ca.pem" ]; then mk_ca_cert; fi
            mk_user_cert
            /usr/bin/cat ${cert_dir}/${cluster_name}_${user}.key
        fi
        ;;
    'server_cert')
        echo "not implemented" ; exit 1
        ;;
    'server_key')
        echo "not implemented" ; exit 1
        ;;
    'verify')
        echo "not implemented" ; exit 1
        ;;
    'show')
        echo "not implemented" ; exit 1
        ;;
esac

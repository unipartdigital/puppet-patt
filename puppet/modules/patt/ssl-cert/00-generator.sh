#!/bin/sh

src_dir=$(cd $(dirname $0) && pwd)

cluster_name=$1
query=$2
cert_dir=${src_dir}

case "$query" in
    'root_cert')
        if [ -f "${cert_dir}/${cluster_name}_ca.pem" ]; then
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.pem
        else
            ${cert_dir}/self_signed_certificate.py cli                        \
                       --ca_country_name           "UK"                       \
                       --ca_state_or_province_name "United Kingdom"           \
                       --ca_locality_name          "Cambridge"                \
                       --ca_organization_name      "Patroni Postgres Cluster" \
                       --ca_common_name            "CA ${cluster_name}"       \
                       --ca_not_valid_after        "3650"                     \
                       --ca_path                   "${cert_dir}/${cluster_name}_ca.pem" \
                       --ca_key_path               "${cert_dir}/${cluster_name}_ca.key"
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.pem
        fi
        ;;
    'root_key')
        if [ -f "${cert_dir}/${cluster_name}_ca.pem" ]; then
          /usr/bin/cat ${cert_dir}/${cluster_name}_ca.key
        else
            ${cert_dir}/self_signed_certificate.py cli                        \
                       --ca_country_name           "UK"                       \
                       --ca_state_or_province_name "United Kingdom"           \
                       --ca_locality_name          "Cambridge"                \
                       --ca_organization_name      "Patroni Postgres Cluster" \
                       --ca_common_name            "CA ${cluster_name}"       \
                       --ca_not_valid_after        "3650"                     \
                       --ca_path                   "${cert_dir}/${cluster_name}_ca.pem" \
                       --ca_key_path               "${cert_dir}/${cluster_name}_ca.key"
            /usr/bin/cat ${cert_dir}/${cluster_name}_ca.key
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

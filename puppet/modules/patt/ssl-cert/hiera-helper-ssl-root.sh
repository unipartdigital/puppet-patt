#!/bin/bash
set -e

#
# should be safe to cut and past into a terminal from here
# cluster_name should be set in the evironement otherwise
# the output of uuidgen is used.
#

ssl_gen="/etc/puppetlabs/code/environments/production/modules/patt/files/patt/misc/self_signed_certificate.py"
cluster_name="${cluster_name:-`/usr/bin/uuidgen`}"
eyaml="/opt/puppetlabs/puppet/bin/eyaml"
tmp=`/usr/bin/mktemp -d`
{
    test -d $tmp || exit 1
    ${ssl_gen} cli \
        --ca_country_name           "UK"                       \
        --ca_state_or_province_name "United Kingdom"           \
        --ca_locality_name          "Cambridge"                \
        --ca_organization_name      "Patroni Postgres Cluster" \
        --ca_common_name            "CA ${cluster_name}"       \
        --ca_not_valid_after        "3650"                     \
        --ca_path                   "${tmp}/root_ca.pem"       \
        --ca_key_path               "${tmp}/root_ca.key"       \
        ;


    ${eyaml} encrypt -l pg_root_crt -f ${tmp}/root_ca.pem
    ${eyaml} encrypt -l pg_root_key -f ${tmp}/root_ca.key

    rm -f ${tmp}/root_ca.pem ${tmp}/root_ca.key
}
/usr/bin/rmdir ${tmp}

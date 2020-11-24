#!/bin/bash
set -e
#
# should be safe to cut and past into a terminal from here
#

eyaml="/opt/puppetlabs/puppet/bin/eyaml"
tmp=`/usr/bin/mktemp -d`
{
    test -d $tmp || exit 1
    ssh_file=$(/usr/bin/basename `/usr/bin/mktemp -d`)
    /usr/bin/ssh-keygen -t rsa -b 4096 -f ${tmp}/${ssh_file}_rsa -N "" -C "patt::installer::$(date '+%s')"

    ${eyaml} encrypt -l installer_ssh_id_priv -f ${tmp}/${ssh_file}_rsa
    ${eyaml} encrypt -l installer_ssh_id_pub -f ${tmp}/${ssh_file}_rsa.pub

    rm -f ${tmp}/${ssh_file}_rsa ${tmp}/${ssh_file}_rsa.pub
}
/usr/bin/rmdir ${tmp}

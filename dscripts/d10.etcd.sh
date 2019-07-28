#!/bin/sh

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap 'echo "$0 FAILED on line $LINENO!" | tee $srcdir/$(basename $0).log' ERR
# Catch unitialized variables:
set -u
P1=${1:-1}

#
sudo yum install -y etcd

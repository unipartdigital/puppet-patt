#!/bin/bash
srcdir=$(cd $(dirname $0); pwd)

script="$1"
shift 1
args="$*"

echo ${srcdir}/$script
cat ${srcdir}/$script | su - postgres

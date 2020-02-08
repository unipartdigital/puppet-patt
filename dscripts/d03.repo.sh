#!/bin/bash

srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ;}" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f $0; }" EXIT

self=$(basename $0 .sh)

# Catch unitialized variables:
set -u

# arch | vendor | major
get_system_release () {
    query=$1
    if [ "x$query" == "xarch" ]; then uname -m; return $?; fi
    if [ -f /etc/redhat-release ]; then
        release=$(rpm -q --whatprovides /etc/redhat-release)
        case $query in
            'major')
                echo $release | rev | cut -d '-' -f 2 | rev | cut -d '.' -f1
                ;;
            'vendor')
                echo $release | rev |  cut -d '-' -f 4 | rev
                ;;
            *)
                echo "query not implemented: $query" 1>&2
                exit 1
        esac
    fi
}

logger () {
    message=${1:-"undef"}
    echo "${message}" 1>&2
}

add_repo () {
    repo_url=$*
    release_vendor=$(get_system_release "vendor")
    release_major=$(get_system_release "major")
    release_arch=$(get_system_release "arch")

    case "${release_vendor}" in
        'redhat' | 'centos')
            for r in ${repo_url[*]}; do
                if [ "${release_major}" -lt 8 ]; then
                    repo_name=$(echo "$r" | sed -e "s|https*://||" -e "s|[\.:/]|_|g" -e "s|\[|_|" -e "s|\]|_|" -e "s|_\+|_|g")
                    cat <<EOF > /etc/yum.repos.d/${repo_name}.repo
[{repo_name}]
name=created by $0 from ${r}
baseurl=${r}
enabled=1
gpgcheck=0
EOF
                else
                    dnf config-manager --nogpgcheck --add-repo ${r}
                fi
            done
            ;;
    esac
}

del_repo () {
    echo "not implemented" 1>&2
    exit 1
}

case "$1" in
    'add')
        shift 1
        add_repo "$@"
        ;;
    'del')
        shift 1
        del_repo "$@"
        ;;
    *)
        echo "not implemented: $1" 1>&2
        exit 1
        ;;
esac

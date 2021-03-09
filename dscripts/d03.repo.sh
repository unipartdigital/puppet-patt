#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!; rm -f $0 ; }" | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} ; rm -f $0 ; }" EXIT

self=$(basename $0 .sh)

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

case "${os_id}" in
    'debian' | 'ubuntu')
        export DEBIAN_FRONTEND=noninteractive
        ;;
esac

logger () {
    message=${1:-"undef"}
    echo "${message}" 1>&2
}

add_repo () {
    repo_url="$*"

    case "${os_id}" in
        'rhel' | 'centos' | 'fedora')
            # some images may not provide the config-manager plugin
            if [ "${os_major_version_id}" -ge 8 ]; then
                dnf config-manager --help > /dev/null 2>&1 || dnf install 'dnf-command(config-manager)' -y
            fi

            for r in ${repo_url[*]}; do
                if [ "x$r" == "x" ]; then
                    continue
                fi
                br=$(echo $(basename ${r}))
                if [ "$(echo ${br} | rev | cut -d '.' -f 1 | rev)" == "repo" ]; then
                    (cd /etc/yum.repos.d/
                     curl -f -k ${r} > /dev/null || continue
                     echo "curl -f -k ${r} > ${br}" 2>&1
                     curl -f -k ${r} > ${br}
                     if  [ -f ${br} ]; then
                         if grep -q "skip_if_unavailable" ${br} ; then
                             if ! grep -iq "skip_if_unavailable=true" ${br} ; then
                                 sed -i -e "s|skip_if_unavailable=.*|skip_if_unavailable=True|"
                             fi
                         else
                             echo "skip_if_unavailable=True" >> ${br}
                         fi
                     fi
                    )
                else
                    echo "curl -f -k ${r}" 1>&2
                    curl -f -k ${r} > /dev/null || continue
                    repo_name=$(echo "$r" | sed -e "s|https*://||" -e "s|[\.:/]|_|g" -e "s|\[|_|" -e "s|\]|_|" -e "s|_\+|_|g")
                    cat <<EOF > /etc/yum.repos.d/${repo_name}.repo
[${repo_name}]
name=created by $0 from ${r}
baseurl=${r}
enabled=1
skip_if_unavailable=True
gpgcheck=0
EOF
                fi
            done
            ;;
        'debian' | 'ubuntu')
            for r in ${repo_url[*]}; do
                if [ "x$r" == "x" ]; then
                    continue
                fi
                type=$(echo $r | cut -d'|' -f 1)
                link=$(echo $r | cut -d'|' -f 2)
                rele=$(echo $r | cut -d'|' -f 3- | sed -e "s/|/ /g")
                rele=${rele:-"main"}
                case ${type} in "deb" | "deb-src" ) : ;; *) continue;; esac
                curl -f -k ${link} > /dev/null || continue
                fname="$(echo ${r} | sha1sum).list"
                if [ ! -f "/etc/apt/sources.list.d/${fname}" ]; then
                    echo "${type} ${link} ${rele}" > /etc/apt/sources.list.d/${fname}
                fi
            done
            ;;
    esac
}

del_repo () {
    echo "not implemented" 1>&2
    exit 1
}

{
    flock -n 9 || exit 1

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
} 9> ${lock_file}

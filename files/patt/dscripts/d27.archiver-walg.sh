#!/bin/bash

lock_file=/tmp/$(basename $0 .sh).lock
srcdir=$(cd $(dirname $0); pwd)
# Exit the script on errors:
set -e
trap '{ echo "$0 FAILED on line $LINENO!" ; } | tee ${srcdir}/$(basename $0).log' ERR
# clean up on exit
trap "{ rm -f ${lock_file} || true ; rm -f $0 ; }" EXIT

# Catch unitialized variables:
set -u

. /etc/os-release
os_id="${ID}"
os_version_id="${VERSION_ID}"
os_major_version_id="$(echo ${VERSION_ID} | cut -d. -f1)"
os_arch="$(uname -m)"

walg_version () {
    prefix=/usr/local
    test -x ${prefix}/bin/wal-g && {
        for i in 1 2 3; do
            { ${prefix}/bin/wal-g --version | awk '{print $3}' && break ; } || sleep 1
        done
    }
}

pkg_init () {
    walg_release=${1:-"v0.2.19"}
    walg_url=${2:-""}
    walg_sha256=${3:-""}
    prefix=/usr/local
    walg_pkg="`basename ${walg_url}`"
    download_url="https://github.com/wal-g/wal-g/releases/download/${walg_release}/wal-g.linux-amd64.tar.gz"

    downloader=""
    wget --version > /dev/null 2>&1 && {
        downloader="wget -q -L"
    } || {
        curl --version > /dev/null 2>&1 && {
            downloader="curl -f -s -O -L"
        }
    }

    {
        test -x ${prefix}/bin/wal-g && \
            test "`${prefix}/bin/wal-g --version | awk '{print $3}'`" == "${walg_release}" > /dev/null 2>&1
    } || {
        cd $srcdir
        if [ -f "$srcdir/${walg_pkg}" ]; then
        # walg provided by sftp
            :
        else
            if [ "x${walg_url}" != "x" ]; then
                download_url=${walg_url}
            fi
            ${downloader} ${download_url}
        fi
        if [ "x${walg_sha256}" != "x" ]; then
            echo "sha256sum ${walg_sha256}: `sha256sum ${walg_pkg} | cut -d' ' -f1`"
            if test "`sha256sum ${walg_pkg} | cut -d' ' -f1`" == "${walg_sha256}" ; then
                tar xvf ${walg_pkg}
            else
                echo "error: sha256sum ${walg_pkg}" >&2
                exit 1
            fi
        else
            tar xvf ${walg_pkg}
        fi
        internal_walg=`tar tf ${walg_pkg}`
        test -f ./${internal_walg} && {
            test ! -f wal-g && {
                mv ./${internal_walg} ./wal-g
            }
        }
        chmod 755 ./wal-g
        test "`./wal-g --version | awk '{print $3}'`" == "${walg_release}" && {
            sudo install -o root -g root -m 755 ./wal-g ${prefix}/bin/wal-g
        }
        rm -f ${srcdir}/wal-g ${srcdir}/${walg_pkg}
    } > /dev/null

    for i in 1 2 3 4 5; do
        { ${prefix}/bin/wal-g --version && break ; } || sleep 1
    done
}

sh_json () {
    postgresql_version=${1}
    cluster_name=${2}
    archive_host=${3}
    archive_port=${4}
    prefix=${5}
    sh_identity=${6}
    sh_id_file=${7}
    sh_config_file=${8}
    user_name=${9:-"postgres"}
    comd=${10:-"tmpl2file.py"}
    tmpl=${11:-"walg-ssh.json"}
    pg_home=$(getent passwd postgres | cut -d':' -f 6)
    test "x${pg_home}" != "x" || { echo "pg_home not found"    >&2 ; exit 1 ; }
    test -d ${pg_home} || { echo "${pg_home} not directory"    >&2 ; exit 1 ; }
    test -f ${srcdir}/${comd} || { echo "script file not found"   >&2 ; exit 1 ; }
    test -f ${srcdir}/${tmpl} || { echo "template file not found" >&2 ; exit 1 ; }
    chown "${user_name}" "${srcdir}"
    chown "${user_name}" "${srcdir}/${comd}"

    # clean up opposite entry with the same priority
    prev_base="$(echo `basename ${sh_config_file}` | cut -d'-' -f 1-2)"
    test -f ${pg_home}/${prev_base}-s3.json && rm -f ${pg_home}/${prev_base}-s3.json

    cat <<EOF | su - ${user_name}
python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl} -o ${pg_home}/`basename ${sh_config_file}` \
--skip '//'                                                                               \
--dictionary_key_val "walg_ssh_prefix=${archive_host}"        \
--dictionary_key_val "prefix=${prefix}"                       \
--dictionary_key_val "ssh_port=${archive_port}"               \
--dictionary_key_val "ssh_username=${sh_identity}"            \
--dictionary_key_val "ssh_id_file=${sh_id_file}"              \
--dictionary_key_val "postgres_version=${postgresql_version}" \
--chmod 640
EOF
}

s3_json () {
    postgresql_version=${1}
    cluster_name=${2}
    endpoint=${3}
    prefix=${4}
    region=${5}
    profile=${6}
    force_path_style=${7}
    s3_config_file=${8}
    user_name=${9:-"postgres"}
    comd=${10:-"tmpl2file.py"}
    tmpl=${11:-"walg-s3.json"}
    pg_home=$(getent passwd postgres | cut -d':' -f 6)
    test "x${pg_home}" != "x" || { echo "pg_home not found"    >&2 ; exit 1 ; }
    test -d ${pg_home} || { echo "${pg_home} not directory"    >&2 ; exit 1 ; }
    test -f ${srcdir}/${comd} || { echo "script file not found"   >&2 ; exit 1 ; }
    test -f ${srcdir}/${tmpl} || { echo "template file not found" >&2 ; exit 1 ; }
    chown "${user_name}" "${srcdir}"
    chown "${user_name}" "${srcdir}/${comd}"

    # clean up opposite entry with the same priority
    prev_base="$(echo `basename ${sh_config_file}` | cut -d'-' -f 1-2)"
    test -f ${pg_home}/${prev_base}-sh.json && rm -f ${pg_home}/${prev_base}-sh.json

    cat <<EOF | su - ${user_name}
python3 ${srcdir}/${comd} -t ${srcdir}/${tmpl} -o ${pg_home}/`basename ${s3_config_file}` \
--skip '//'                                                                               \
--dictionary_key_val "aws_endpoint=${endpoint}"                                           \
--dictionary_key_val "prefix=${prefix}"                                                   \
--dictionary_key_val "aws_region=${region}"                                               \
--dictionary_key_val "aws_profile=${profile}"                                             \
--dictionary_key_val "aws_s3_force_path_style=${force_path_style}"                        \
--dictionary_key_val "postgres_version=${postgresql_version}"                             \
--chmod 640
EOF
}

backup_walg_service () {
    command=$1
    postgres_version=$2
    backup_walg=$3

    test -f /etc/systemd/system/backup_walg-${postgres_version}.service || {
        echo "systemd file not found: /etc/systemd/system/backup_walg-${postgres_version}.service" 1>&2
        exit 1
    }
    test -f $srcdir/backup_walg.py && {
        test -f ${backup_walg} || {
            mkdir -m 755 -p `dirname ${backup_walg}`
            install -v -m 644 $srcdir/backup_walg.py `dirname ${backup_walg}`
        }
    }

    case "${command}" in
        'enable')
            /usr/bin/systemctl enable backup_walg-${postgres_version}.service
            /usr/bin/systemctl -q is-active backup_walg-${postgres_version}.service || {
                /usr/bin/systemctl --no-block start backup_walg-${postgres_version}.service
            }
            ;;
        'disable')
            /usr/bin/systemctl enable backup_walg-${postgres_version}.service
            ;;
        *)
            echo "${command} not implemented" 1>&2
            exit 1
            ;;
    esac
}

touch ${lock_file} 2> /dev/null || true
case "${1:-''}" in
    # get wal-g version on postgres peer
    'walg_version')
        shift 1
        { flock -w 10 8 || exit 1
          walg_version "$@"
        } 8< ${lock_file}
        ;;
    # must be run on each postgres peer
    'pkg_init')
        shift 1
        { flock -w 10 8 || exit 1
          pkg_init "$@"
        } 8< ${lock_file}
        ;;
    # must be run on each postgres peer
    'sh_json')
        shift 1
        { flock -w 10 8 || exit 1
          sh_json "$@"
        } 8< ${lock_file}
        ;;
    's3_json')
        shift 1
        { flock -w 10 8 || exit 1
          s3_json "$@"
        } 8< ${lock_file}
        ;;
    'backup_walg_service')
        shift 1
        { flock -w 10 8 || exit 1
          backup_walg_service "$@"
        } 8< ${lock_file}
        ;;
    *)
        {
            cat <<EOF
usage:
 $0 pkg_init <wal-g release version> ['v0.2.19']
 $0 sh_json
 $0 s3_json
 $0 backup_walg_service enable <postgres_version> | disable <postgres_version>
EOF
            exit 1
        } >&2
        ;;
esac

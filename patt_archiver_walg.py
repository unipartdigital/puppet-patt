#!/usr/bin/env python3

import logging
import os
import tempfile
# from pathlib import Path
# import shutil
# from string import Template
# import time
import patt
from patt_archiver import Archiver

logger = logging.getLogger('patt_archiver-walg')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_archiver-walg', result=result, hide_stdout=hide_stdout)

valid_cluster_char="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

class ArchiverWalg(Archiver):
    def __init__(self):
        super().__init__()
        self.archiver_type = 'walg'

    """
    install walg on each nodes
    """
    def package_init(self, nodes, version=None, url=None, sha256=None):
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)

        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh",
                                   args=['walg_version'], sudo=False)
        ok = all(x == version for x in [n.out for n in result])
        if ok: return True

        if url is None: url = ""
        if sha256 is None: sha256 = ""
        payload=None
        walg_local_pkg="./pkg/{}".format(os.path.basename (url))
        if os.path.isfile(walg_local_pkg):
            payload=walg_local_pkg

        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh", payload=payload,
                                   args=['pkg_init'] + [version] + [url] + [sha256],
                                   sudo=False)
        log_results (result)
        return all(x == True for x in [bool(n.out) for n in result])


    """
    preapare the archive server for chroot sftp
    """
    def _archiving_standalone_sftpd(self, cluster_name, nodes, listen_addr="::0", listen_port=2222):
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)

        tmpl="./config/sftpd.service"
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/systemd/system/{}".format (os.path.basename (tmpl))] +
                                   ['--dictionary_key_val'] + ["listen_port={}".format(listen_port)] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        assert not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

        tmpl="./config/sftpd_config"
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/ssh/{}".format (os.path.basename (tmpl))] +
                                   ['--dictionary_key_val'] +
                                   ["listen_address=[{}]:{}".format(listen_addr, listen_port)] +
                                   ['--dictionary-rhel'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-fedora'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-centos'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-debian'] +
                                   ["subsystem=/usr/lib/openssh/sftp-server"] +
                                   ['--dictionary-ubuntu'] +
                                   ["subsystem=/usr/lib/openssh/sftp-server"] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        assert not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    """
    preapare the archive server for chroot sftp
    """
    def archiving_add(self, cluster_name, nodes, port):
        cluster_name="".join(
            ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
             else i for i in cluster_name])
        assert cluster_name[0] in valid_cluster_char
        patt.host_id(nodes)
        patt.check_dup_id (nodes)
        if not port == 22:
            assert port > 1024, "error: restricted to unreserved or default ssh port only"
            self._archiving_standalone_sftpd(cluster_name=cluster_name, nodes=nodes,
                                             listen_addr="::0", listen_port=port)

        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh",
                                   args=['ssh_archiving_add'] + [cluster_name] + [port], sudo=True)
        log_results (result)
        return all(x == True for x in [bool(n.out == "drwx--x--x {}.{} {}".format (
            cluster_name, "walg", "/var/lib/walg/" + cluster_name)) for n in result])

    """
    s3 json config
    """
    def s3_config(self, postgres_version, cluster_name, nodes, archive_store):
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)
        comd="./dscripts/tmpl2file.py"
        tmpl="./config/walg-s3.json"
        count=0
        isok = []
        logger.debug ("walg_s3_json: {}".format(archive_store))
        for c in archive_store:
            logger.debug ("walg_s3_json: {}".format(c))
            if 'method' in c and c['method'] == 's3':
                endpoint=c['endpoint']
                assert endpoint, "missing endpoint definition"
                prefix=c['prefix']
                assert prefix, "missing prefix definition"
                if not (prefix.endswith(cluster_name) or prefix.endswith(cluster_name + '/')):
                    prefix=prefix + '/' + cluster_name
                    region=c['region']
                    assert region, "missing region definition"
                if 'force_path_style' in c:
                    force_path_style=c['force_path_style']
                else:
                    force_path_style='true'
                if 'profile' in c:
                    profile=c['profile']
                else:
                    profile=''

                if count == 0:
                    s3_config_file=".walg.json"
                else:
                    s3_config_file="walg-{}-s3.json".format(count)

                result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh",
                                           payload=[comd, tmpl],
                                           args=['s3_json'] + [postgres_version] + [cluster_name] +
                                           [endpoint] + [prefix] + [region] + [profile] +
                                           [force_path_style] + [s3_config_file] +
                                           ['postgres'] + [os.path.basename (comd)] +
                                           [os.path.basename (tmpl)], sudo=True)
                isok.append(not any(x == True for x in [bool(n.error) for n in result if
                                                        hasattr(n, 'error')]))
                log_results (result)
            count += 1
        return all(x == True for x in isok)

    """
    sh json config
    """
    def sh_config(self, postgres_version, cluster_name, nodes, archive_store):
        cluster_name="".join(
            ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
             else i for i in cluster_name])
        assert cluster_name[0] in valid_cluster_char
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)
        comd="./dscripts/tmpl2file.py"
        tmpl="./config/walg-sh.json"
        count=0
        isok = []
        logger.debug ("walg_sh_json: {}".format(archive_store))
        for c in archive_store:
            logger.debug ("walg_sh_json: {}".format(c))
            if 'method' in c and c['method'] == 'sh':
                host=c['host']
                assert host, "missing ssh host definition"
                if 'prefix' in c:
                    prefix=c['prefix']
                if not prefix:
                    prefix=cluster_name
                if not (prefix.endswith(cluster_name) or prefix.endswith(cluster_name + '/')):
                    prefix=prefix + '/' + cluster_name
                (login, hostname, port) = patt.ipv6_nri_split (host)
                if not login:
                    login = cluster_name
                if not port:
                    port = 22
                identity_file=None
                if 'identity_file' in c:
                    identity_file=c['identity_file']
                if not identity_file:
                    identity_file="walg_rsa"

                if count == 0:
                    sh_config_file=".walg.json"
                else:
                    sh_config_file="walg-{}-sh.json".format(count)

                result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh", payload=[comd, tmpl],
                                           args=['sh_json'] + [postgres_version] + [cluster_name] +
                                           [hostname] + [port] + [prefix] + [login] +
                                           [identity_file] + [sh_config_file] +
                                           ['postgres'] + [os.path.basename (comd)] +
                                           [os.path.basename (tmpl)], sudo=True)
                isok.append(not any(x == True for x in [bool(n.error) for n in result if
                                                        hasattr(n, 'error')]))
                log_results (result)
            count += 1
        return all(x == True for x in isok)

    """
    configure the systemd schedule backup service (named after the postgres version)
    """
    def backup_service_setup(self, nodes, postgres_version,
                             tmpl="./config/backup_walg.service"):
        logger.info ("walg_s3_backup_service processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        comd="./dscripts/tmpl2file.py"
        pg_data_rhl_fam="/var/lib/pgsql/{}/data".format(postgres_version)
        pg_data_deb_fam="/var/lib/postgresql/{}/data".format(postgres_version)
        systemd_service="{}-{}.service".format(os.path.basename (tmpl).rpartition('.')[0], postgres_version)
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/systemd/system/{}".format (systemd_service)] +
                                   ['--dictionary_key_val'] +
                                   ["backup_walg={}".format(
                                       "/usr/local/libexec/patt/dscripts/backup_walg.py")] +
                                   ['--dictionary_key_val'] +
                                   ["cluster_config={}".format("/usr/local/etc/cluster_config.yaml")] +
                                   ['--dictionary-rhel'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-fedora'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-centos'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-debian'] +
                                   ["pg_data={}".format(pg_data_deb_fam)] +
                                   ['--dictionary-ubuntu'] +
                                   ["pg_data={}".format(pg_data_deb_fam)] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    def backup_service_command(self, nodes, command, postgres_version):
        logger.info ("walg_s3_backup_service processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-walg.sh",
                                   payload="dscripts/backup_walg.py",
                                   args=['backup_walg_service'] + [command] + [postgres_version] +
                                   ["/usr/local/libexec/patt/dscripts/backup_walg.py"],
                                   sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

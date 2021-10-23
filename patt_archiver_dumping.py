#!/usr/bin/env python3

import logging
import os
import tempfile
from pathlib import Path
import shutil
from string import Template
import time
import patt
from patt_archiver import Archiver

logger = logging.getLogger('patt_archiver-dumping')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_archiver-dumping', result=result, hide_stdout=hide_stdout)

valid_cluster_char="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

class ArchiverDumping(Archiver):
    def __init__(self):
        super().__init__()
        self.archiver_type = 'dumping'

    """
    check only if pg_dump is available, it must as it is part of core package
    if is only used to get the same signature as others Archiver class
    """
    def package_init(self, nodes, version=None, url=None, sha256=None):
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-dumping.sh",
                                   args=['pg_dump_version'], sudo=False)
        log_results (result)
        if version:
            return all(x == version for x in [bool(n.out) for n in result])
        else:
            return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    """
    preapare the archive server for ssh
    """
    def archiving_add(self, cluster_name, nodes, port):
        pass

    """
    s3 json config
    """
    def s3_config(self, postgres_version, cluster_name, nodes, archive_store):
        pass

    """
    sh json config
    """
    def sh_config(self, postgres_version, cluster_name, nodes, archive_store):
        pass

    """
    install in /usr/local/bin/backup_dumping.py
    """
    def backup_service_install(self, nodes, command="./dscripts/backup_dumping.py"):
        logger.info ("walg_backup_service_install processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        comd="./dscripts/tmpl2file.py"
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=command,
                                   args=['-t'] + [os.path.basename (command)] +
                                   ['-o'] + ["/usr/local/bin/{}".format (os.path.basename (command))] +
                                   ['--chmod'] + ['755'],
                                   sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


    """
    configure the systemd onshot backup service (named after the postgres version)
    """
    def backup_service_setup(self, nodes, postgres_version,
                             dumping_root_dir="",
                             tmpl="./config/backup_dumping.service"):
        logger.info ("dumping_backup_service processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        comd="./dscripts/tmpl2file.py"
        pg_data_rhl_fam="/var/lib/pgsql/{}/data".format(postgres_version)
        pg_data_deb_fam="/var/lib/postgresql/{}/data".format(postgres_version)
        pg_path_rhl_fam="/usr/pgsql-{}/bin".format(postgres_version)
        pg_path_deb_fam="/usr/lib/postgresql/{}/bin".format(postgres_version)
        systemd_service="{}-{}.service".format(os.path.basename (tmpl).rpartition('.')[0], postgres_version)
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/systemd/system/{}".format (systemd_service)] +
                                   ['--dictionary_key_val'] +
                                   ["backup_dumping={}".format(
                                       "/usr/local/bin/backup_dumping.py")] +
                                   ['--dictionary_key_val'] +
                                   ["cluster_config={}".format("/usr/local/etc/cluster_config.yaml")] +
                                   ['--dictionary_key_val'] +
                                   ["dumping_root_dir={}".format(dumping_root_dir)] +
                                   ['--dictionary-rhel'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-rhel'] +
                                   ["pg_path={}".format(pg_path_rhl_fam)] +
                                   ['--dictionary-fedora'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-fedora'] +
                                   ["pg_path={}".format(pg_path_rhl_fam)] +
                                   ['--dictionary-centos'] +
                                   ["pg_data={}".format(pg_data_rhl_fam)] +
                                   ['--dictionary-centos'] +
                                   ["pg_path={}".format(pg_path_rhl_fam)] +
                                   ['--dictionary-debian'] +
                                   ["pg_data={}".format(pg_data_deb_fam)] +
                                   ['--dictionary-debian'] +
                                   ["pg_path={}".format(pg_path_deb_fam)] +
                                   ['--dictionary-ubuntu'] +
                                   ["pg_data={}".format(pg_data_deb_fam)] +
                                   ['--dictionary-ubuntu'] +
                                   ["pg_path={}".format(pg_path_deb_fam)] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    def backup_service_command(self, nodes, command, postgres_version, calendar_events=[],
                               tmpl="./config/backup_dumping.timer"):
        logger.info ("dumping_backup_service processing {}".format ([n.hostname for n in nodes]))
        if not calendar_events: return True
        all_result=[]
        patt.host_id(nodes)
        comd="./dscripts/tmpl2file.py"
        systemd_service="{}-{}.timer".format(os.path.basename (tmpl).rpartition('.')[0], postgres_version)
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/systemd/system/{}".format (systemd_service)] +
                                   ['--dictionary_key_val'] +
                                   ['calendar_events="{}"'.format('\n'.join(calendar_events))] +
                                   ['--chmod'] + ['644'] +
                                   ['--touch'] + ['/var/tmp/systemd-reload'],
                                   sudo=True)
        log_results (result)
        all_result.append(not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')]))
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-dumping.sh",
                                   args=['systemd_service', command, systemd_service], sudo=True)
        all_result.append(not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')]))
        log_results (result)
        return all(all_result)

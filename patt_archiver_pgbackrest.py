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

logger = logging.getLogger('patt_archiver-pgbackrest')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_archiver-pgbackrest', result=result, hide_stdout=hide_stdout)

valid_cluster_char="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

class ArchiverPgbackrest(Archiver):
    def __init__(self):
        super().__init__()
        self.archiver_type = 'pgbackrest'

        """
        install pgbackrest packages on each nodes
        use vendor package, parameters are used only to get the same signature as others Archiver class
        """
    def package_init(self, nodes, version=None, url=None, sha256=None):
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)
        if version:
            result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-pgbackrest.sh",
                                       args=['pgbackrest_version'], sudo=False)
            ok = all(x == version for x in [bool(n.out) for n in result])
            if ok: return True

        payload=[]
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver-pgbackrest.sh",
                                   payload=payload,
                                   args=['pkg_init'], sudo=True)
        log_results (result)
        return all(x == True for x in [bool(n.out) for n in result])

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
    configure the systemd schedule backup service (named after the postgres version)
    """
    def backup_service_setup(self, nodes, postgres_version,
                             tmpl="./config/backup_pgbackrest.service"):
        pass

    def backup_service_command(self, nodes, command, postgres_version):
        pass

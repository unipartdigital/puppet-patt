#!/usr/bin/env python3

import patt
import logging
import os
import tempfile
from pathlib import Path
import shutil
from string import Template
import time

logger = logging.getLogger('patt_health')

def log_results(result, hide_stdout=False):
    error_count=0
    for r in result:
        logger.debug ("hostname: {}".format(r.hostname))
        if not hide_stdout:
            logger.debug ("stdout: {}".format (r.out))
        if r.error is None:
            pass
        elif r.error.strip().startswith("Error: Nothing to do"):
            pass
        else:
            error_count += 1
            logger.error ("stderr: {}".format (r.error))
    return error_count

"""
install httpd wsgi packages and dep on each postgres nodes
"""
def health_init(nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    payload=None
    result = patt.exec_script (nodes=nodes, src="./dscripts/d50.health.sh", payload=payload,
                               args=['init'],
                               sudo=True)
    log_results (result)
    return all(x == False for x in [bool(n.error) for n in result])

"""
configure minimal (low consumption) httpd wsgi
"""
def health_configure(nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    payload=['dscripts/tmpl2file.py',
             'config/monitoring-httpd.conf',
             'monitoring/patt_monitoring.py',
             'monitoring/cluster-health.wsgi',
             'config/cluster_health.te']
    result = patt.exec_script (nodes=nodes, src="./dscripts/d50.health.sh", payload=payload,
                               args=['configure'] +
                               ['patt_health'] +
                               [os.path.basename(payload[0])] +
                               [os.path.basename(payload[1])] +
                               [os.path.basename(payload[2])] +
                               [os.path.basename(payload[3])] +
                               [os.path.basename(payload[4])],
                               sudo=True)
    log_results (result)
    return all(x == False for x in [bool(n.error) for n in result])

def health_enable(nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    payload=None
    result = patt.exec_script (nodes=nodes, src="./dscripts/d50.health.sh", payload=payload,
                               args=['enable'] +
                               ['patt_health'],
                               sudo=True)
    log_results (result)
    return all(x == False for x in [bool(n.error) for n in result])
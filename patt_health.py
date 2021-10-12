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
    patt.log_results(logger='patt_health', result=result, hide_stdout=hide_stdout)

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
def health_configure(nodes, cluster_config_path=None):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    payload=['dscripts/tmpl2file.py',               # 0
             'config/monitoring-httpd.conf',        # 1
             'config/df-recorder.service',          # 2
             'monitoring/patt_monitoring.py',       # 3
             'monitoring/df_recorder.py',           # 4
             'monitoring/cluster-health.wsgi',      # 5
             'monitoring/cluster-health-mini.wsgi', # 6
             'monitoring/df_plot.wsgi',             # 7
             'monitoring/df_monitor.wsgi',          # 8
             'config/cluster_health.te',            # 9
             'config/monitoring-httpd-00.conf.apt', # 10
             'config/monitoring-httpd-00.conf.dnf', # 11
             'monitoring/xhtml.py',                 # 12
             cluster_config_path,                   # 13
             ]

    result = patt.exec_script (nodes=nodes, src="./dscripts/d50.health.sh", payload=payload,
                               args=['configure'] +
                               ['patt_health'] +
                               [os.path.basename(payload[0])] +
                               [os.path.basename(payload[1])] +
                               [os.path.basename(payload[2])] +
                               [os.path.basename(payload[3])] +
                               [os.path.basename(payload[4])] +
                               [os.path.basename(payload[5])] +
                               [os.path.basename(payload[6])] +
                               [os.path.basename(payload[7])] +
                               [os.path.basename(payload[8])] +
                               [os.path.basename(payload[9])] +
                               [os.path.basename(payload[13])],
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

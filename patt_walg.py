#!/usr/bin/env python3

import patt
import logging
import os
import tempfile
from pathlib import Path
import shutil
from string import Template
import time

logger = logging.getLogger('patt_walg')

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
install postgres packages and dep on each nodes
"""
def walg_init(walg_version, nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                args=['init'] + [walg_version], sudo=False)
    log_results (result)
    return all(x == True for x in [bool(n.out) for n in result])

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

"""
install util packages to allow sftp access
"""
def walg_ssh_archiving_init(nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                args=['ssh_archiving_init'], sudo=True)
    log_results (result)
    #return all(x == True for x in [bool(n.out) for n in result])

"""
gen a walg ssh key on each peer and return all the public key (on success)
"""
def walg_ssh_gen(cluster_name, nodes, postgres_user='postgres'):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_archive_keygen'] + [cluster_name] + [postgres_user],
                               sudo=True, log_call=True)
    log_results (result, hide_stdout=True)
    assert all(x == True for x in [bool(n.out) for n in result])
    return [n.out for n in result]

"""
gen an initial known_hosts or check if valid
"""
def walg_ssh_known_hosts(cluster_name, nodes, archiving_server):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_known_hosts'] + [cluster_name] +
                               [archiving_server[0].hostname],
                               sudo=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
add the public keys into the archive server
"""
def walg_authorize_keys(cluster_name, nodes, keys=[]):
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)
    with tempfile.NamedTemporaryFile(mode='w+', encoding='ascii') as tmpl_file:
        for k in keys + [""]:
            print("{}".format (k), file=tmpl_file)
        tmpl_file.flush()
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                   payload=tmpl_file.name,
                                   args=['ssh_authorize_keys'] + [cluster_name] +
                                   [os.path.basename (tmpl_file.name)], sudo=True)
        log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


"""
preapare the archive server for chroot sftp
"""
def walg_archiving_add(cluster_name, nodes):
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_archiving_add'] + [cluster_name], sudo=True)
    log_results (result)
    return all(x == True for x in [bool(n.out == "drwx--x--x {}.{} {}".format (
        cluster_name, "walg", "/var/lib/walg/" + cluster_name)) for n in result])

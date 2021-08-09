#!/usr/bin/env python3

import patt
import os
import logging

logger = logging.getLogger('patt_haproxy')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_haproxy', result=result, hide_stdout=hide_stdout)

"""
install haproxy packages and dep on each nodes
"""
def haproxy_init(nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d40.haproxy.sh",
                                args=['init'], sudo=True)
    log_results (result)


"""
enable haproxy systemd service
if /etc/haproxy/haproxy.cfg check is ok
 reload the configuration file if haproxy already running
 start and enable haproxy.service otherwise
"""
def haproxy_enable(nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d40.haproxy.sh",
                                args=['enable'], sudo=True)
    log_results (result)

def haproxy_configure(cluster_name, template_src, nodes, postgres_nodes, config_file_target):
    haproxy_init (nodes)
    result = patt.exec_script (nodes=nodes, src="./dscripts/haproxy_config.py", payload=template_src,
                                args=['-c'] + [cluster_name] + ['-t'] + [os.path.basename (template_src)] +
                                ['-d'] + [config_file_target] +
                                ['-p'] + [p.hostname for p in postgres_nodes] +
                                ['-x'] + [x.hostname for x in nodes],
                                sudo=True)
    log_results (result)
    haproxy_enable (nodes)

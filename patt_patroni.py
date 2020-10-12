#!/usr/bin/env python3

import patt
import os
import logging
import random
import json
import ast
import tempfile
import yaml

logger = logging.getLogger('patt_patroni')

def log_results(result):
    error_count=0
    for r in result:
        logger.debug ("hostname: {}".format(r.hostname))
        logger.debug ("stdout: {}".format (r.out))
        if r.error is None:
            pass
        elif r.error.strip().startswith("Error: Nothing to do"):
            pass
        else:
            error_count += 1
            logger.error ("stderr syst: {}".format (r.error))
    return error_count

"""
install patroni packages and dep on each nodes
"""
def patroni_init(postgres_version, patroni_version, nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d30.patroni.sh",
                                args=['init'] + [postgres_version] + [patroni_version], sudo=True)
    log_results (result)

"""
enable patroni systemd service
"""
def patroni_enable(postgres_version, patroni_version, nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d30.patroni.sh",
                                args=['enable'] + [postgres_version] + [patroni_version], sudo=True)
    log_results (result)

    random_node = [random.choice(nodes)]
    result = patt.exec_script (nodes=random_node, src="./dscripts/d30.patroni.sh",
                                args=['check'], sudo=True)
    for r in result:
        logger.warn ("hostname: {}".format(r.hostname))
        return ("\n{}".format (r.out))
        logger.warn ("error: {}".format (r.error))

def patroni_configure(postgres_version, cluster_name, template_src, nodes, etcd_peers,
                      config_file_target, sysuser_pass, postgres_parameters):
    tmpl=""
    with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8') as tmpl_file:
        if os.path.isfile(template_src):
            with open(template_src, 'r') as p:
                try:
                    tmpl=yaml.safe_load(p)
                except yaml.YAMLError as e:
                    print(str(e), file=sys.stderr)
                    raise
                except:
                    raise
            if postgres_parameters:
                for p in postgres_parameters:
                    key,val = p.split ('=')
                    tmpl['postgresql']['parameters'][key.strip()] = val.strip()
            print(yaml.dump(tmpl, default_flow_style=False), file=tmpl_file)
            tmpl_file.flush()

        result = patt.exec_script (nodes=nodes, src="./dscripts/patroni_config.py", payload=tmpl_file.name,
                                    args=['-c'] + [cluster_name] + ['-t'] +
                                    [os.path.basename (tmpl_file.name)] +
                                    ['-d'] + [config_file_target] +
                                    ['-p'] + [n.hostname for n in nodes] +
                                    ['-e'] + [n.hostname for n in etcd_peers] +
                                    ['-s'] + ['"' + str(sysuser_pass) + '"'],
                                    sudo=True,
                                    log_call=False)
        log_results (result)


def floating_ip_init(nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d25.floating_ip.sh",
                                args=['init'], sudo=True, timeout=1440)
    log_results (result)

def floating_ip_build(nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d25.floating_ip.sh", payload="./ip_takeover.py",
                                args=['build'], sudo=False)
    log_results (result)

def floating_ip_enable(nodes, floating_ips):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d25.floating_ip.sh",
                                args=['enable', " ".join(floating_ips)], sudo=True)
    log_results (result)

"""
get the cluster info from the nodes list (first try the first nodes and next until success)
"""
def get_cluster_info(nodes):
    for n in nodes:
        try:
            result = patt.exec_script (nodes=[n], src="./dscripts/patroni_info.py",
                                        args=['-i', 'cluster'], sudo=False)
        except:
            continue
        else:
            for r in result:
                try:
                    c = json.loads (json.dumps(r.out.strip()))
                except:
                    continue
                else:
                    return dict(ast.literal_eval(c))
    return {}

def get_sys_users (postgres_peers, patroni_config='/var/lib/pgsql/patroni.yaml'):
    cluster_info = get_cluster_info(nodes=postgres_peers)
    host=''
    if 'members' in cluster_info:
        for m in cluster_info['members']:
            if 'role' in m and ( m['role'] == 'leader' or m['role'] == 'sync_standby'):
                host = m['host']
                if m['state'] == 'running': break
    p = [x for x in postgres_peers if x.hostname == host or host in x.ip_aliases]
    for n in p:
        try:
            result = patt.exec_script (nodes=[n], src="./dscripts/patroni_info.py", args=['-i', 'sys_user'],
                                        sudo=True, log_call=False)
        except:
            continue
        else:
            for r in result:
                try:
                    c = json.loads (json.dumps(r.out.strip()))
                except:
                    continue
                else:
                    return dict(ast.literal_eval(c))
    return {}

def get_leader (postgres_peers):
    cluster_info = get_cluster_info(nodes=postgres_peers)
    host=''
    if 'members' in cluster_info:
        for m in cluster_info['members']:
            if 'role' in m and m['role'] == 'leader':
                host = m['host']
                if m['state'] == 'running':
                    p = [x for x in postgres_peers if x.hostname == host or host in x.ip_aliases]
                    return p

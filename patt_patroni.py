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

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_patroni', result=result, hide_stdout=hide_stdout)

"""
take a list of {'database': '', 'user': ''}
"""
def cert_pg_hba_list (db_user=[], key_db='database', key_user='user', key_cert='cert'):
    default_pg_hba_list = [
        'local    all         all                   ident',
        'host     all         all         ::/0      scram-sha-256',
        'host     all         all         0.0.0.0/0 scram-sha-256',
        'host     replication replication ::/0      scram-sha-256',
        'host     replication replication 0.0.0.0/0 scram-sha-256'
    ]
    result = ["# TYPE   DATABASE   USER   ADDRESS   METHOD"]
    db_user = db_user if db_user else []
    for i in db_user:
        if key_db not in i: continue
        if key_user not in i: continue
        if key_cert not in i: continue
        if not i[key_db] or not i[key_user]: continue
        if not (i[key_cert] == "true" or i[key_cert] == True): continue
        result.append ("hostssl  {}          {}    ::/0      cert".format (i[key_db], i[key_user]))
        result.append ("hostssl  {}          {}    0.0.0.0/0 cert".format (i[key_db], i[key_user]))
    return result + default_pg_hba_list


"""
install patroni packages and dep on each nodes
"""
def patroni_init(postgres_version, patroni_version, nodes, dcs="etcd"):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    payload=['config/patroni.te','dscripts/tmpl2file.py', 'config/postgresql-patroni.service.tmpl']
    result = patt.exec_script (nodes=nodes, src="./dscripts/d30.patroni.sh", payload=payload,
                               args=['init'] + [postgres_version] + [patroni_version] +
                               ['patroni.te'] + ['postgresql-patroni.service.tmpl'] + [dcs],
                               sudo=True)
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

def patroni_configure(postgres_version, cluster_name, template_src, nodes,
                      config_file_target, sysuser_pass, postgres_parameters,
                      pg_hba_list=cert_pg_hba_list(), user=None, enable_pg_temp=False,
                      etcd_peers=[], raft_peers=[], dcs_type='etcd'):
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
                if enable_pg_temp:
                    if 'temp_tablespaces' in tmpl['postgresql']['parameters']:
                        pass
                    else:
                        tmpl['postgresql']['parameters']['temp_tablespaces'] = 'pgsql_temp'
            if pg_hba_list:
                tmpl['postgresql']['pg_hba'] = pg_hba_list
            print(yaml.dump(tmpl, default_flow_style=False), file=tmpl_file)
            tmpl_file.flush()

        opt_args=[]
        opt_args += ['-e'] + [n.hostname for n in etcd_peers] if etcd_peers else ['-e', []]
        opt_args += ['-r'] + [n.hostname for n in raft_peers] if raft_peers else ['-r', []]
        result = patt.exec_script (nodes=nodes, src="./dscripts/patroni_config.py", payload=tmpl_file.name,
                                   args=['PatroniConfig'] +
                                   ['-c'] + [cluster_name] + ['-t'] +
                                   [os.path.basename (tmpl_file.name)] +
                                   ['-d'] + [config_file_target] +
                                   ['-u'] + [user] +
                                   ['-v'] + [postgres_version] +
                                   ['-p'] + [n.hostname for n in nodes] +
                                   opt_args +
                                   ['-s'] + ['"' + str(sysuser_pass) + '"'] +
                                   ['--dcs_type'] + [dcs_type] + ['--debug'],
                                   sudo=True,
                                   log_call=False)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

def floating_ip_init(nodes, ip_takeover_version="0.92"):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d25.floating_ip.sh",
                                args=['init'] + [ip_takeover_version], sudo=True, timeout=1440)
    log_results (result)

def floating_ip_build(nodes, ip_takeover_version="0.92"):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d25.floating_ip.sh",
                               payload=["./ip_takeover.py", "./ip_takeover.make"],
                               args=['build'] + [ip_takeover_version], sudo=False)
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

"""
add only the ['raft'] config elements. to be used with raft only node.
"""
def patroni_raft_controller_configure(cluster_name, nodes, config_file_target, user=None, raft_peers=[]):
    result = patt.exec_script (nodes=nodes, src="./dscripts/patroni_config.py", payload=[],
                               args=['RaftConfig'] +
                               ['-c'] + [cluster_name] +
                               ['-d'] + [config_file_target] +
                               ['-u'] + [user] +
                               ['-p'] + [n.hostname for n in nodes] +
                               ['-r'] + [n.hostname for n in raft_peers] +
                               ['--debug'],
                               sudo=True,
                               log_call=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

def disable_auto_failover (postgres_version, postgres_peers):
    for p in postgres_peers:
        try:
            result = patt.exec_script (nodes=[p], src="dscripts/d30.patroni.sh",
                                       args=['disable_auto_failover'] +  [postgres_version], sudo=True)
            if any(x == True for x in [bool(n.error.strip() == 'Error: Cluster is already paused') for n in result if hasattr(n,'error')]):
                logger.warning ("Cluster is already paused")
                return True
            elif any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')]):
                logger.error ([n.error.strip() for n in result if hasattr(n,'error')])
                continue
            else:
                log_results (result)
                return True
        except Exception:
            continue
    return False

def enable_auto_failover (postgres_version, postgres_peers):
    for p in postgres_peers:
        try:
            result = patt.exec_script (nodes=[p], src="dscripts/d30.patroni.sh",
                                       args=['enable_auto_failover'] +  [postgres_version], sudo=True)
            if any(x == True for x in [bool(n.error.strip() == 'Error: Cluster is not paused') for n in result if hasattr(n,'error')]):
                logger.warning ("Cluster is not paused")
                return True
            elif any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')]):
                continue
            else:
                log_results (result)
                return True
        except Exception:
            continue
    return False

"""
raft only node init
"""
def patroni_raft_init (patroni_version, nodes, data_dir="/var/lib/raft", user="raft"):
    payload=[]
    result = patt.exec_script (nodes=nodes, src="./dscripts/d12.raft_controller.sh", payload=payload,
                               args=['init'] +
                               [patroni_version] + [data_dir] + [user],
                               sudo=True,
                               log_call=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
raft only node configure
"""
def patroni_raft_configure (nodes, user="raft"):
    payload=['dscripts/tmpl2file.py', 'config/patroni_raft_controller.service.tmpl', 'config/patroni_raft.te']
    result = patt.exec_script (nodes=nodes, src="./dscripts/d12.raft_controller.sh", payload=payload,
                               args=['configure'] +
                               ['patroni_raft_controller.service.tmpl'] + [user] + ['patroni_raft.te'],
                               sudo=True,
                               log_call=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
raft only node service enable
"""
def patroni_raft_enable (nodes, user="raft"):
    payload=[]
    result = patt.exec_script (nodes=nodes, src="./dscripts/d12.raft_controller.sh", payload=payload,
                               args=['enable'] +
                               ['patroni_raft_controller.service'] + [user],
                               sudo=True,
                               log_call=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
postgres peer raft path configure
"""
def patroni_pg_node_raft_configure (nodes):
    payload=['dscripts/tmpl2file.py', 'config/patroni_raft_controller.service.tmpl', 'config/patroni_raft.te']
    result = patt.exec_script (nodes=nodes, src="./dscripts/d12.raft_controller.sh", payload=payload,
                               args=['pg_node_configure'] +
                               ['/var/lib/raft'] + ['patroni_raft.te'],
                               sudo=True,
                               log_call=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

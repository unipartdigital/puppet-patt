#!/usr/bin/env python3

import patt
import logging
import os
import tempfile
from pathlib import Path
import shutil
from string import Template

logger = logging.getLogger('patt_postgres')

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
            logger.error ("stderr syst: {}".format (r.error))
    return error_count

"""
install postgres packages and dep on each nodes
"""
def postgres_init(postgres_version, nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d20.postgres.sh",
                                args=['init'] + [postgres_version], sudo=True)
    log_results (result)


def postgres_get_cert  (q, postgres_user='postgres', nodes=[]):
    if q == 'root.crt':
        e='--get_ca_crt'
    elif q == 'root.key':
        e='--get_ca_key'
    else:
        raise ValueError ("unknow query {}".format(q))
    for n in nodes:
        try:
            result = patt.exec_script (nodes=[n], src="dscripts/ssl_cert_postgres.py",
                                        args=['-u', postgres_user, e], sudo=True)
        except:
            continue
        else:
            for r in result:
                if r.out:
                    return r.out
        finally:
            log_results (result, hide_stdout=True)

def postgres_ssl_cert(cluster_name,
                      postgres_user='postgres',
                      nodes=[],
                      keep_ca=True):
    ssl_script="misc/self_signed_certificate.py"
    source = patt.Source()
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    # if run via puppet it will install the cert on the running agent but
    # not the others node before running the installer.
    # Retrieve and distribue the cert to all nodes
    running_node = source.whoami(nodes)
    ca_provider=nodes
    if running_node:
        ca_provider=[running_node]
        self_ca_dir=None # installing from peer
    else:
        # not installing from peer
        if keep_ca:
            self_home = os.path.expanduser("~")
            self_ca_dir = self_home + '/' + '.patt/ca'
            Path(self_ca_dir).mkdir(parents=True, exist_ok=True, mode=0o700)

    for i in ['root.key', 'root.crt']:
        tmp = postgres_get_cert (q=i, postgres_user=postgres_user, nodes=ca_provider)
        if not tmp:
            # generate CA on first node and retry
            result = patt.exec_script (nodes=[nodes[0]],
                                        src="dscripts/ssl_cert_postgres.py",
                                        payload=ssl_script,
                                        args=['-c'] + [cluster_name] +
                                        ['-s'] + [os.path.basename (ssl_script)] +
                                        ['-u'] + [postgres_user] +
                                        ['--ca_country_name', "'UK'"] +
                                        ['--ca_state_or_province_name', "'United Kingdom'"] +
                                        ['--ca_locality_name', "'Cambridge'"] +
                                        ['--ca_organization_name', "'Patroni Postgres Cluster'"] +
                                        ['--ca_common_name', "'CA {}'".format (cluster_name)] +
                                        ['--ca_not_valid_after', "'3650'"] +
                                        ['-p'] + [p.hostname for p in nodes] +
                                        list ([" ".join(p.ip_aliases) for p in nodes]),
                                        sudo=True)
            log_results (result)
            tmp = postgres_get_cert (q=i, postgres_user=postgres_user, nodes=[nodes[0]])

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open (tmp_dir + '/' + i, "w") as cf:
                cf.write(tmp)
                cf.write('\n')
                cf.flush()
                cf.close()
                os.chmod(cf.name, 0o640)
                if self_ca_dir:
                    if os.path.isdir(self_ca_dir):
                        t = self_ca_dir + '/' + cluster_name + '-' + os.path.basename (cf.name)
                        if not os.path.isfile (t): shutil.copy2(cf.name, t)
                result = patt.exec_script (nodes=nodes, src="dscripts/ssl_cert_postgres.sh",
                                            payload=tmp_dir + '/' + i,
                                            args=['copy_ca', os.path.basename (tmp_dir + '/' + i), i],
                                            sudo=True)
                log_results (result, hide_stdout=True)


    result = patt.exec_script (nodes=nodes,
                                src="dscripts/ssl_cert_postgres.py",
                                payload=ssl_script,
                                args=['-c'] + [cluster_name] +
                                ['-s'] + [os.path.basename (ssl_script)] +
                                ['-u'] + [postgres_user] +
                                ['-p'] + [p.hostname for p in nodes] +
                                list ([" ".join(p.ip_aliases) for p in nodes]),
                                sudo=True)
    log_results (result)


"""
lookup ~/.patt/ca/ for cluster_name-root.crt and cluster_name-root.key
if found generate a user cert ~/.patt/ca/cluster_name-user_name.crt/key
"""
def postgres_ssl_user_cert(cluster_name, user_names=[]):
    self_home = os.path.expanduser("~")
    self_ca_dir = self_home + '/' + '.patt/ca'
    ca_path_crt = self_ca_dir + '/' + cluster_name + '-' + 'root.crt'
    ca_path_key = self_ca_dir + '/' + cluster_name + '-' + 'root.key'

    if os.path.isfile (ca_path_crt) and os.path.isfile (ca_path_key):
        import misc.self_signed_certificate as ssl_gen
        ca_key = ssl_gen.private_key(key_path=ca_path_key)
        for i in user_names:
            usr_path_crt = self_ca_dir + '/' + cluster_name + '-' + i + '.crt'
            usr_path_key = self_ca_dir + '/' + cluster_name + '-' + i + '.key'
            usr_key = ssl_gen.private_key(key_path=usr_path_key)
            usr_crt = ssl_gen.mk_certificate_thin(country_name="UK",
                                                  state_or_province_name="United Kingdom",
                                                  locality_name="Cambridge",
                                                  organization_name="Patroni Postgres Cluster",
                                                  common_name=i,
                                                  private_key=ca_key,
                                                  public_key=usr_key.public_key(),
                                                  certificate_path=usr_path_crt,
                                                  ca_path=ca_path_crt,
                                                  not_valid_after_days=365,
                                                  dns=[],
                                                  ip=[]
                                                  )


"""
exec the script file as user postgres
if the script file is local, it will be first copyed on the nodes
if script file is executable it will be run as it is otherwise it will run via bash
script_file must be idempotent
"""
def postgres_exec(postgres_peers, script_file):
    script = None
    nodes=postgres_peers
    if os.path.isfile (script_file):
        script = script_file
        script_arg=os.path.basename (script_file)
    else:
        script_arg=script_file

    result = patt.exec_script (nodes=nodes,
                                src="./dscripts/postgres_exec.sh", payload=script,
                                args=[script_arg],
                                sudo=True,
                                log_call=True)
    log_results (result)

def postgres_db_role(postgres_peers,
                     role_name, database_name, role_options=[],
                     template_file=''):
    dictionary={'role_options': ''}
    dictionary['role_name']=role_name
    if role_options:
        dictionary['role_options']="WITH {}".format (" ".join(role_options))
    dictionary['database_name']=database_name

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open (tmp_dir + '/' + 'pg_db_role.script', "w") as cf:
            with open(template_file, 'r') as t:
                str=Template (t.read())
                cf.write(str.substitute(dictionary))
                cf.flush()
                t.close()
            postgres_exec(postgres_peers, cf.name)
            cf.close()

def postgres_create_role(postgres_peers, role_name, role_options=[]):
    postgres_db_role(postgres_peers=postgres_peers, role_name=role_name, role_options=role_options,
                     database_name='',
                     template_file="./config/pg_create_role.tmpl")

def postgres_create_database(postgres_peers, database_name, owner):
    postgres_db_role(postgres_peers=postgres_peers, database_name=database_name, role_name=owner,
                     template_file="./config/pg_create_database.tmpl")

"""
install postgres GC cron script
"""
def postgres_gc_cron(nodes, vaccum_full_df_percent, target, postgres_version):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    tmpl="./config/postgres-gc.sh.tmpl"
    vacuumdb_option=""
    if postgres_version >= 12:
        vacuumdb_option="--skip-locked"
    result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                               payload=tmpl,
                               args=['-t'] + [os.path.basename (tmpl)] +
                               ['-o'] + [target] +
                               ['--chmod'] + ['755'] +
                               ['--dictionary_key_val'] + ["pc={}".format(vaccum_full_df_percent)] +
                               ['--dictionary_key_val'] + ["vacuumdb_option={}".format(vacuumdb_option)],
                               sudo=True)
    log_results (result)

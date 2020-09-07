#!/usr/bin/env python3

import subprocess
import yaml
import sys
import argparse
import os
import socket
import sys
import ast
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN

"""
use ip addr show to return a list of setup ip address
"""
def ip_show(scope='global'):
    result = []
    cmd = subprocess.run(["/sbin/ip", "-br", "addr", "show", "scope", scope],
                         stdout=subprocess.PIPE, encoding='utf8')
    if cmd.returncode == 0:
        for l  in cmd.stdout.splitlines():
            try:
                (iface, flag, ips) = l.split(maxsplit=2)
                result.append ({'iface': iface, 'flag': flag, 'ip': [i.split('/',1)[0] for i in ips.split()]})
            except:
                pass
    return result

"""
list all the ip set on the system and return the first match with the list of nodes
"""
def _get_ip(nodes):
    ip = [i['ip'] for i in ip_show() if i['flag'] == 'UP'][0]
    for n in nodes:
        if n in ip:
            return [i for i in ip if i == n ][0]

"""
node name should be uniq cluster wide
hostid may be a good choice but fixed IP or host name should work as well.
"""
def _get_hostid():
    try:
        cmd = subprocess.run(["cat", "/etc/machine-id"], stdout=subprocess.PIPE, encoding='utf8')
        if cmd.returncode == 0:
            return cmd.stdout.strip()
    except:
        raise

"""
if patroni_config is readable return a yaml object otherwise None
"""
def _get_patroni_config (patroni_config='/var/lib/pgsql/patroni.yaml'):
    result=None
    if os.path.isfile(patroni_config):
            with open(patroni_config, 'r') as p:
                try:
                    result=yaml.safe_load(p)
                    return result
                except yaml.YAMLError as e:
                    print(str(e), file=sys.stderr)
                    raise
                except:
                    raise
    return result

class PatroniConfig(object):

    def __init__(self, cluster_name, template_file, nodes, etcd_peers,
                 sys_user_pass, dst_file, name_space="/service"):
        self.tmpl=None
        self.file_name=dst_file
        self.user_pass_dict = {} if sys_user_pass == None else dict(ast.literal_eval(sys_user_pass))
        self.pass_rep = ''
        self.pass_rew = ''
        self.pass_sup = ''
        self.prev=_get_patroni_config(self.file_name)

        with open(template_file, 'r') as t:
            try:
                self.tmpl=(yaml.safe_load(t))
            except yaml.YAMLError as e:
                print(str(e), file=sys.stderr)
                raise
            except:
                raise

        try:
            self.pass_rep = self.prev['postgresql']['authentication']['replication']['password']
        except:
            pass
        try:
            self.pass_rew = self.prev['postgresql']['authentication']['rewind']['password']
        except:
            pass
        try:
            self.pass_sup = self.prev['postgresql']['authentication']['superuser']['password']
        except:
            pass

        if not self.pass_rep and 'replication' in self.user_pass_dict:
            self.pass_rep = self.user_pass_dict['replication']
        if not self.pass_rew and 'rewind' in self.user_pass_dict:
            self.pass_rew = self.user_pass_dict['rewind']
        if not self.pass_sup and 'superuser' in self.user_pass_dict:
            self.pass_sup = self.user_pass_dict['superuser']

        if not self.tmpl['postgresql']['authentication']['replication']['password']:
            self.tmpl['postgresql']['authentication']['replication']['password'] = self.pass_rep
        if not self.tmpl['postgresql']['authentication']['rewind']['password']:
            self.tmpl['postgresql']['authentication']['rewind']['password'] = self.pass_rew
        if not self.tmpl['postgresql']['authentication']['superuser']['password']:
            self.tmpl['postgresql']['authentication']['superuser']['password'] = self.pass_sup

        my_ip = _get_ip(nodes)
        # override Global/Universal
        self.tmpl['name'] = _get_hostid()
        self.tmpl['namespace'] = name_space
        self.tmpl['scope'] = cluster_name
        self.tmpl['postgresql']['connect_address'] = my_ip + ':5432'

        # restapi should be globaly accessible for haproxy
        self.tmpl['restapi']['listen'] = ':::8008'
        # restapi address + port to access the REST API (from the others node)
        self.tmpl['restapi']['connect_address'] = my_ip + ':8008'

        # provide a static list of etcd peers
        self.tmpl['etcd']['hosts'] = ",".join([str(i) + ":2379" for i in etcd_peers])

    def write (self):
        try:
            with open(self.file_name, 'w') as f:
                print(yaml.dump(self.tmpl, default_flow_style=False), file=f)
        except:
            raise

    def dump (self):
        try:
            print(yaml.dump(self.tmpl, default_flow_style=False))
        except:
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--cluster_name', help='cluster name', required=True)
    parser.add_argument('-t','--template_file', help='patroni yaml template file', required=True)
    parser.add_argument('-d','--destination_file', help='patroni yaml destination file', required=True)
    parser.add_argument('-p','--postgres_peers', help='postgres peers', required=True, nargs='+')
    # peers argument should be called like: '-p p1 p2 p3'
    parser.add_argument('-e','--etcd_peers', help='etcd peers', required=True, nargs='+')
    parser.add_argument('-s','--sys_user_pass', help='system user password dict', required=True, type=str)
    parser.add_argument('--lock_dir', help='lock directory', required=False, default="/tmp")

    args = parser.parse_args()
    os.chdir (os.path.dirname (__file__))

    lock_filename = args.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
    if not os.path.exists(lock_filename):
        lockf = open(lock_filename, "w+")
        lockf.close()
    lockf = open(lock_filename, "r")
    lock_fd = lockf.fileno()
    flock(lock_fd, LOCK_EX | LOCK_NB)

    pc = PatroniConfig (cluster_name=args.cluster_name,
                        template_file=args.template_file,
                        nodes=args.postgres_peers,
                        etcd_peers=args.etcd_peers,
                        sys_user_pass=args.sys_user_pass,
                        dst_file=args.destination_file)
    pc.write ()

    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass
#!/usr/bin/env python3

import subprocess
import sys
import argparse
import os
import socket
import sys
from string import Template
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
    print (result)
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
        cmd = subprocess.run(["hostid"], stdout=subprocess.PIPE, encoding='utf8')
        if cmd.returncode == 0:
            return cmd.stdout.strip()
    except:
        raise

class HAProxyConfig(object):

    def __init__(self, cluster_name, template_file, nodes, postgres_nodes, postgres_port=5432, check_port=8008):
        tmpl=None
        self.dic = {}

        with open(template_file, 'r') as t:
            try:
                self.tmpl=Template (t.read())
            except:
                raise

        self.dic['host_ip'] = _get_ip(nodes)
        self.dic['server_list']=""
        for n in postgres_nodes:
            self.dic['server_list'] += \
            "server postgresql_{}_{} {}:{} maxconn 100 check port {}\n    ".format \
            (n, postgres_port, n, postgres_port, check_port)

    def write (self, file_name):
        try:
            with open(file_name, 'w') as f:
                print(self.tmpl.substitute(self.dic), file=f)
        except:
            raise

    def dump (self):
        try:
            print(self.tmpl.substitute(self.dic))
        except:
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--cluster_name', help='cluster name', required=True)
    parser.add_argument('-t','--template_file', help='haproxy template file', required=True)
    parser.add_argument('-d','--destination_file', help='haproxy destination file', required=True)
    parser.add_argument('-p','--postgres_peers', help='postgres peers', required=True, nargs='+')
    parser.add_argument('-x','--haproxy_peers', help='haproxy peers', required=True, nargs='+')
    parser.add_argument('--lock_dir', help='lock directory', required=False, default="/tmp")

    # peers argument should be called like: '-p p1 p2 p3'

    args = parser.parse_args()
    os.chdir (os.path.dirname (__file__))

    lock_filename = args.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
    if not os.path.exists(lock_filename):
        lockf = open(lock_filename, "w+")
        lockf.close()
    lockf = open(lock_filename, "r")
    lock_fd = lockf.fileno()
    flock(lock_fd, LOCK_EX | LOCK_NB)

    hapc = HAProxyConfig (cluster_name=args.cluster_name,
                          template_file=args.template_file,
                          nodes=args.haproxy_peers, postgres_nodes=args.postgres_peers)
    hapc.dump ()
    hapc.write (args.destination_file)

    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass

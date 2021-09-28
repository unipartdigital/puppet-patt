#!/usr/bin/env python3

#import subprocess
import sys
import argparse
import os
from string import Template
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN

class NftConfig(object):

    def __init__(self, template_file, patroni_peers=[], etcd_peers=[], raft_peers=[], haproxy_peers=[],
                 postgres_clients=[], monitoring_clients=[]):
        tmpl=None
        self.dic = {}
        with open(template_file, 'r') as t:
            try:
                self.tmpl=Template (t.read())
            except:
                raise

        if not patroni_peers:
            patroni_peers=["::1"]
        if not etcd_peers:
            etcd_peers=["::1"]
        if not raft_peers:
            raft_peers=["::1"]
        if not haproxy_peers:
            haproxy_peers=["::1"]
        if not postgres_clients:
            postgres_clients=["::0/0"]
        if not monitoring_clients:
            monitoring_clients=["::0/0"]

        self.dic['etcd_peers'] = ", ".join (etcd_peers)
        self.dic['raft_peers'] = ", ".join (raft_peers)
        self.dic['patroni_peers'] = ", ".join (patroni_peers)
        self.dic['haproxy_peers'] = ", ".join (haproxy_peers)
        self.dic['postgres_clients'] = ", ".join (postgres_clients)
        self.dic['monitoring_clients'] = ", ".join (monitoring_clients)

    def write (self, file_name):
        try:
            with os.fdopen(os.open (file_name, os.O_CREAT | os.O_WRONLY, 0o600), 'w') as f:
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
    parser.add_argument('-t','--template_file', help='patroni yaml template file', required=True)
    parser.add_argument('-d','--destination_file', help='patroni yaml destination file', required=False)
    # peers arguments should look like: -p p1 p2 p3 -e e1 e2 e3 -x x1 x2 x3 -c c1 c2 c3
    parser.add_argument('-p','--patroni_peers', help='postgres peers', required=True, nargs='+')
    parser.add_argument('-e','--etcd_peers', help='etcd peers', required=False, nargs='+')
    parser.add_argument('-r','--raft_peers', help='raft peers', required=False, nargs='+')
    parser.add_argument('-x','--haproxy_peers', help='haproxy peers', required=False, nargs='+')
    parser.add_argument('-c','--postgres_clients', help='postgres_clients', required=False, nargs='+')
    parser.add_argument('-m','--monitoring_clients', help='monitoring_clients', required=False, nargs='+')
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

    nft = NftConfig (template_file=args.template_file,
                     patroni_peers=args.patroni_peers,
                     etcd_peers=args.etcd_peers,
                     raft_peers=args.raft_peers,
                     haproxy_peers=args.haproxy_peers,
                     postgres_clients=args.postgres_clients,
                     monitoring_clients=args.monitoring_clients)
    if args.destination_file:
        nft.write (args.destination_file)
    else:
        nft.dump ()

    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass

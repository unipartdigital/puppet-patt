#!/usr/bin/env python3

import requests
import sys
import os
import yaml
import argparse
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN
import pwd

"""
if patroni_config is readable return a yaml object otherwise None
"""
def _get_patroni_config (patroni_config="{}/patroni.yaml".format (pwd.getpwnam('postgres').pw_dir)):
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

def get_sys_user (patroni_config="{}/patroni.yaml".format (pwd.getpwnam('postgres').pw_dir)):
    pc = _get_patroni_config (patroni_config=patroni_config)
    result = {}
    for u in ['replication', 'superuser', 'rewind']:
        if 'postgresql' in pc and 'authentication' in pc['postgresql']:
            if u in pc['postgresql']['authentication'] and 'password' in pc['postgresql']['authentication'][u]:
                result[u] = pc['postgresql']['authentication'][u]['password']
    print (result)

def cluster_info(patroni_url='http://localhost:8008/cluster'):
    try:
        r = requests.get(patroni_url)
        if r.status_code == requests.codes.ok:
            print (r.json())
        else:
            sys.exit(r.status_code)
    except:
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--info', help='requested info: [cluster|sys_user]', required=False)
    parser.add_argument('--lock_dir', help='lock directory', required=False, default="/tmp")

    args = parser.parse_args()

    lock_filename = args.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
    if not os.path.exists(lock_filename):
        lockf = open(lock_filename, "w+")
        lockf.close()
    lockf = open(lock_filename, "r")
    lock_fd = lockf.fileno()
    flock(lock_fd, LOCK_EX | LOCK_NB)

    if args.info == 'cluster':
        cluster_info()
    elif args.info == 'sys_user':
        get_sys_user()

    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass

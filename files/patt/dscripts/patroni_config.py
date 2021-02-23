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
import hashlib
import io
import pwd

"""
query /etc/os-release and build an os vendor dictionary with 'ID', 'VERSION_ID', 'MAJOR_VERSION_ID'
"""
def os_release ():
   os_release_dict = {}
   with open("/etc/os-release") as osr:
      lines=osr.readlines()
      for i in lines:
         if '=' in i:
            k,v=i.split('=',1)
            if k.upper() in ['ID', 'VERSION_ID']:
                v=v.strip()
                if v.startswith('"') and v.endswith('"'):
                    v=v[1:-1].strip()
                os_release_dict[k.upper()]=v
            if 'VERSION_ID' in os_release_dict:
               os_release_dict['MAJOR_VERSION_ID'] = os_release_dict['VERSION_ID'].split('.')[0]
   return os_release_dict

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

class PatroniConfig(object):

    def __init__(self, cluster_name, template_file, nodes, etcd_peers,
                 sys_user_pass, dst_file, postgres_version, name_space="/service"):
        self.tmpl=None
        self.file_name=dst_file
        self.user_pass_dict = {} if sys_user_pass == None else dict(ast.literal_eval(sys_user_pass))
        self.pass_rep = ''
        self.pass_rew = ''
        self.pass_sup = ''
        self.prev=_get_patroni_config(self.file_name)

        osr = os_release()

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

        if osr['ID'] in ['rhel', 'centos', 'fedora']:
            self.tmpl['postgresql']['data_dir'] = "/var/lib/pgsql/{}/data".format (postgres_version.strip())
            self.tmpl['postgresql']['bin_dir'] = "/usr/pgsql-{}/bin".format (postgres_version.strip())
            self.tmpl['postgresql']['pgpass'] = "/var/lib/pgsql/pgpass"
        elif osr['ID'] in ['debian', 'ubuntu']:
            self.tmpl['postgresql']['data_dir'] = "/var/lib/postgresql/{}/data".format (
                postgres_version.strip())
            self.tmpl['postgresql']['bin_dir'] = "/usr/lib/postgresql/{}/bin".format (
                postgres_version.strip())
            self.tmpl['postgresql']['pgpass'] = "/var/lib/postgresql/pgpass"
        else:
            raise ValueError ("not implemented {}".format(osr))

        # restapi should be globaly accessible for haproxy
        self.tmpl['restapi']['listen'] = ':::8008'
        # restapi address + port to access the REST API (from the others node)
        self.tmpl['restapi']['connect_address'] = my_ip + ':8008'

        # provide a static list of etcd peers
        self.tmpl['etcd']['hosts'] = ",".join([str(i) + ":2379" for i in etcd_peers])

        # enable ssl if not set or explicitly disabled (and if possible)
        def is_ssl_set (tmpl_str):
            if not 'postgresql' in tmpl_str: return False
            if not 'parameters' in tmpl_str['postgresql']: return False
            if not 'ssl' in tmpl_str['postgresql']['parameters']: return False
        if is_ssl_set (self.tmpl):
            pass
        else:
            from os import access, R_OK
            from os.path import isfile
            pg_home=pwd.getpwnam('postgres').pw_dir
            try:
                for f in [pg_home + '/server.crt', pg_home + '/server.key']:
                    assert isfile(f) and access(f, R_OK)
            except AssertionError:
                pass
            else:
                self.tmpl['postgresql']['parameters']['ssl'] = True
                self.tmpl['postgresql']['parameters']['ssl_cert_file'] = pg_home + '/server.crt'
                self.tmpl['postgresql']['parameters']['ssl_key_file']  = pg_home + '/server.key'
                try:
                    f = pg_home + '/.postgresql/root.crt'
                    assert isfile(f) and access(f, R_OK)
                except AssertionError:
                    pass
                else:
                    self.tmpl['postgresql']['parameters']['ssl_ca_file'] = pg_home + '/.postgresql/root.crt'

    """
    write only on change
    """
    def write (self):
        old_md5 = hashlib.md5()
        new_md5 = hashlib.md5()
        if os.path.isfile(self.file_name):
            with open(self.file_name, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    old_md5.update(chunk)

        buf = io.StringIO()
        print(yaml.dump(self.tmpl, default_flow_style=False), file=buf)
        new_md5.update(buf.getvalue().encode('utf8'))

        if old_md5.hexdigest() == new_md5.hexdigest():
            return
        try:
            with open(self.file_name, 'w') as f:
                print(yaml.dump(self.tmpl, default_flow_style=False), file=f)
        except:
            raise
        try:
            with open('/tmp/patroni.reload', 'w') as f:
                pass
        except:
            raise
        finally:
            f.close()

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
    parser.add_argument('-u','--user', help='destination_file relative to <user> home dit', required=False)
    parser.add_argument('-v','--postgres_version', help='postgres version', required=True)
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

    destination_file=None
    if args.user and args.user is not None:
        destination_file = "{}/{}".format (pwd.getpwnam(args.user).pw_dir, args.destination_file)
    else:
        destination_file = args.destination_file

    pc = PatroniConfig (cluster_name=args.cluster_name,
                        template_file=args.template_file,
                        postgres_version=args.postgres_version,
                        nodes=args.postgres_peers,
                        etcd_peers=args.etcd_peers,
                        sys_user_pass=args.sys_user_pass,
                        dst_file=destination_file)
    pc.write ()

    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass

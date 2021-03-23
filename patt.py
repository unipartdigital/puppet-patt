#!/usr/bin/env python3

import os, sys
from multiprocessing import Pool
import logging

logger = logging.getLogger('patt')

try:
    import ssh_client
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath( __file__ )) + '/ssh')
    import ssh_client

class Resp:
    def __init__(self):
        self.hostname = None
        self.sudo = None
        self.id = None
        self.error = None
        self.out = None

class Source:
    def __init__(self):
        self.id = None

    """
    set id to the contain of machine-id or "" if /etc/machine-id is not found
    """
    def host_id(self):
        if self.id: return self.id
        try:
            with open ('/etc/machine-id', "r") as f:
                self.id = f.read().strip()
                if int (self.id, 16) == 0:
                    raise
        except FileNotFoundError:
            self.id = ""

    def whoami(self, nodes=[]):
        if not self.id:
            self.host_id()
        for n in nodes:
            if self.id == n.id:
                return n

    def part_of(self, nodes=[]):
        tmp = self.whoami()
        if tmp: return True
        return False

class Node:

    def __init__(self, ssh_uri, default_login=None, default_keyfile=None, default_port=22):
        self.hostname = None
        self.login = None
        self.port = None
        self.id = None
        self.ip_aliases = []
        self.user_object = []
        # embedded user param
        (self.login, self.hostname, self.port) = ssh_client._ipv6_nri_split(ssh_uri)
        if self.login == '' and default_login:
            self.login = default_login
        if self.port:
            self.port = int(self.port)
        elif default_port:
            self.port = default_port
        self.keyfile = default_keyfile

    """
    check connectivity and if we can run sudo command
    """
    def _check_priv (self):
        clt = ssh_client.ssh_client (self.hostname, port=self.port, login=self.login, keyfile=self.keyfile)
        try:
            clt.open(timeout=10)
            result = clt.exec ('sudo id -u')
            r = Resp()
            r.hostname = self.hostname
            if result.status == 0:
                r.sudo = int(result.stdout.read()) == 0
                return r
            else:
                r.error =  result.stderr.read().decode()
                return r
        except Exception as e:
            logger.error ("_check_priv ({})".format(self.hostname))
            logger.error (str(e))
            return None
        finally:
            clt.close()

    """
    host_id
    retrieve hostid via ssh
    """
    def _host_id (self):
        try:
            clt = ssh_client.ssh_client (
                self.hostname, port=self.port, login=self.login, keyfile=self.keyfile)
            clt.open(timeout=10)
            # result = clt.exec ('hostid')
            result = clt.exec ('cat /etc/machine-id')
            if result.status == 0:
                self.id = result.stdout.read().decode().strip()
                if int (self.id, 16) == 0:
                    logger.error ("_get_id ({}) id == 0!".format(self.hostname))
                    raise
        except Exception as e:
            logger.error ("_get_id ({})".format(self.hostname))
            logger.error (str(e))
        finally:
            clt.close()

    """
    host_ip_aliases
    retrieve all the host ipv6 aliases via ssh
    """
    def _host_ip_aliases (self):
        try:
            clt = ssh_client.ssh_client (
                self.hostname, port=self.port, login=self.login, keyfile=self.keyfile)
            clt.open(timeout=10)
            result = clt.exec (
                "/sbin/ip -br -6 a show to 2000::/3 | sed 's|[[:space:]]\+| |g' | cut -d' ' -f 3- ")
            if result.status == 0:
                tmp = result.stdout.read().decode().strip()
                tmp = tmp.split()
                self.ip_aliases = [i.split('/')[0] for i in tmp if i.split('/')[0] not in self.hostname]
        except Exception as e:
            logger.error ("_host_ip_aliases ({})".format(self.hostname))
            logger.error (str(e))
        finally:
            clt.close()

    """
    exec script
    """
    def _exec_script (self):
        src      = self.user_object[0]
        sudo     = self.user_object[1]
        payload  = self.user_object[2]
        args     = self.user_object[3]
        log_call = self.user_object[4]
        if log_call:
            logger.info ("{} -> {}".format (self.hostname, self.user_object))
        try:
            r = Resp()
            clt = ssh_client.ssh_client (
                self.hostname, port=self.port, login=self.login, keyfile=self.keyfile)
            clt.open(timeout=None)
            rscript = clt.mktemp_send_file (src, 0o700)

            if rscript and payload:
                remote_d = os.path.dirname (rscript)
                sftp = clt.new_sftp()
                if isinstance(payload, list):
                    for p in payload:
                        local_p = os.path.abspath (p)
                        sftp.put (local_p, remote_d + '/' + os.path.basename (local_p))
                else:
                    local_p = os.path.abspath (payload)
                    sftp.put (local_p, remote_d + '/' + os.path.basename (local_p))

            args = ' '.join (str(e) for e in args)
            if sudo:
                sudo='sudo '
            else:
                sudo=''
            result = clt.exec (sudo + rscript + ' ' + args)
            r.hostname = self.hostname
            if self.id: r.id = self.id
            try:
                if rscript:
                    tmp_clean = clt.exec (sudo + '/usr/bin/rm -f' + ' ' + rscript)
                if isinstance(payload, list):
                    for p in payload:
                        tmp_clean = clt.exec (sudo + '/usr/bin/rm -f' + ' ' +
                                              os.path.dirname (rscript) + '/' + os.path.basename (p))
                elif payload:
                    tmp_clean = clt.exec (sudo + '/usr/bin/rm -f' + ' ' +
                                          os.path.dirname (rscript) + '/' + os.path.basename (payload))
                if rscript:
                    tmp_clean = clt.exec (sudo + '/usr/bin/rmdir --ignore-fail-on-non-empty ' +
                                          os.path.dirname (rscript))
            except:
                pass
            else:
                if result.status == 0:
                    r.out = result.stdout.read().decode().strip()
                    return r
                else:
                    r.error = result.stderr.read().decode()
                    return r
        except Exception as e:
            logger.error ("hostname: {}".format(r.hostname))
            logger.error ("stdout: {}".format (r.out))
            logger.error ("stderr: {}".format (r.error))
            logger.error (str(e))
            raise
        finally:
            clt.close()

"""
convenient way to build a list of Node (Class Object)
"""
def to_nodes (nodes=[], default_login=None, default_keyfile=None):
    result = [Node (n, default_login, default_keyfile) for n in nodes]
    return result

def check_priv (nodes):
    with Pool(len(nodes)) as pool:
        try:
            results = [pool.map_async (Node._check_priv, (n for n in nodes))]
            for r in results:
                return r.get(timeout=10)
        except:
            raise

def _host_id_ref (n):
    if n.id:
        return n
    n._host_id()
    return n

def host_id (nodes):
    with Pool(len(nodes)) as pool:
        try:
            results = [pool.map_async (_host_id_ref, nodes)]
            for r in results:
                for i in r.get(timeout=10):
                    for idx, item in enumerate(nodes):
                        if i.hostname in item.hostname:
                            nodes[idx] = i
            pool.close()
            pool.join()
        except:
            raise

def _host_ip_aliases_ref (n):
    if n.ip_aliases:
        return n
    n._host_ip_aliases()
    return n

def host_ip_aliases (nodes):
    with Pool(len(nodes)) as pool:
        try:
            results = [pool.map_async (_host_ip_aliases_ref, nodes)]
            for r in results:
                for i in r.get(timeout=10):
                    for idx, item in enumerate(nodes):
                        if i.hostname in item.hostname:
                            nodes[idx] = i
            pool.close()
            pool.join()
        except:
            raise

def check_dup_id (nodes):
    id_list=[]
    for i in nodes:
        id_list.append(i.id)

    seen = {}
    dupes = []
    for x in id_list:
        if x not in seen:
            seen[x] = 1
        else:
            if seen[x] == 1:
                dupes.append(x)
            seen[x] += 1
    if len (dupes) > 0:
        logger.error ("{} id not uniq".format (dupes))
        raise ValueError ("{} id not uniq".format (dupes))


def exec_script (nodes, src, sudo=True, payload=None, args=[], log_call=True, timeout=360):
    with Pool(len(nodes)) as pool:
        try:
            for n in nodes:
                n.user_object = [src, sudo, payload, args, log_call]
            results = pool.map_async (Node._exec_script, (n for n in nodes))
            return results.get(timeout=timeout)
        except Exception as e:
            logger.error (str(e))
            raise

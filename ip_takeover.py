#!/usr/bin/python3

"""
 callback script: action, role and cluster name
 add vip on master
 del vip on replica

"""

import logging
import sys, os
import ipaddress
import subprocess

#from patroni.utils import Retry, RetryFailedError

logger = logging.getLogger(__name__)

class Iproute2Error (Exception):
    def __init__(self, message=None):
        self.message = message

def iproute2 (objects=None, command=[], options=['-6', '-br']):
    logger.warning ("{}".format (["/sbin/ip"] + options + [objects] + command))
    cmd = subprocess.run(["/sbin/ip"] + options + [objects] + command,
                         stdout=subprocess.PIPE, encoding='utf8')
    if cmd.returncode == 0:
        return cmd.stdout.strip()
    else:
        raise Iproute2Error (cmd.stderr.strip())

def read_ip_iface_from_file (file_name):
    ip_iface =[]
    try:
        with open(os.open (file_name, os.O_RDONLY)) as f:
            try:
                for l in f.readlines():
                    a = l.split ('%')
                    iface = None
                    try:
                        ip = ipaddress.IPv6Address(a[0].strip())
                        iface = a[1].strip()
                    except IndexError:
                        ip = ipaddress.IPv6Address(l.strip())
                        if ip.is_global and (ip,iface) not in ip_iface:
                            ip_iface.append ((str(ip), iface))
                    except ipaddress.AddressValueError as e:
                        pass
                    except Exception as e:
                        logger.exception ("{}".format (e))
                        continue
                    else:
                        if ip.is_global and (ip,iface) not in ip_iface:
                            ip_iface.append ((str(ip), iface))
            except Exception as e:
                logger.warning ("{}".format (e))
                pass
        logger.warning ("[{}] {} floating ip {}".format (
            __file__, len (ip_iface), ip_iface))
    except FileNotFoundError as e:
        logger.warning ("[{}] {} {}".format(__file__, e.filename, e.strerror))
    finally:
        return ip_iface

def ip_address_do (cmd, ip_iface=[(None, None)], default_iface=None):
    ip_seen = []
    try:
        result = iproute2 ("addr", ["show", "scope", "global"])
        for l in result.splitlines():
            (iface, flag, ips) = l.split(maxsplit=2)
            ips = ips.split()
            for i in ips:
                ip = ipaddress.IPv6Address(i.split('/')[0])
                ip_seen.append ((ip, iface.strip()))
        for i in ip_iface:
            ip = ipaddress.IPv6Address(i[0])
            iface = default_iface
            if i[1] is not None:
                iface = default_iface
            if cmd == 'add':
                if (ip, iface) in ip_seen:
                    logger.warning ("addr add: {} {} exists".format (str (ip), iface))
                    continue
                iproute2 ("addr", ["add", str (ip), "dev", iface, "scope", "global", "noprefixroute" ,"nodad"])
            elif cmd == 'del':
                if (ip, iface) in ip_seen:
                    iproute2 ("addr", ["del", str (ip), "dev", iface])
                else:
                    logger.warning ("addr del: {} {} not found".format (str (ip), iface))
                    continue
    except Exception as e:
        logger.error ("{}".format (e))

def ip_address_add (ip_iface=[(None, None)], default_iface=None):
    return ip_address_do ('add', ip_iface=ip_iface, default_iface=default_iface)

def ip_address_del (ip_iface=[(None, None)], default_iface=None):
    return ip_address_do ('del', ip_iface=ip_iface, default_iface=default_iface)

class IPTakeOver(object):
    def __init__(self, cluster_name, floating_ip_file_name="/usr/local/etc/patroni_floating_ip.conf"):
        self.cluster_name = cluster_name if cluster_name is not None else 'unknown'
        self.floating_ip = read_ip_iface_from_file (floating_ip_file_name)
        self.is_setup = len (self.floating_ip) > 0
        self.default_iface = None
        try:
            default_iface = []
            result = iproute2 ("addr", ["show", "scope", 'global'])
            for l in result.splitlines():
                (iface, flag, ips) = l.split(maxsplit=2)
                iface = iface.split ('@')[0]
                if iface not in default_iface:
                    default_iface.append (iface)
            if len (default_iface) == 1:
                self.default_iface = default_iface[0]
            else:
                logger.warning ("iface seen {} using {}".format (default_iface, self.default_iface))
        except Exception as e:
            logger.exception (e)

    def ip_add (self):
        ip_address_add (self.floating_ip, self.default_iface)

    def ip_del (self):
        ip_address_del (self.floating_ip, self.default_iface)

# callback
    def on_reload (self, role):
    # run this script when configuration reload is triggered.
        logger.warning ("[{}] {} {}".format (self.cluster_name, "on_reload", role))
        if role == "replica":
            self.ip_del()
        elif role == "master":
            self.ip_add()

    def on_restart (self, role):
    # run this script when the postgres restarts (without changing role).
        logger.warning ("[{}] {} {}".format (self.cluster_name, "on_restart", role))
        if role == "replica":
            self.ip_del()

    def on_role_change (self, role):
    # run this script when the postgres is being promoted or demoted.
    # role here represent the new role:
        # if role == master -> promoted old_role == replica
        # if role == replica -> demoted old_role == master
        logger.warning ("[{}] {} {}".format (self.cluster_name, "on_role_change", role))
        if role == "replica":
            self.ip_del()
        elif role == "master":
            self.ip_add()

    def on_start (self, role):
    # run this script when the postgres starts.
        logger.warning ("[{}] {} {}".format (self.cluster_name, "on_start", role))
        if role == "replica":
            self.ip_del
        elif role == "master":
            self.ip_add()

    def on_stop (self, role):
    # run this script when the postgres stops.
        logger.warning ("[{}] {} {}".format (self.cluster_name, "on_stop", role))


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.WARNING)

    if len(sys.argv) == 4 and sys.argv[1] in (
            'on_reload', 'on_restart', 'on_role_change', 'on_start', 'on_stop'):
        iptakeover = IPTakeOver(cluster_name=sys.argv[3])
        if iptakeover.is_setup:
            getattr(iptakeover, sys.argv[1])(sys.argv[2])
    else:
        sys.exit("Usage: {0} action role name".format(sys.argv[0]))

if __name__ == "__main__":
    main()

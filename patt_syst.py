#!/usr/bin/env python3

import patt
import os
import logging

logger = logging.getLogger('patt_syst')

def log_results(result):
    for r in result:
        logger.debug ("hostname: {}".format(r.hostname))
        logger.debug ("stdout: {}".format (r.out))
        if hasattr(r,'error') and r.error:
            logger.error ("stderr: {}".format (r.error))

"""
install util system packages and dep on each nodes
"""
def util_init(nodes):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("util_init {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d02.util.sh",
                                args=['init'], sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


"""
install nft system packages and dep on each nodes
"""
def nft_init(nodes):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("nft_init {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d01.nft.sh",
                                args=['init'], sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


"""
enable nftables Netfilter Tables Service
"""
def nftables_enable(nodes):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("nftables_enable {}".format ([n.hostname for n in nodes]))

    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d01.nft.sh",
                                args=['nftables_enable'], sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

def nftables_configure(cluster_name, template_src, config_file_target,
                       patroni_peers=[], etcd_peers=[], haproxy_peers=[], sftpd_peers=[],
                       postgres_clients=[], monitoring_clients=[], floating_ip=[]):
    nodes = list ({n.hostname: n for n in
                   patroni_peers + etcd_peers + haproxy_peers + sftpd_peers}.values())
    logger.debug ("nftables_configure {}".format ([n.hostname for n in nodes]))

    nft_init (nodes)

    x_patroni=[x.hostname for x in patroni_peers] + floating_ip
    if not x_patroni:
        x_patroni=['::1']
    x_etcd=[x.hostname for x in etcd_peers] + floating_ip
    if not x_etcd:
        x_etcd=['::1']
    x_haproxy=[x.hostname for x in haproxy_peers] + floating_ip
    if not x_haproxy:
        x_haproxy=['::1']
    x_postgres_clients=[c for c in postgres_clients]
    if not x_postgres_clients:
        x_postgres_clients=['::1/128']
    x_monitoring_clients=[c for c in monitoring_clients]
    if not x_monitoring_clients:
        x_monitoring_clients=['::1/128']

    """
    vip may show up as an aliases
    while it is true, clean it up and set it explicitly for all peer
    """
    def rm_vip(e=[], vip=[]):
        try:
            for v in vip:
                e.remove(v)
        except:
            pass
        return " ".join(e)

    result = patt.exec_script (nodes=nodes, src="./dscripts/nft_config.py", payload=template_src,
                                args=['-t'] + [os.path.basename (template_src)] +
                                ['-d'] + [config_file_target] +
                                ['-p'] + x_patroni +
                                list ([rm_vip(p.ip_aliases, floating_ip) for p in patroni_peers]) +
                                ['-e'] + x_etcd +
                                list ([rm_vip(e.ip_aliases, floating_ip) for e in etcd_peers]) +
                                ['-x'] + x_haproxy +
                                list ([rm_vip(x.ip_aliases, floating_ip) for x in haproxy_peers]) +
                                ['-c'] + x_postgres_clients +
                                ['-m'] + x_monitoring_clients,
                                sudo=True)
    log_results (result)
    all_ok = not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
    if all_ok:
        all_ok = nftables_enable (nodes)
        return all_ok
    return False

"""
setup the free disks on each nodes
"""
def disk_init(nodes, vol_size, mnt=None, user=None, mode=None):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("disk init {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    util_init(nodes)

    opt = []
    if mnt:
        opt = opt + ['--mount_point'] + [mnt]
    if user:
        opt = opt + ['--user_name'] + [user]
    if mode:
        opt = opt + ['--chmod'] + [mode]

    result = patt.exec_script (nodes=nodes, src="./dscripts/data_vol.py", args=opt + ['-s'] + [vol_size],
                               sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
additional repo setup
repo must be on and ready
"""
def add_repo (repo_url, nodes):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("add repo url {}".format (nodes))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d03.repo.sh",
                                args=['add'] + [" ".join(repo_url)], sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
add a tuned postgresql profile and enable it
"""
def tuned_postgresql(nodes):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("tuned postgresql {}".format (nodes))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d22_tuned.sh",
                               args=['enable'], sudo=True)
    log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

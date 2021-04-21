#!/usr/bin/env python3

import patt
import os
import logging

logger = logging.getLogger('patt_syst')

def log_results(result):
    error_count=0
    for r in result:
        logger.debug ("hostname: {}".format(r.hostname))
        logger.debug ("stdout: {}".format (r.out))
        if r.error is None:
            pass
        elif r.error.strip().startswith("Error: Nothing to do"):
            pass
        else:
            error_count += 1
            logger.error ("stderr: {}".format (r.error))
    return error_count

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

def nftables_configure(cluster_name, template_src, config_file_target,
                       patroni_peers=[], etcd_peers=[], haproxy_peers=[], sftpd_peers=[],
                       postgres_clients=[]):
    nodes = list ({n.hostname: n for n in
                   patroni_peers + etcd_peers + haproxy_peers + sftpd_peers}.values())
    logger.debug ("nftables_configure {}".format ([n.hostname for n in nodes]))

    nft_init (nodes)

    x_patroni=[x.hostname for x in patroni_peers]
    if not x_patroni:
        x_patroni=['::1']
    x_etcd=[x.hostname for x in etcd_peers]
    if not x_etcd:
        x_etcd=['::1']
    x_haproxy=[x.hostname for x in haproxy_peers]
    if not x_haproxy:
        x_haproxy=['::1']
    x_postgres_clients=[c for c in postgres_clients]
    if not x_postgres_clients:
        x_postgres_clients=['::1/128']

    result = patt.exec_script (nodes=nodes, src="./dscripts/nft_config.py", payload=template_src,
                                args=['-t'] + [os.path.basename (template_src)] +
                                ['-d'] + [config_file_target] +
                                ['-p'] + x_patroni +
                                list ([" ".join(p.ip_aliases) for p in patroni_peers]) +
                                ['-e'] + x_etcd +
                                list ([" ".join(e.ip_aliases) for e in etcd_peers]) +
                                ['-x'] + x_haproxy +
                                list ([" ".join(x.ip_aliases) for x in haproxy_peers]) +
                                ['-c'] + x_postgres_clients,
                                sudo=True)
    log_results (result)
    nftables_enable (nodes)

"""
setup the free disks on each nodes
"""
def disk_init(nodes, vol_size, mnt=None, user=None):
    nodes = list ({n.hostname: n for n in nodes}.values())
    logger.debug ("disk init {}".format (nodes))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    util_init(nodes)
    if mnt:
        result = patt.exec_script (nodes=nodes, src="./dscripts/data_vol.py",
                                   args=['-m'] + [mnt] + ['-s'] + [vol_size], sudo=True)
    elif user:
        result = patt.exec_script (nodes=nodes, src="./dscripts/data_vol.py",
                                   args=['-u'] + [user] + ['-s'] + [vol_size], sudo=True)
    log_results (result)


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

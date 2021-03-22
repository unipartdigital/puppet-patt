#!/usr/bin/env python3

import patt
import logging
import random
import time

logger = logging.getLogger('patt_etcd')

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class EtcdError(Error):
    """Exception raised for errors in the input/output.
    Attributes:
        expression -- input expression in which the error occurred
        message    -- explanation of the error
    """
    def __init__(self, expression=None, message=None):
        self.expression = expression
        self.message = message

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

def cluster_health(nodes):
    result = patt.exec_script (nodes=nodes, src="./dscripts/d10.etcd.sh",
                               args=['cluster_health'], sudo=True)
    for r in result:
        logger.debug ("cluster_health: _{}_".format(r.out.strip()))
        if r.out.strip() == "cluster is healthy":
            return True
    return False

def get_members(nodes, cluster_name, state='ok'):
    members = []
    if state == 'ok':
        cmd = 'check_healthy'
    else:
        cmd = 'check_unhealthy'

    result = patt.exec_script (nodes=nodes, src="./dscripts/d10.etcd.sh",
                                    args=[cmd] + [cluster_name], sudo=True)

    for r in result:
        try:
            line = r.out.rsplit()
            line = [l.rsplit('[')[1] for l in line]
            line = [l.rsplit(']')[0] for l in line]
        except:
            continue
        if not line:
            continue
        for l in line:
            if l not in members:
                members.append(l)
    return members

"""
wca extract the worst case from the output of patt.rtt6
and return the average of it
warn if mdev > 1
"""
def wca (rtt_matrix, cnt=4):
    result=[]
    for i in rtt_matrix:
        # src/dst/min/avg/max/mdev
        logger.debug ("rtt src/dst/min/avg/max/mdev: {}".format(i[0]))
        if i[0][5] > 1.0:
            logger.warning ("standard deviation warning {}".format (i[0]))
        result.append (i[0][4])
    return int(sum(result)/len(result)) + cnt

def etcd_sort_by_version (nodes):
    for i in range(10):
        resp = patt.exec_script (nodes=nodes, src="./dscripts/d10.etcd.sh", args=['version'], sudo=True)
        log_results (resp)
        if all(x == False for x in [bool(n.error) for n in resp]): break
        time.sleep(3.0)
    for r in resp:
        tmp = (r.hostname, r.out.strip())
        for idx, item in enumerate(nodes):
            if tmp[0] == item.hostname:
                nodes[idx].etcd_version = tmp[1]
    result = sorted(nodes, key=lambda etcd_peer: etcd_peer.etcd_version)
    logger.debug ("etcd_sort_by_version: {}".format(
        [str(n.hostname) + ' ' + str(n.id) + ' ' +  str(n.etcd_version) for n in result]))
    return result

def pick_init_node(nodes):
    # precedence: lowest etcd version number and then lowest etcd version + hostname sort order
    source = patt.Source()
    running_node = source.whoami(nodes)
    sorted_node = etcd_sort_by_version (nodes)
    lowest_etcd = []
    for i in sorted_node:
        if not lowest_etcd:
            lowest_etcd.append (i)
        elif lowest_etcd[0].etcd_version == i.etcd_version:
            lowest_etcd.append (i)
        else:
            break
    picked_up = sorted(lowest_etcd, key=lambda n: n.hostname)[0]
    logger.debug ("pick up etcd node: {}".format(picked_up.hostname))
    return picked_up

def etcd_init(cluster_name, nodes):
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    id_hosts = [n.id + '_' +  n.hostname for n in nodes]
    result = patt.exec_script (nodes=nodes, src="./dscripts/d10.etcd.sh",
                                args=['init'] + [cluster_name] + id_hosts, sudo=True)
    log_results (result)

    good_members = get_members(nodes, cluster_name, 'ok')
    bad_members = get_members(nodes, cluster_name, 'bad')

    initialized = not (not good_members and not bad_members)
    logger.info ("initialized cluster: {}".format (initialized))
    logger.info ("member ok {}".format (good_members))
    logger.info ("member ko {}".format (bad_members))

    init_node = pick_init_node(nodes)

    if not initialized:

        heartbeat_interval=10
        # rtt_matrix = patt.rtt6 (nodes)
        # heartbeat_interval=wca(rtt_matrix) * 1.5
        # if heartbeat_interval < 5:
        election_timeout=50
        # else:
        #     election_timeout=int (10 * heartbeat_interval)

        id_hosts = "{}_{}".format (init_node.id, init_node.hostname)

        result = patt.exec_script (nodes=[init_node], src="./dscripts/d10.etcd.sh",
                                   args=['config'] + ['new'] + [cluster_name] +
                                   [id_hosts], sudo=True)
        #                                   [heartbeat_interval] + [election_timeout] + id_hosts, sudo=True)
        log_results (result)

        result = patt.exec_script (nodes=[init_node], src="./dscripts/d10.etcd.sh",
                                    args=['enable'] + [cluster_name] + [id_hosts], sudo=True)
        log_results (result)

        bad_members = get_members([init_node], cluster_name, 'bad')
        for i in range(3):
            good_members = get_members([init_node], cluster_name, 'ok')
            if good_members: break
            time.sleep(11) #  > than dscripts/d10.etcd.sh file locks wait

        logger.info ("member ok {}".format (good_members))
        logger.info ("member ko {}".format (bad_members))

        if init_node.hostname not in good_members:
            result = patt.exec_script (nodes=[init_node], src="./dscripts/d10.etcd.sh",
                                       args=['disable'] + [cluster_name] + [id_hosts], sudo=True)
            raise EtcdError ('cluster init error', "error initialising new cluster {}".format(cluster_name))

    # process any remaining members one by one using one of the healthy nodes as a controller
    good_members = get_members([init_node], cluster_name, 'ok')
    bad_members = get_members([init_node], cluster_name, 'bad')

    ctrl = [n for n in nodes if n.hostname in good_members]
    members = ctrl

    nodes_to_remove = [n for n in bad_members if n not in [l.hostname for l in nodes]]
    logger.info ("to remove: {}".format (nodes_to_remove))
    if nodes_to_remove:
        result = patt.exec_script (nodes=[ctrl[0]], src="./dscripts/d10.etcd.sh",
                                    args=['member_remove'] + [cluster_name] + nodes_to_remove, sudo=True)
        log_results (result)

    good_members = get_members([init_node], cluster_name, 'ok')
    bad_members = get_members([init_node], cluster_name, 'bad')

    nodes_to_process = [n for n in nodes if n.hostname not in good_members and n.hostname not in bad_members]
    logger.info ("to process: {}".format ([n.hostname for n in nodes_to_process]))
    for m in nodes_to_process:
        logger.info ("process etcd member {}".format (m.hostname))
        if not m.hostname in [n.hostname for n in members]:
            members.append (m)
        id_hosts = [n.id + '_' +  n.hostname for n in members]

        # assert cluster_health([init_node]), "add member require no unhealthy nodes in the cluster"

        assert ctrl, "no usable controller node"
        # only the first control node is used to add member

        for i in range(10):
            result = patt.exec_script (nodes=[ctrl[0]], src="./dscripts/d10.etcd.sh",
                                       args=['member_add'] + [cluster_name] + id_hosts, sudo=True)
            log_results (result)
            if all(x == False for x in [bool(n.error) for n in result]): break
            time.sleep(3.0)

        result = patt.exec_script (nodes=members, src="./dscripts/d10.etcd.sh",
                                    args=['config'] + ['existing'] + [cluster_name] +
                                    id_hosts, sudo=True)
        # [heartbeat_interval] + [election_timeout] + id_hosts, sudo=True)
        log_results (result)

        result = patt.exec_script (nodes=members, src="./dscripts/d10.etcd.sh",
                                    args=['enable'] + [cluster_name] + id_hosts, sudo=True)
        log_results (result)

    good_members = get_members([init_node], cluster_name, 'ok')
    bad_members = get_members([init_node], cluster_name, 'bad')
    logger.warn ("member ok {}".format (good_members))
    logger.warn ("member ko {}".format (bad_members))
    assert good_members
    ok_nodes = [n for n in nodes if n.hostname in good_members and n.hostname not in bad_members]
    assert ok_nodes
    if bad_members:
        time.sleep(3)
        bad_members = get_members(ok_nodes, cluster_name, 'bad')
        assert not bad_members

    random_node = [random.choice(ok_nodes)]
    result = patt.exec_script (nodes=random_node, src="./dscripts/d10.etcd.sh",
                                args=['check'], sudo=True)
    for r in result:
        logger.warn ("hostname: {}".format(r.hostname))
        return ("\n{}".format (r.out))
        logger.warn ("error: {}".format (r.error))

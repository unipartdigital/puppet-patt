#!/usr/bin/env python3

import patt
import patt_syst
import patt_etcd
import patt_postgres
import patt_patroni
import patt_haproxy
import logging
from logging.handlers import TimedRotatingFileHandler
import file_lock as fl

import secrets
import string
import argparse
import yaml
import sys
import os
from pprint import pformat

logger = logging.getLogger('patt_cli')

class Config(object):
    def __init__(self):
        self.add_repo = None
        self.cluster_name = None
        self.vol_size_etcd = None
        self.vol_size_pgsql = None
        self.etcd_peers = None
        self.floating_ip = None
        self.haproxy_peers = None
        self.haproxy_template_file = None
        self.log_file = None
        self.loglevel = None
        self.lock_dir = None
        self.nodes = None
        self.patroni_release = None
        self.patroni_template_file = None
        self.postgres_peers = None
        self.postgres_release = None
        self.postgres_parameters = None
        self.ssh_keyfile = None
        self.ssh_login = None
        self.pg_master_exec = None
        self.create_role = None
        self.create_database = None
        self.gc_cron_df_pc = 50
        self.gc_cron_target = "/etc/cron.hourly/postgres-gc.sh"

    def from_argparse_cli(self, args):
        for a in args._get_kwargs():
            if a[0] in self.__dict__.keys():
                setattr(self, a[0], a[1])

    def to_yaml(self):
        result = yaml.dump(self)
        print (result.replace("!!python/object", "#!!python/object"))
        sys.exit(0)

    def from_yaml_file(self, yaml_file):
        result=None
        with open(yaml_file, 'r') as f:
            try:
                result=yaml.safe_load(f)
                for k in result.keys():
                    if k in self.__dict__.keys():
                        setattr(self, k, result[k])
            except yaml.YAMLError as e:
                print(str(e), file=sys.stderr)
                raise
            except:
                raise

def progress_bar (current, total, pre="Progress", post="Complete", decimals = 1, length = 100, fill = '█'):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (current / float(total)))
    filledLength = int(length * current // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (pre, bar, percent, post), end = '\r')
    if current == total:
        print()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='interface')

    yml = subparsers.add_parser('yaml')
    yml.add_argument('-f','--yaml_config_file', help='config file', required=True)

    cli = subparsers.add_parser('cli')
    cli.add_argument('-n','--nodes', action='append', help='nodes name or address', required=True)
    cli.add_argument('-l','--ssh_login', help='default ssh login', required=False)
    cli.add_argument('-k','--ssh_keyfile', help='default ssh keyfile', required=False)
    cli.add_argument('-c','--cluster_name', help='cluster name', required=True)
    cli.add_argument('-e','--etcd_peers', action='append', help='etcd peers', required=False)

    cli.add_argument('-p','--postgres_peers', action='append', help='postgres peers', required=False)
    cli.add_argument('-r','--postgres_release', help='postgres release version 11|12|13', default="13", required=False)
    cli.add_argument('-pp','--postgres_parameters', help='list of configuration settings for Postgres', default=[""], required=False)

    cli.add_argument('--patroni_release', help='patroni release version', default="2.1", required=False)
    cli.add_argument('-t','--patroni_template_file', help='patroni template file', required=False)

    cli.add_argument('-hp', '--haproxy_peers', help='haproxy peers', required=False)
    cli.add_argument('-ht', '--haproxy_template_file', help='haproxy template file', required=False)
    cli.add_argument('-v', '--verbose', action="store_const", dest="loglevel", const=logging.INFO, default=logging.ERROR)
    cli.add_argument('-vv', '--debug', action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.ERROR)
    cli.add_argument('--log_file', help="log file (full path)", required=False)
    cli.add_argument('--floating_ip', action='append', help="IP addresses hold by the primary node", required=False)
    cli.add_argument('--add-repo', help="add (and enable) the repo from the specified URL", action='append', required=False,
                        default=["https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo"])
    cli.add_argument('--yaml_dump', help="dump the cli options in yaml format", action='store_true', required=False)
    cli.add_argument('--pg_master_exec', help="script list to exec on master as postgres, could be local or remote)", action='append', required=False, default=[])
    cli.add_argument('--lock_dir', help='lock directory', required=False, default="/dev/shm")

    args = parser.parse_args()
    if args.interface == 'cli':
        cfg.from_argparse_cli (args)
        if args.yaml_dump:
            cfg.to_yaml()
    elif args.interface == 'yaml':
        cfg.from_yaml_file (args.yaml_config_file)
    else:
        parser.print_help()
        raise ValueError

    if cfg.log_file:
        log_file = cfg.log_file
    else:
        log_file = "/tmp/{}.log".format (cfg.cluster_name)

    if cfg.lock_dir:
        lock_filename = cfg.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
    else:
        lock_filename = '/dev/shm/' + os.path.basename (__file__).split('.')[0] + '.lock'

    lock = fl.file_lock(lock_filename)
    with lock:
        time_logger_handler = TimedRotatingFileHandler(filename=log_file, when='D', # 'H' Hours 'D' Days
                                                       interval=1, backupCount=0, encoding=None, utc=False)

        logging.basicConfig(level=cfg.loglevel,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            handlers=[time_logger_handler])

        ssh_login = None
        if cfg.ssh_login:
            ssh_login = cfg.ssh_login

        nodes = patt.to_nodes (cfg.nodes, ssh_login, cfg.ssh_keyfile)

        if cfg.etcd_peers:
            etcd_peers = patt.to_nodes (cfg.etcd_peers, ssh_login, cfg.ssh_keyfile)
        else:
            etcd_peers = nodes

        if cfg.postgres_peers:
            postgres_peers = patt.to_nodes (cfg.postgres_peers, ssh_login, cfg.ssh_keyfile)
        else:
            postgres_peers=nodes

        if cfg.haproxy_peers:
            haproxy_peers = patt.to_nodes (cfg.haproxy_peers, ssh_login, cfg.ssh_keyfile)
        else:
            haproxy_peers=nodes

        progress_bar (1, 14)

        # Peer check
        for p in [etcd_peers, postgres_peers, haproxy_peers]:
            for n in patt.check_priv(p):
                assert (n.sudo == True)
                patt.host_id(p)
                patt.host_ip_aliases(p)
        patt.check_dup_id ([p for p in etcd_peers])
        patt.check_dup_id ([p for p in postgres_peers])
        patt.check_dup_id ([p for p in haproxy_peers])

        logger.info ("cluster name   : {}".format(cfg.cluster_name))
        logger.info ("cluster nodes  : {}".format([(n.hostname, n.ip_aliases) for n in nodes]))
        logger.info ("etcd_peers     : {}".format([(n.hostname, n.id, n.ip_aliases) for n in etcd_peers]))
        logger.info ("postgres_peers : {}".format(
            [(n.hostname, n.id, n.ip_aliases) for n in postgres_peers]))
        if cfg.haproxy_template_file:
            logger.info ("haproxy_peers  : {}".format([(n.hostname, n.id) for n in haproxy_peers]))

        progress_bar (2, 14)

        if cfg.add_repo:
            patt_syst.add_repo (repo_url=cfg.add_repo, nodes=etcd_peers)

        patt_syst.nftables_configure (cluster_name=cfg.cluster_name,
                                      template_src='./config/firewall.nft',
                                      config_file_target='/etc/nftables/postgres_patroni.nft',
                                      patroni_peers=postgres_peers,
                                      etcd_peers=etcd_peers,
                                      haproxy_peers=haproxy_peers,
                                      postgres_clients=["::0/0"])
        progress_bar (3, 14)

        if cfg.vol_size_etcd:
            patt_syst.disk_init (etcd_peers, mnt="/var/lib/etcd", vol_size=cfg.vol_size_etcd)

        if cfg.vol_size_pgsql:
            patt_syst.disk_init (postgres_peers, mnt="/var/lib/pgsql", vol_size=cfg.vol_size_pgsql)

        progress_bar (4, 14)

        etcd_report = patt_etcd.etcd_init(cfg.cluster_name, etcd_peers)

        progress_bar (5, 14)

        patt_syst.tuned_postgresql (postgres_peers)

        progress_bar (5, 14)

        patt_postgres.postgres_init(cfg.postgres_release, postgres_peers)

        progress_bar (5, 14)

        patt_postgres.postgres_ssl_cert(cfg.cluster_name, nodes=postgres_peers)

        cert_users = [i['name'] for i in cfg.create_role if 'name' in i]
        patt_postgres.postgres_ssl_user_cert(cfg.cluster_name, user_names=cert_users)

        progress_bar (6, 14)

        patt_patroni.floating_ip_init(nodes=postgres_peers)

        progress_bar (7, 14)

        patt_patroni.floating_ip_build(nodes=postgres_peers)

        progress_bar (8, 14)

        if cfg.floating_ip:
            patt_patroni.floating_ip_enable(nodes=postgres_peers, floating_ips=cfg.floating_ip)

            progress_bar (9, 14)

        patt_patroni.patroni_init(cfg.postgres_release, cfg.patroni_release, postgres_peers)

        progress_bar (10, 14)

        if cfg.patroni_template_file:

            cluster_info = patt_patroni.get_cluster_info(nodes=postgres_peers)
            host=''
            if 'members' in cluster_info:
                for m in cluster_info['members']:
                    if 'role' in m and ( m['role'] == 'leader' or m['role'] == 'sync_standby'):
                        host = m['host']
                        if m['state'] == 'running': break
            p = [x for x in postgres_peers if x.hostname == host or host in x.ip_aliases]

            pass_dict = {}
            if p:
                pass_dict = patt_patroni.get_sys_users (p)
            else:
                for u in ['replication', 'superuser', 'rewind']:
                    s = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(64))
                    pass_dict[u] = s

            patt_patroni.patroni_configure(postgres_version=cfg.postgres_release,
                                           cluster_name=cfg.cluster_name,
                                           template_src=cfg.patroni_template_file,
                                           nodes=postgres_peers,
                                           etcd_peers=etcd_peers,
                                           config_file_target='/var/lib/pgsql/patroni.yaml',
                                           sysuser_pass=pass_dict,
                                           postgres_parameters=cfg.postgres_parameters,
                                           pg_hba_list=patt_patroni.cert_pg_hba_list(
                                               db_user=cfg.create_database, key_db='name', key_user='owner')
                                           )
            progress_bar (11, 14)

            patroni_report = patt_patroni.patroni_enable(cfg.postgres_release, cfg.patroni_release,
                                                         postgres_peers)
            progress_bar (12, 14)


            if cfg.haproxy_template_file:
                patt_haproxy.haproxy_configure(cluster_name=cfg.cluster_name,
                                               template_src=cfg.haproxy_template_file,
                                               nodes=haproxy_peers,
                                               postgres_nodes=postgres_peers,
                                               config_file_target='/etc/haproxy/haproxy.cfg')
                progress_bar (13, 14)

            progress_bar (14, 14)

            if postgres_peers:
                postgres_leader = patt_patroni.get_leader (postgres_peers)
                if cfg.create_role:
                    for i in cfg.create_role:
                        role_options = i['options'] if 'options' in i else []
                        patt_postgres.postgres_create_role(postgres_leader, i['name'], role_options)

                if cfg.create_database:
                    for i in cfg.create_database:
                        patt_postgres.postgres_create_database(postgres_leader, i['name'], i['owner'])

                if cfg.pg_master_exec:
                    for s in cfg.pg_master_exec:
                        patt_postgres.postgres_exec(postgres_leader, s)

            patt_postgres.postgres_gc_cron(nodes=postgres_peers,
                                           vaccum_full_df_percent=cfg.gc_cron_df_pc,
                                           target=cfg.gc_cron_target,
                                           postgres_version=cfg.postgres_release)

            print ("\nEtcd Cluster\n{}".format(etcd_report))
            logger.info ("Etcd Cluster {}".format(etcd_report))
            if cfg.patroni_template_file:
                patroni_cluster_info = patt_patroni.get_cluster_info(postgres_peers)
                print ("\nPostgres Cluster\n{}".format(pformat(patroni_cluster_info)))
                logger.info ("Postgres Cluster\n{}".format(pformat(patroni_cluster_info)))

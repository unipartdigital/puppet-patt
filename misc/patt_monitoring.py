#!/usr/bin/python3

import yaml
import requests
import ipaddress
import time
from pprint import pformat
import sqlite3
import os

def _ipv6_nri_split (nri):
    (login, s, hostname) = nri.rpartition('@')
    t1=hostname.find('[')
    t2=hostname.find(']')
    port=''
    if t1 >= 0 and t2 >= 0:
        port="".join([n for n in hostname[t2+2:] if hostname[t2+1] == ':'])
        hostname=hostname[t1+1:t2]
    elif len ([n for n in hostname if n == ':']) == 1:
        t1=hostname.find(':')
        port=hostname[t1 + 1:]
        hostname=hostname[:t1+1]
    return (login, hostname, port)

def pp_string(s):
    return pformat(s)

class Gconfig:
    pass

class PersistenceSQL3(object):
    def __init__(self, database):
        self.sql3 = sqlite3.connect(database=database)
    def __enter__(self):
        return self.sql3
    def __exit__(self, type, value, traceback):
        self.sql3.close()

class ClusterService:

    cluster_keys = ['cluster_name', 'etcd_peers', 'postgres_peers']
    # subset of class Config(object) from patt_cli

    def load_cluster_config(self):
        with open(self.cluster_config, 'r') as f:
            try:
                result=yaml.safe_load(f)
                for k in result.keys():
                    if k in ClusterService.cluster_keys:
                        setattr(Gconfig, k, result[k])
            except yaml.YAMLError as e:
                print(str(e), file=sys.stderr)
                raise
            except:
                raise

    def __init__(self,
                 cluster_config="/usr/local/etc/cluster_config.yaml"):
        self.cluster_config=cluster_config
        for k in ClusterService.cluster_keys:
            if not hasattr(Gconfig, k):
                self.load_cluster_config()
                break
        self.etcd_peers = Gconfig.etcd_peers
        self.postgres_peers = Gconfig.postgres_peers

    def get (self, query=None, start=None, element=None, urls=[]):
        for url in urls:
            try:
                result=None
                try:
                    r = requests.get("{}/{}".format(url, query), timeout=(9.0, 10.0)) # (connect, read)
                    rj = r.json()
                except requests.exceptions.ConnectionError:
                    continue
                except:
                    raise
                else:
                    if start and start in rj:
                        if element:
                            result = [c[element] for c in rj[start] if element in c]
                            assert isinstance(result, list)
                    else:
                        result = rj
            except TimeoutError as te:
                continue
            except AssertionError as e:
                continue
            except:
                raise
            else:
                return result

    def http_normalize_url(self, service_port, peers=[]):
        result=[]
        for n in peers:
            (login, hostname, port) = _ipv6_nri_split (n)
            if ipaddress.IPv6Address(hostname):
                tmp = "[{}]:{}".format (n, service_port)
            else:
                tmp = "[{}]:{}".format (n, service_port)
            if tmp.startswith('http://') or tmp.startswith('https://'):
                result.append(tmp)
            else:
                result.append("http://" + tmp)
                result.append("https://" + tmp)
        return result

class EtcdService(ClusterService):

    def __init__(self, init_urls=[]):
        super().__init__()
        if self.etcd_peers:
            self.init_urls = self.etcd_peers
        self.init_urls = self.http_normalize_url (2379, self.init_urls)

    def get_client_urls (self):
        return [n[0] for n in self.get ('v2/members', 'members', 'clientURLs', self.init_urls)]

    def node_health (self, client_urls=[]):
        for c in client_urls:
            result=False
            try:
                r = requests.get("{}/health".format(c), timeout=(9.0, 10.0)) # (connect, read)
                rj = r.json()
            except TimeoutError as te:
                continue
            except requests.exceptions.ConnectionError:
                continue
            except:
                raise
            else:
                if 'health' in rj:
                    result = rj['health'] == "true"
            return result

    def cluster_health(self):
        cluster_client_urls = self.get_client_urls()
        return [(c, self.node_health ([c])) for c in cluster_client_urls]

    def is_healthy(self):
        clth = self.cluster_health()
        return all([c[1] for c in clth]) and len (clth) > 0

class PatroniService(ClusterService):

    class Info(object):
        pass

    def _to_attr (self, e = {}):
        info = PatroniService.Info()
        if e is None: return
        for k in e.keys():
            setattr(info, k, e[k])
        return info

    def __init__(self, init_urls=[], max_time_elapsed_since_replayed=10):
        super().__init__()
        if self.postgres_peers:
            self.init_urls = self.postgres_peers
        self.init_urls = self.http_normalize_url (8008, self.init_urls)
        self.max_time_elapsed_since_replayed = max_time_elapsed_since_replayed

    def _get_api_url(self):
        return self.get ('cluster', 'members', 'api_url', self.init_urls)

    def _get_info(self, url):
        return [self.get ('', None, None, [n]) for n in url]

    def get_info(self):
        self.info = ([self._to_attr(i) for i in self._get_info(self._get_api_url())])
        try:
            self.info = sorted(self.info, key=lambda peer: peer.role)
        except AttributeError:
            pass
        return self.info

    def has_master(self):
        if not self.info:
            self.get_info
        return any([n.role == "master" and n.state == "running"
                    for n in self.info if hasattr(n, 'role')])

    def has_replica(self):
        if not self.info:
            self.get_info
        return any([n.role == "replica" and n.state == "running" for n in self.info if hasattr(n, 'role')])

    def match_config(self):
        if not self.info:
            self.get_info
        return len (self.postgres_peers) == len(self.info)

    def master_xlog_location(self):
        if not self.info:
            self.get_info
        return [n.xlog['location'] for n in self.info
                if hasattr(n, 'role') and n.role == 'master' and 'location' in n.xlog][0]

    def replica_received_replayed (self):
        if not self.info:
            self.get_info
        return [(n.xlog['received_location'], n.xlog['replayed_location'], n.xlog['replayed_timestamp'])
                for n in self.info if
                hasattr(n, 'xlog') and n.role == 'replica' and
                'received_location' and 'replayed_location' in n.xlog]

    def replica_received_replayed_delta(self):
        mxlog = self.master_xlog_location()
        now = time.gmtime()
        tn=time.mktime(now)
        t0=time.mktime(time.gmtime(0))
        def time_or_zero(stamp):
            if stamp:
                return time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S.%f %Z"))
            return t0

        return [(mxlog - n[0],
                 (n[0] - n[1]),
                 tn - time_or_zero(n[2]))
                for n in self.replica_received_replayed()]

    def replica_received_replayed_delta_ok(self):
        rdlt = self.replica_received_replayed_delta()
        result = [n[1] == 0 or (n[0] == 0 or n[2] < self.max_time_elapsed_since_replayed) for n in rdlt]
        return all(result) and bool(result)

    def timeline_match(self):
        if not self.info:
            self.get_info
        return all([n.timeline == self.info[0].timeline for n in self.info if
                hasattr(self.info[0], 'timeline') and hasattr(n, 'timeline')])

    def dump(self):
        result=[pp_string(vars(i)) for i in self.info if hasattr(i, '__dict__')]
        return "\n\n".join(result)

    """
    take a reply list and return the first values found/
    """
    def to_tuple (self, l):
        for n in l:
            if n: return n

    """
    """
    def db_create (self, database="/var/tmp/patt_monitoring.sql3"):
        with PersistenceSQL3(database=database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                cur.execute("""create table if not exists replication_log (
                id integer primary key, received integer, replayed integer, rstamp integer);
                """)
                cur.execute(
                    "select count (id) from replication_log;")
                r = cur.fetchone()
                if r[0] < 3:  # initialize with 2 dummy rows
                    for i in [1, 2]:
                        cur.execute(
                            "insert into replication_log(received, replayed, rstamp ) values (0,0,0);"
                        )
            except:
                raise
            else:
                db3.commit()

    """
    param:
    max_keep_sample = 1000, numer of row to keep should not be too high or max_db_size may have no effect.
    max_db_size=64, when dbsize > max_db_size in KB, cleanup (delete + vacuum)
    """
    def db_cleanup (self, database="/var/tmp/patt_monitoring.sql3",
                    max_keep_sample=3000, max_db_size=64):
        if os.path.exists(database):
            db_size = os.stat(os.path.abspath(database)).st_size
            if int(db_size / 1024) < int(max_db_size): return

        with PersistenceSQL3(database=database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                cur.execute("""select (SELECT count (*) from replication_log) > ? as cleanup;""",
                            [max_keep_sample])
                r = cur.fetchone()
                if r and not bool(r["cleanup"]): return
                cur.execute("""delete from replication_log where id in
                (select id from replication_log where
                id < (select id from replication_log order by id desc limit 1)
                order by id asc limit (select (select count (*) from replication_log) - ?));""",
                            [max_keep_sample])
            except:
                raise
            else:
                db3.commit()

        with PersistenceSQL3(database=database) as db3:
            try:
                db3.isolation_level = None
                db3.execute('VACUUM')
                db3.isolation_level = ''
            except:
                raise


    def replication_health(self, database="/var/tmp/patt_monitoring.sql3"):
        mxlog = self.master_xlog_location()
        rdlt = self.to_tuple(self.replica_received_replayed())
        self.db_create()
        self.db_cleanup()
        with PersistenceSQL3(database=database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                rstamp = time.mktime(time.gmtime(0))
                if rdlt[2]:
                    rstamp = time.mktime(time.strptime(rdlt[2], "%Y-%m-%d %H:%M:%S.%f %Z"))
                cur = db3.cursor()
                cur.execute(
                    "select id, received, replayed, rstamp from replication_log order by id desc limit 1;")
                r = cur.fetchone()
                if r and (r["received"] == mxlog or r["replayed"] == mxlog):
                    # convergence to xlog reached
                    pass
                else:
                    cur.execute(
                        "insert into replication_log(received, replayed, rstamp ) values (?,?,?)",
                        (rdlt[0], rdlt[1], rstamp))
                cur.execute("""
                SELECT id, avg (received) OVER (order by id ROWS BETWEEN 7 PRECEDING AND CURRENT ROW) as
                moving_avg from replication_log where id in
                (select id from replication_log order by id DESC limit 3);
                """)
                r = cur.fetchall()
                health=False
                if len (r) >= 3:
                    health = not (r[0]["moving_avg"] == r[1]["moving_avg"] and
                                  r[0]["moving_avg"] == r[2]["moving_avg"])
            except:
                raise
            else:
                db3.commit()
                return health


if __name__ == "__main__":

    print ("+--------------+")
    print ("| Etcd Service |")
    print ("+--------------+")
    etcd=EtcdService()
    print ("EtcdService cluster is healthy: {}".format(etcd.is_healthy()))
    print ("EtcdService cluster members:\n{}".format (pp_string(etcd.cluster_health())))

    print()

    print ("+-----------------+")
    print ("| Patroni Service |")
    print ("+-----------------+")
    patroni=PatroniService()
    patroni.get_info()
    print ("patroni has master : {}".format (patroni.has_master()))
    print ("patroni has replica: {}".format (patroni.has_replica()))
    print ("patroni match config: {}".format (patroni.match_config()))
    print ("replayed delta ok: {}".format (patroni.replica_received_replayed_delta_ok()))
    print ("delta xlog received/replayed/since now: {}".format (
        patroni.replica_received_replayed_delta()))
    print ("patroni dump:\n {}".format (patroni.dump()))
    print ("timeline_ok: {}".format (patroni.timeline_match()))
    print ("replication_health: {}".format (patroni.replication_health()))

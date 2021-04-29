#!/usr/bin/python3

import yaml
import requests
import ipaddress
import pprint

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

class Gconfig:
    pass

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

class Etcd(ClusterService):

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

class Patroni(ClusterService):

    class Info(object):
        pass

    def _to_attr (self, e = {}):
        info = Patroni.Info()
        if e is None: return
        for k in e.keys():
            setattr(info, k, e[k])
        return info

    def __init__(self, init_urls=[]):
        super().__init__()
        if self.postgres_peers:
            self.init_urls = self.postgres_peers
        self.init_urls = self.http_normalize_url (8008, self.init_urls)

    def _get_api_url(self):
        return self.get ('cluster', 'members', 'api_url', self.init_urls)

    def _get_info(self, url):
        return [self.get ('', None, None, [n]) for n in url]

    def get_info(self):
        self.info = ([self._to_attr(i) for i in self._get_info(self._get_api_url())])
        return self.info

    def has_master(self):
        if not self.info:
            self.get_info
        return any([n.role == "master" and n.state == "running" for n in self.info])

    def has_replica(self):
        if not self.info:
            self.get_info
        return any([n.role == "replica" and n.state == "running" for n in self.info])

    def match_config(self):
        if not self.info:
            self.get_info
        return len (self.postgres_peers) == len(self.info)

    def dump(self):
        result=[pprint.pformat(vars(i)) for i in self.info]
        return "\n\n".join(result)

if __name__ == "__main__":

    print ("+------+")
    print ("| Etcd |")
    print ("+------+")
    etcd=Etcd()
    print ("Etcd cluster is healthy: {}".format(etcd.is_healthy()))
    print ("Etcd cluster members:\n{}".format (pprint.pformat(etcd.cluster_health())))

    print()

    print ("+---------+")
    print ("| Patroni |")
    print ("+---------+")
    patroni=Patroni()
    patroni.get_info()
    print ("patroni has master : {}".format (patroni.has_master()))
    print ("patroni has replica: {}".format (patroni.has_replica()))
    print ("patroni match config: {}".format (patroni.match_config()))
    print ("patroni dump:\n {}".format (patroni.dump()))

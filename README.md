# Puppet-Patt

## Deploy replicated PostgreSQL cluster managed by Patroni:

## Usage with Puppet

* make the module and move it into your puppet server
* or clone the puppet git branch

```
make patt-puppet.tar.xz
```

* Define 1 nodes with a config similar to this one below.
* The 2 others nodes definition could be a symlink to the target.

```
# example with 3 monitor and 2 data nodes

 patt::cluster_name: 'patt_5281'
 patt::floating_ip:
  - '2001:db8:3c4d:15:2b3b:8a9a:1754:32eb'
 patt::nodes:
  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
  - '2001:db8:3c4d:15:f321:3eff:fe21:d83a'
 patt::etcd_peers:
  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
  - '2001:db8:3c4d:15:f321:3eff:fe21:d83a'
  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
 patt::postgres_peers:
  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
 patt::haproxy_peers: []
 patt::log_file: '/var/log/patt/patt.log'
 patt::patt_loglevel: 10
 patt::postgres_release: '13'
 patt::patroni_release: '2.0.2'
 patt::walg_release: 'v0.2.19'
 #patt::walg_ssh_destination: 'user1@2001:db8:3c4d:15:f321:3eff:fe21:d83a'
 patt::add_repo:
   - 'https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo'
 patt::haproxy_template_file: ''
 patt::patroni_template_file: 'config/postgres-ipv6.yaml'
 patt::ssh_keyfile: ''
 patt::ssh_login: ''
 patt::vol_size_walg: '16G'
 patt::vol_size_etcd: '2G'
 patt::vol_size_pgsql: '8G'
 #patt::vol_size_pgsql_temp: 10G

 patt::gc_cron_df_pc: '80'
 patt::gc_cron_target: '/etc/cron.hourly/postgres-gc.sh'
 patt::pg_create_role:
   - {name: example_user, options: ["LOGIN", "PASSWORD ''SCRAM-SHA-256$4096:1AUcFsTpygXKdif7BePuHg==$wKlf3/HEv+n6KQHCAxG17U963IImAJr5hMCxmO97BqM=:MOXFOHc1jgDcRhVZZgJaPzZrtqDPUnOdBGSf7ygLWEA=''"]}
 patt::pg_create_database:
   - {name: example_db, owner: example_user}

 ## python3 misc/pg_auth-scram-helper.py -p SeCrEtPasSwOrD

 patt::installer_ssh_id_pub: >
     ENC[PKCS7,MIIEbQYJKoZIhvcNAQcDoIIEXjCCBFoCAQAxggEhMIIBHQIBADAFMAACAQEw...]

 patt::installer_ssh_id_priv: ENC[PKCS7,MIIOvQYJKo...]

# puppet/modules/patt/ssh-keys/hiera-helper-ssh-id.sh

 patt::pg_root_crt: ENC[PKCS7,MIIJjQYS7,MDFosJKLjn...]

 patt::pg_root_key: ENC[PKCS7,MIIOHQYJKoZIhvcNAQcD...]

# puppet/modules/patt/ssl-cert/hiera-helper-ssl-root.sh

```

* in your site definition

```
node /^patt-[1-3].novalocal/ {
  include ::profile::base
  include ::patt
}

```

## Usage without puppet

### CLI

```
make paramiko

./patt_cli.py cli -n 2001:db8:dead:beef:fe::a -n 2001:db8:dead:beef:fe::b -n 2001:db8:dead:beef:fe::c \
                -c my_cluster_name -t ./config/postgres-ipv6.yaml -l centos
```
* some options are only available via the yaml cli interface

### yaml
* the cli options can be saved in yaml format using: `--yaml_dump`
* to use a yaml configuration file: `patt_cli.py yaml -f config_file.yaml`

#### yaml config example
```
#!!python/object:__main__.Config
cluster_name: patt_5281
floating_ip:
- 2001:db8:3c4d:15:2b3b:8a9a:1754:32eb
nodes:
- 2001:db8:3c4d:15:f321:3eff:feb9:4802
- 2001:db8:3c4d:15:f321:3eff:fee0:b279
- 2001:db8:3c4d:15:f321:3eff:fe21:d83a
etcd_peers:
- 2001:db8:3c4d:15:f321:3eff:fee0:b279
- 2001:db8:3c4d:15:f321:3eff:fe21:d83a
- 2001:db8:3c4d:15:f321:3eff:feb9:4802
postgres_peers:
- 2001:db8:3c4d:15:f321:3eff:fee0:b279
- 2001:db8:3c4d:15:f321:3eff:feb9:4802
haproxy_peers:
haproxy_template_file:
log_file: /var/log/patt/patt.log
loglevel: 10
patroni_release: 2.0.2
patroni_template_file: config/postgres-ipv6.yaml
postgres_parameters:
postgres_release: 13
walg_release: v0.2.19
#walg_ssh_destination: 'user1@2001:db8:3c4d:15:f321:3eff:fe21:d83a'
add_repo:
- https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo
ssh_keyfile:
ssh_login:
create_role:
- {name: example_user, options: [LOGIN, PASSWORD ''SCRAM-SHA-256$4096:1AUcFsTpygXKdif7BePuHg==$wKlf3/HEv+n6KQHCAxG17U963IImAJr5hMCxmO97BqM=:MOXFOHc1jgDcRhVZZgJaPzZrtqDPUnOdBGSf7ygLWEA='']}
create_database:
- {name: example_db, owner: example_user}
vol_size_walg: 16G
vol_size_etcd: 2G
vol_size_pgsql: 8G
#vol_size_pgsql_temp: 10G
gc_cron_df_pc: 80
gc_cron_target: /etc/cron.hourly/postgres-gc.sh

```

## Notes

### Puppet Module
* If ssh id and ssl root cert are not set then they will be generated in `/dev/shm/` on the puppet server.

### Network
* IPv6 only.

### SSH
* Any node definition accept the form 'username@[IPV6]:PORT', username@IPV6, IPV6.

### OS
* Should work with:
** CentOS Linux 8
** Debian GNU/Linux 10
** Ubuntu 20.04 LTS

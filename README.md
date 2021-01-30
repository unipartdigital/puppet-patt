# Puppet-Patt

## Deploy replicated PostgreSQL cluster managed by Patroni:

## Usage with Puppet

* make the module and move it into your puppet server

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
 patt::patroni_release: '2.0.1'
 patt::add_repo:
   - 'https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo'
 patt::haproxy_template_file: ''
 patt::patroni_template_file: 'config/postgres-ipv6.yaml'
 patt::ssh_keyfile: ''
 patt::ssh_login: ''
 patt::vol_size_etcd: '2G'
 patt::vol_size_pgsql: '8G'
 patt::gc_cron_df_pc: '80'
 patt::gc_cron_target: '/etc/cron.hourly/postgres-gc.sh'
 patt::pg_create_role:
   - {name: example_user, options: ["LOGIN", "PASSWORD ''md5fff64d4f930006fe343c924f6c32157e''"]}
 patt::pg_create_database:
   - {name: example_db, owner: example_user}


 # echo -n "md5" | echo -n "SeCrEtPasSwOrDexample_user" | md5sum

 installer_ssh_id_pub: >
     ENC[PKCS7,MIIEbQYJKoZIhvcNAQcDoIIEXjCCBFoCAQAxggEhMIIBHQIBADAFMAACAQEw...]

 installer_ssh_id_priv: ENC[PKCS7,MIIOvQYJKo...]

# puppet/modules/patt/ssh-keys/hiera-helper-ssh-id.sh

 pg_root_crt: ENC[PKCS7,MIIJjQYS7,MDFosJKLjn...]

 pg_root_key: ENC[PKCS7,MIIOHQYJKoZIhvcNAQcD...]

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
* cli options can saved in a yaml config file using `--yaml_dump`
* it can be reused as `patt_cli.py yaml -f config_file.yaml`

#### yaml config example
```
#!!python/object:__main__.Config
cluster_name: patt_5181
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
patroni_release: 2.0.1
patroni_template_file: config/postgres-ipv6.yaml
postgres_parameters:
postgres_release: 13
add_repo:
- https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo
ssh_keyfile:
ssh_login:
create_role:
- {name: example_user, options: [LOGIN, PASSWORD ''md5fff64d4f930006fe343c924f6c32157e'']}
create_database:
- {name: example_db, owner: example_user}
vol_size_etcd: 2G
vol_size_pgsql: 8G
gc_cron_df_pc: 80
gc_cron_target: /etc/cron.hourly/postgres-gc.sh

```

## Note
* with the puppet module if ssh id and ssl root cert are not set. It will be generated in `/dev/shm/` on the puppet server.
* we are soon in 2021 and puppet-patt works in ipv6 only.
* RHEL centric, tested on centos8

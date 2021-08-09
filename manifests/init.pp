# main interface point with Puppet.
# If possible, make the main class the only parameterized class in your module.

class patt (
 String                  $cluster_name,
 Optional[Array[String]] $add_repo = [],
 Optional[Array[String]] $etcd_peers,
 Array[String]           $floating_ip,
 Optional[Array[String]] $haproxy_peers = [],
 Optional[String]        $haproxy_template_file = '',
 Optional[String]        $log_file,
 Optional[Integer]       $patt_loglevel,
 Array[String]           $nodes,
 Optional[String]        $patroni_release,
 Optional[String]        $patroni_template_file,
 Optional[Array[String]] $postgres_peers,
 Optional[Array[String]] $postgres_parameters = [],
 Optional[String]        $postgres_release,
 Optional[String]        $walg_release,
 Optional[String]        $walg_url = '',
 Optional[String]        $walg_sha256 = '',
 Optional[Array[Struct[{method => Enum[s3, sh],
                        # s3
                        profile => Optional[String],
                        endpoint => Optional[String],
                        region => Optional[String],
                        force_path_style => Optional[String],
                        # s3/sh
                        prefix => Optional[String],
                        # sh
                        host => Optional[String],
                        identity_file => Optional[String],
                        }]]] $walg_store = [],
 Optional[String]        $aws_credentials = '',
 Optional[String]        $ssh_keyfile = '',
 Optional[String]        $ssh_login = '',
 Optional[Array[Struct[{name => String, options => Optional[Array[String]]}]]] $pg_create_role = [],
 Optional[Array[Struct[{name => String, owner => String}]]] $pg_create_database = [],

 Optional[String]        $vol_size_walg  = '2G',
 Optional[String]        $vol_size_etcd  = '2G',
 Optional[String]        $vol_size_pgsql = '2G',
 Optional[String]        $vol_size_pgsql_temp = '0',
 # size may be increased between run but not shrinked

 Optional[String]        $install_dir='/usr/local/libexec/patt',

 Optional[String]        $installer_ssh_id_pub  = '',
 Optional[String]        $installer_ssh_id_priv = '',
 # installer ssh pub/priv Identity, if not provided RSA Identity will be generated

 Optional[String]        $pg_root_crt = '',
 Optional[String]        $pg_root_key = '',
 # PostgreSQL root certificat,  if not provided CA will be generated

 Optional[String]        $gc_cron_df_pc = '50',
 Optional[String]        $gc_cron_target = "/etc/cron.hourly/postgres-gc.sh",
 # install autovacuum cron script into patt::gc_cron_target
 # if used PGDATA disk space (in percent) > patt::gc_cron_target then
 #  run vacuum full (+analyze) otherwise run simple vacuumdb (+analyze)
 # see also 'config/postgres-gc.sh.tmpl'

 Optional[Array[String]] $network_allow_postgres_clients = ['::0/0'],
 Optional[Array[String]] $network_allow_monitoring_clients = ['::0/0'],
 # nftables allowed network clients
)
{

$iplist = split(inline_epp('<%=$facts[all_ip]%>'), " ")

if is_array($patt::etcd_peers) {
 $etcd_p = $patt::etcd_peers
}else{
 $etcd_p = $patt::nodes
}

 $is_etcd = inline_epp(@(END))
<% [$etcd_p].flatten.each |$peer| { -%>
<% $iplist.flatten.each |$i| { -%>
<% if $i == $peer { -%>
<%=$i == $peer-%>
<% } -%>
<% } -%>
<% } -%>
|- END

if is_array($patt::postgres_peers) {
 $postgres_p = $patt::postgres_peers
}else{
 $postgres_p = $patt::nodes
}

 $is_postgres = inline_epp(@(END))
<% [$postgres_p].flatten.each |$peer| { -%>
<% $iplist.flatten.each |$i| { -%>
<% if $i == $peer { -%>
<%=$i == $peer-%>
<% } -%>
<% } -%>
<% } -%>
|- END

if is_array($patt::haproxy_peers) {
 $haproxy_p = $patt::haproxy_peers
}else{
 $haproxy_p = []
}

 $is_haproxy = inline_epp(@(END))
<% [$haproxy_p].flatten.each |$peer| { -%>
<% $iplist.flatten.each |$i| { -%>
<% if $i == $peer { -%>
<%=$i == $peer-%>
<% } -%>
<% } -%>
<% } -%>
|- END

if "${patt::is_etcd}" == "true" {
 $is_peer_installer = "true"
}elsif "${patt::is_postgres}" == "true" {
 $is_peer_installer = "true"
}else{
 $is_peer_installer = "false"
}

# notify {"$iplist":
#  withpath => true,
#  }
notify {"is installer peer: ${is_peer_installer}":
 withpath => true,
 }
notify {"is etcd peer: ${is_etcd}":
 withpath => true,
 }
notify {"is postgres peer: ${is_postgres}":
 withpath => true,
 }
notify {"is haproxy peer: ${is_haproxy}":
 withpath => true,
 }

  contain patt::require
  contain patt::packages
  if "${patt::is_peer_installer}" == "true" {
   contain patt::swap
   contain patt::install
   contain patt::mount
   contain patt::config
   contain patt::service
  }
}

# example with 3 monitor and 2 data nodes
#
# patt::cluster_name: 'patt_5281'
# patt::floating_ip:
#  - '2001:db8:3c4d:15:2b3b:8a9a:1754:32eb'
# patt::nodes:
#  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
#  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
#  - '2001:db8:3c4d:15:f321:3eff:fe21:d83a'
# patt::etcd_peers:
#  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
#  - '2001:db8:3c4d:15:f321:3eff:fe21:d83a'
#  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
# patt::postgres_peers:
#  - '2001:db8:3c4d:15:f321:3eff:fee0:b279'
#  - '2001:db8:3c4d:15:f321:3eff:feb9:4802'
# patt::haproxy_peers: []
# patt::log_file: '/var/log/patt/patt.log'
# patt::patt_loglevel: 10
# patt::postgres_release: '13'
# patt::patroni_release: '2.0.1'
# patt::walg_release: 'v0.2.19'
# patt::walg_store:
#  - {method: 's3', profile: 'default' # should match ~/.aws/credential [profile]',
#     endpoint: 'http://aws.end.point:8080', prefix: 'bucket_name',
#     region: 'eu-west-2',
#     force_path_style: 'true'
#    }
#  - {method: 'sh', host: '<login default cluster_name>@[ipv6_sftp_archive_host]:<port default to 22>',
#     prefix: '',               # default cluster_name (in auto configure mode)
#     identity_file: '',        # default walg_rsa (in auto configure mode)
#    }
# patt::add_repo:
#   - 'https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo'
# patt::haproxy_template_file: ''
# patt::patroni_template_file: 'config/postgres-ipv6.yaml'
# patt::ssh_keyfile: ''
# patt::ssh_login: ''
# patt::vol_size_etcd: '2G'
# patt::vol_size_pgsql: '8G'
# patt::gc_cron_df_pc: '80'
# patt::gc_cron_target: '/etc/cron.hourly/postgres-gc.sh'
#
# patt::postgres_parameters:
#  # activate wal-g archiving
#  - archive_mode = on
#  - archive_command = /usr/local/bin/wal-g wal-push %p
#
# patt::network_allow_postgres_clients:
#  - '::0/0'
# patt::network_allow_monitoring_clients:
#  - '::0/0'
#
# patt::pg_create_role:
#   - {name: example_user, options: ["LOGIN", "PASSWORD ''SCRAM-SHA-256$4096:1AUcFsTpygXKdif7BePuHg==$wKlf3/HEv+n6KQHCAxG17U963IImAJr5hMCxmO97BqM=:MOXFOHc1jgDcRhVZZgJaPzZrtqDPUnOdBGSf7ygLWEA=''"]}
# # python3 misc/pg_auth-scram-helper.py -p SeCrEtPasSwOrD
#
# patt::pg_create_database:
#   - {name: example_db, owner: example_user}
#
#
#
# installer_ssh_id_pub: >
#     ENC[PKCS7,MIIEbQYJKoZIhvcNAQcDoIIEXjCCBFoCAQAxggEhMIIBHQIBADAFMAACAQEw...]
#
# installer_ssh_id_priv: ENC[PKCS7,MIIOvQYJKo...]
#
# pg_root_crt: ENC[PKCS7,MIIJjQYS7,MDFosJKLjn...]
#
# pg_root_key: ENC[PKCS7,MIIOHQYJKoZIhvcNAQcD...]
#
#

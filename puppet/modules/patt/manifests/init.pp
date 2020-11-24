# main interface point with Puppet.
# If possible, make the main class the only parameterized class in your module.

class patt (
 String                  $cluster_name,
 Optional[Array[String]] $add_repo,
 Optional[Array[String]] $etcd_peers,
 Array[String]           $floating_ip,
 Optional[Array[String]] $haproxy_peers,
 Optional[String]        $haproxy_template_file,
 Optional[String]        $log_file,
 Optional[Integer]       $patt_loglevel,
 Array[String]           $nodes,
 Optional[String]        $patroni_release,
 Optional[String]        $patroni_template_file,
 Optional[Array[String]] $postgres_peers,
 Optional[Array[String]] $postgres_parameters = [],
 Optional[String]        $postgres_release,
 Optional[String]        $ssh_keyfile,
 Optional[String]        $ssh_login,
 Optional[Array[Struct[{name => String, options => Optional[Array[String]]}]]] $pg_create_role = [],
 Optional[Array[Struct[{name => String, owner => String}]]] $pg_create_database = [],

 Optional[String]        $vol_size_etcd  = '2G',
 Optional[String]        $vol_size_pgsql = '2G',
 # size may be increased between run but not shrinked
)
{

  contain patt::require
  contain patt::packages
  contain patt::install
  contain patt::config
  contain patt::service
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
# patt::add_repo:
#   - 'https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo'
# patt::haproxy_template_file: ''
# patt::patroni_template_file: 'config/postgres-ipv6.yaml'
# patt::ssh_keyfile: ''
# patt::ssh_login: ''
# patt::vol_size_etcd: '2G'
# patt::vol_size_pgsql: '8G'
# patt::pg_create_role:
#   - {name: example_user, options: ["LOGIN", "PASSWORD ''md5fff64d4f930006fe343c924f6c32157e''"]}
# patt::pg_create_database:
#   - {name: example_db, owner: example_user}
#
#
# # echo -n "md5" | echo -n "SeCrEtPasSwOrDexample_user" | md5sum
#

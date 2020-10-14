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

)
{

  contain patt::require
  contain patt::packages
  contain patt::install
  contain patt::config
  contain patt::service
}

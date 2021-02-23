class patt::mount (
$postgres_home = $::osfamily ? {
  'Debian'  => '/var/lib/postgresql',
  'RedHat'  => '/var/lib/pgsql',
  default => '/var/lib/postgresql',
},
$etcd_data = "/var/lib/etcd",
)
{

 if "${is_etcd}" == "true" {
  notify {"etcd peer mount":}

  file{"${etcd_data}":
     ensure  =>  directory,
     owner   => etcd,
     group   => etcd,
     mode    => '0711',
     require => [Package["etcd"]],
  }

  $etcd_any_empty = reduce([$patt::vol_size_etcd, $etcd_data], false) |$a, $b| {
     $a or ($b == '')
  }

  unless $etcd_any_empty {
   exec{'mount_$etcd_data':
     command => "${patt::install_dir}/dscripts/data_vol.py -m ${etcd_data} -s ${patt::vol_size_etcd}",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["etcd"], File["${etcd_data}"]],
     onlyif  => '/bin/test -z `/bin/ls -A ${etcd_data}`'
   }
  }
 }

 if "${is_postgres}" == "true" {
  notify {"postgres peer mount":}

  file{"${postgres_home}":
     ensure  =>  directory,
     owner   => postgres,
     group   => postgres,
     mode    => '0711',
     require => [Package["postgresql_${patt::postgres_release}_server"]],
  }

  $psql_any_empty = reduce([$patt::vol_size_pgsql, $postgres_home], false) |$a, $b| {
     $a or ($b == '')
  }

  unless $psql_any_empty {
   exec{'mount_$postgres_home':
     command => "${patt::install_dir}/dscripts/data_vol.py -m ${postgres_home} -s ${patt::vol_size_pgsql}",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["postgresql_${patt::postgres_release}_server"], File["${postgres_home}"]],
     onlyif  => '/bin/test -z `/bin/ls -A ${postgres_home}`'
   }
  }
 }

}
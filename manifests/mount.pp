class patt::mount
(
 $postgres_home = $::osfamily ? {
   'Debian'  => '/var/lib/postgresql',
   'RedHat'  => '/var/lib/pgsql',
     default => '/var/lib/postgresql',
  },
 $etcd_data = "/var/lib/etcd",
)
{

 if "${patt::is_etcd}" == "true" {
  notify {"etcd peer mount":}
  if ($patt::vol_size_etcd) {
   $do_mount_etcd = true
  }else{
   $do_mount_etcd = false
  }

  if $do_mount_etcd {
   exec{"mount_$etcd_data":
     command => "${patt::install_dir}/dscripts/data_vol.py -m ${etcd_data} -s ${patt::vol_size_etcd}",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["etcd"]],
     onlyif  => "/bin/test `ls -CA ${etcd_data} 2> /dev/null | wc -l` == 0",
     logoutput => true,
  }
  }else{
   exec{"mount_$etcd_data":
     command => "/bin/true",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["etcd"]],
     onlyif  => "/bin/test `ls -CA ${etcd_data} 2> /dev/null | wc -l` == 0",
     logoutput => true,
    }
  }
  file{"${etcd_data}":
     ensure  => directory,
     owner   => etcd,
     group   => etcd,
     mode    => '0711',
     require => [Package["etcd"], Exec["mount_$etcd_data"]],
  }
 }

 if "${patt::is_postgres}" == "true" {
  notify {"postgres peer mount":}
  if $patt::vol_size_pgsql {
   $do_mount_postgres = true
  }else{
   $do_mount_postgres = false
  }
  if $do_mount_postgres {
   exec{"mount_$postgres_home":
     command => "${patt::install_dir}/dscripts/data_vol.py -m ${postgres_home} -s ${patt::vol_size_pgsql}",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["postgresql_${patt::postgres_release}_server"], File["${postgres_home}"]],
     onlyif  => "/bin/test `ls -CA ${postgres_home} 2> /dev/null | wc -l` == 0",
     logoutput => true,
   }
  }else{
   exec{"mount_$postgres_home":
     command => "/bin/true",
     require => [File["${patt::install_dir}/dscripts/data_vol.py"]],
     before  => [Package["postgresql_${patt::postgres_release}_server"], File["${postgres_home}"]],
     onlyif  => "/bin/test `ls -CA ${postgres_home} 2> /dev/null | wc -l` == 0",
     logoutput => true,
   }
  }
  file{"${postgres_home}":
     ensure  =>  directory,
     owner   => postgres,
     group   => postgres,
     mode    => '0711',
     require => [Package["postgresql_${patt::postgres_release}_server"], Exec["mount_$postgres_home"]],
  }
 }

}
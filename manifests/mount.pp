class patt::mount (
$postgres_home = "/var/lib/pgsql",
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
    require => [File["${patt::install_dir}/dscripts/data_vol.py"], File["${postgres_home}"]],
    before  => [File["${postgres_home}/.postgresql/"], File["${postgres_home}/.postgresql/root.crt"],
                File["${postgres_home}/.postgresql/root.key"]],
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
    require => [Package["postgresql${patt::postgres_release}-server"]],
 }

 $psql_any_empty = reduce([$patt::vol_size_pgsql, $postgres_home], false) |$a, $b| {
    $a or ($b == '')
 }

 unless $psql_any_empty {
  exec{'mount_$postgres_home':
    command => "${patt::install_dir}/dscripts/data_vol.py -m ${postgres_home} -s ${patt::vol_size_pgsql}",
    require => [File["${patt::install_dir}/dscripts/data_vol.py"], File["${postgres_home}"]],
    before  => [File["${postgres_home}/.postgresql/"], File["${postgres_home}/.postgresql/root.crt"],
                File["${postgres_home}/.postgresql/root.key"]],
    onlyif  => '/bin/test -z `/bin/ls -A ${postgres_home}`'
  }
 }
}

}
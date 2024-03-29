class patt::sslcerts(
 $ssl_cert_dir = join([module_directory('patt'), 'ssl-cert'], '/'),
 $postgres_home = $::osfamily ? {
   'Debian'  => '/var/lib/postgresql',
   'RedHat'  => '/var/lib/pgsql',
   default => '/var/lib/postgresql',
 },
)
{

if "${is_postgres}" == "true" {
 notify {"postgres peer sslcerts":}

 $is_any_empty = reduce([$patt::pg_root_crt, $patt::pg_root_key], false) |$a, $b| {
     $a or ($b == '')
 }

 if $is_any_empty {
  $ca_crt=generate("$ssl_cert_dir/00-generator.sh", "$patt::cluster_name", "root_cert")
  $ca_key=generate("$ssl_cert_dir/00-generator.sh", "$patt::cluster_name", "root_key")
 }else{
  $ca_crt=$patt::pg_root_crt
  $ca_key=$patt::pg_root_key
 }

  file{"${postgres_home}/.postgresql/":
     ensure  =>  directory,
     owner   => postgres,
     group   => postgres,
     mode    => '0700',
     require => [Package["postgresql${patt::postgres_release}-server"]],
  }

 file {"${postgres_home}/.postgresql/root.crt":
    ensure  => file,
    content => inline_epp(@(END), k => $ca_crt),
<%=$k%>
END
    owner   => root,
    group   => root,
    mode    => '0644',
    require => [Package["postgresql${patt::postgres_release}-server"], File["${postgres_home}/.postgresql/"]],
  }

  file {"${postgres_home}/.postgresql/root.key":
    ensure  => file,
    content => inline_epp(@(END), k => $ca_key),
<%=$k%>
END
    owner   => postgres,
    group   => postgres,
    mode    => '0600',
    require => [Package["postgresql${patt::postgres_release}-server"], File["${postgres_home}/.postgresql/"]],
  }
 }
}
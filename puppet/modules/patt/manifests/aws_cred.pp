class patt::aws_cred(
 $postgres_home = $::osfamily ? {
   'Debian'  => '/var/lib/postgresql',
   'RedHat'  => '/var/lib/pgsql',
   default => '/var/lib/postgresql',
 },
)
{

 if "${patt::is_postgres}" == "true" {
  notify {"postgres peer aws credentials":}


  if $patt::aws_credentials {
   file{"${postgres_home}/":
      ensure  => directory,
      owner   => postgres,
      group   => postgres,
      mode    => '0711',
      require => [Package["postgresql${patt::postgres_release}-server"]],
   }
   file{"${postgres_home}/.aws/":
      ensure  => directory,
      owner   => postgres,
      group   => postgres,
      mode    => '0700',
      require => [Package["postgresql${patt::postgres_release}-server"],
                     File["${postgres_home}/"]],
   }

   file {"${postgres_home}/.aws/credentials":
    ensure  => file,
    content => inline_epp(@(END), k => $patt::aws_credentials),
<%=$k%>
END
    owner   => postgres,
    group   => postgres,
    mode    => '0640',
    require => [Package["postgresql${patt::postgres_release}-server"],
                   File["${postgres_home}/.aws/"]],
   }
  }
 }
}

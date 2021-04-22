class patt::aws_cred(
 $postgres_home = $::osfamily ? {
   'Debian'  => '/var/lib/postgresql',
   'RedHat'  => '/var/lib/pgsql',
   default => '/var/lib/postgresql',
 },
)
{

if "${is_postgres}" == "true" {
 notify {"postgres peer aws credentials":}
 }

unless $patt::aws_credentials {
  file{"${postgres_home}/.postgresql/":
     ensure  => directory,
     owner   => postgres,
     group   => postgres,
     mode    => '0700',
     require => [Package["postgresql${patt::postgres_release}-server"]],
  }
  file{"${postgres_home}/.postgresql/.aws":
     ensure  => directory,
     owner   => postgres,
     group   => postgres,
     mode    => '0700',
     require => [Package["postgresql${patt::postgres_release}-server"],
                    File["${postgres_home}/.postgresql/"]],
  }

 file {"${postgres_home}/.postgresql/.aws/credentials":
    ensure  => file,
    content => inline_epp(@(END), k => $patt::aws_credentials),
<%=$k%>
END
    owner   => postgres,
    group   => postgres,
    mode    => '0640',
    require => [Package["postgresql${patt::postgres_release}-server"],
                   File["${postgres_home}/.postgresql/.aws"]],
  }
 }
}

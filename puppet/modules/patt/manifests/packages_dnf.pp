class patt::packages_dnf
 (
  $python_version="3.8"
 )
{

  $pkg_p=split("$python_version", '\.')
  $pv="${pkg_p[0]}${pkg_p[1]}"
  notify {"set python_version: ${python_version}":}
  notify {"set pkg python: python${pv}":}

 $base = [
  'epel-release',
  'nftables',
  'policycoreutils',
  'util-linux',
  'xfsprogs',
  'lvm2',
  'cryptsetup',
  'psmisc'
 ]

 $base_peer = [
  "python${pv}-PyYAML",
  "python${pv}-cryptography",
  "python${pv}-pip",
 ]

 $base_pg_node = [
  'gcc',
  "python${pv}-Cython",
  "python${pv}-devel",
  "python${pv}-psycopg2",
  "python${pv}-requests",
  "python3-scapy",
  ]


 $base.each|$b| {
  unless defined(Package["$b"]) {
   package { $b: ensure => 'installed' }
  }
 }


 package {"python${pv}" : ensure => 'installed'}

 if "${patt::is_peer_installer}" == "true" {
  notify {"peer installer":}
  package { "make" : ensure => 'installed' }

  exec {"python${pv}_alternative":
     command => "/sbin/alternatives --set python3 /usr/bin/python${python_version}",
     user => 'root',
     require => [Package["python${pv}"]],
     unless => ['/usr/bin/python3 --version | /usr/bin/grep -q ${python_version}'],
  }

  exec {"pip${pv}_alternative":
     command => "/sbin/alternatives --set pip3 /usr/bin/pip${python_version}",
     user => 'root',
     require => [Package["python${pv}"], Exec["python${pv}_alternative"]],
     unless => ['/usr/bin/pip3 --version | /usr/bin/grep -q "python ${python_version}"'],
  }

  $base_peer.each|$p| {
   unless defined(Package["$p"]) {
    package { $p: ensure => 'installed' , require => Exec["python${pv}_alternative"]}
   }
  }
 }

 if "${patt::is_etcd}" == "true" {
  notify {"etcd peer install":}

  Exec{'/etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo':
   command  => '/usr/bin/curl -f https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo > /etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo',
   unless => '/bin/test -f /etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo'
   }

  package {'etcd': ensure  => 'installed',
                   require => Exec['/etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo'],
                   install_only => true}
 }

 if "${patt::is_postgres}" == "true" {
  notify {"postgres peer install":}

  $base_pg_node.each|$b| {
   unless defined(Package["$b"]) {
    package { $b: ensure => 'installed' }
   }
  }

  unless defined(Package["pgdg-redhat-repo"]) {
   package{'pgdg-redhat-repo':
    provider => 'dnf',
    ensure => 'present',
    source => 'https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm',
   }
  }

  exec { 'dnf_module_disable_postgresql':
     command => "/usr/bin/dnf -qy module disable postgresql",
     require => Package['pgdg-redhat-repo'],
  }

  $pg_pkg = [
          "postgresql${patt::postgres_release}",
          "postgresql${patt::postgres_release}-server",
          "postgresql${patt::postgres_release}-contrib"
          ]

  $pg_pkg.each|$p| {
   unless defined(Package["$p"]) {
    if ($p == "postgresql${patt::postgres_release}-server") {
     package { $p: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'],
                   alias  => "postgresql_${patt::postgres_release}_server"}
    }else{
     package { $p: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'] }
    }
   }
  }
 }

 if "${patt::is_haproxy}" == "true" {
    notify {"haproxy peer install":}

    Package{'haproxy': ensure => installed}
 }

}

class patt::packages()
{

 # pre
 # needed by epel-release
 yumrepo { 'PowerTools':
   enabled  => 1,
   gpgcheck => '1',
 }

 $base = ['epel-release', 'gcc', 'make', 'nftables', 'policycoreutils', 'util-linux', 'xfsprogs']

 $pyth = ['python3', 'python3*-scapy', 'python3*-Cython', 'python3*-PyYAML', 'python3*-devel', 'python3*-pip', 'python3*-psycopg2']

 package { $base: ensure => 'installed' }
 package { $pyth: ensure => 'installed' }

 package{'pgdg-redhat-repo':
  provider => 'dnf',
  ensure => 'present',
  source => 'https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm',
 }

 exec { 'dnf_module_disable_postgresql':
    command => "/usr/bin/dnf -qy module disable postgresql",
    require => Package['pgdg-redhat-repo'],
 }

 $pg_pkg = [ "postgresql${patt::postgres_release}", "postgresql${patt::postgres_release}-server", "postgresql${patt::postgres_release}-contrib" ]
 package { $pg_pkg: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'] }

# TODO
# conditional
# 'haproxy'

}

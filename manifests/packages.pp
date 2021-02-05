class patt::packages()
{

 # pre
 # needed by epel-release
 unless defined(Yumrepo["PowerTools"]) {
  yumrepo { 'PowerTools':
    enabled  => 1,
    gpgcheck => '1',
  }
 }

 $base = ['epel-release', 'gcc', 'make', 'nftables', 'policycoreutils', 'util-linux', 'xfsprogs', 'lvm2', 'cryptsetup', 'psmisc']

 $pyth = ['python3', 'python3*-scapy', 'python3*-Cython', 'python3*-PyYAML', 'python3*-devel', 'python3*-pip', 'python3*-psycopg2']

 $base.each|$b| {
  unless defined(Package["$b"]) {
   package { $b: ensure => 'installed' }
  }
 }

 $pyth.each|$p| {
  unless defined(Package["$p"]) {
   package { $p: ensure => 'installed' }
  }
 }

 unless defined(Package["pgdg-redhat-repo"]) {
  package{'pgdg-redhat-repo':
   provider => 'dnf',
   ensure => 'present',
   source => 'https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm',
  }
 }

if "${is_etcd}" == "true" {
 notify {"etcd peer install":}
 Exec{'/etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo':
  command  => '/usr/bin/curl -f https://copr.fedorainfracloud.org/coprs/unipartdigital/pkgs/repo/epel-8/unipartdigital-pkgs-epel-8.repo > /etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo',
  unless => '/bin/test -f /etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo'
  }

 package {'etcd': ensure  => 'installed',
                  require => Exec['/etc/yum.repos.d/unipartdigital-pkgs-epel-8.repo'],
                  install_only => true}
}

if "${is_postgres}" == "true" {
 notify {"postgres peer install":}

 exec { 'dnf_module_disable_postgresql':
    command => "/usr/bin/dnf -qy module disable postgresql",
    require => Package['pgdg-redhat-repo'],
 }

 $pg_pkg = [ "postgresql${patt::postgres_release}", "postgresql${patt::postgres_release}-server", "postgresql${patt::postgres_release}-contrib" ]
 $pg_pkg.each|$p| {
  unless defined(Package["$p"]) {
   package { $p: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'] }
  }
 }
}

# # TODO
# # conditional
# # 'haproxy'

}

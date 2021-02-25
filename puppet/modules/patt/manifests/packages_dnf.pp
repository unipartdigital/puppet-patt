class patt::packages_dnf()
{

 # pre
 # CentOS-Linux-PowerTools needed by epel-release
 # unless defined(Yumrepo["CentOS-Linux-PowerTools"]) {
 #  yumrepo { 'CentOS-Linux-PowerTools':
 #    enabled  => 1,
 #    gpgcheck => '1',
 #  }
 # }

 $base = ['epel-release', 'gcc', 'make', 'nftables', 'policycoreutils', 'util-linux', 'xfsprogs', 'lvm2', 'cryptsetup', 'psmisc']

 $pyth = ['python3-scapy', 'python38-Cython', 'python38-PyYAML', 'python38-devel', 'python38-pip', 'python38-psycopg2', 'python38-cryptography', 'python38-requests']

 $base.each|$b| {
  unless defined(Package["$b"]) {
   package { $b: ensure => 'installed' }
  }
 }


 package {'python38' : ensure => 'installed'}

 exec {'python38_alternative':
    command => "/sbin/alternatives --set python3 /usr/bin/python3.8",
    user => 'root',
    require => Package['python38'],
    onlyif => ['/usr/bin/test "$(readlink -f /usr/bin/python3)" != "/usr/bin/python3.8"'],
 }


 $pyth.each|$p| {
  unless defined(Package["$p"]) {
   package { $p: ensure => 'installed' , require => Exec['python38_alternative']}
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
   if ($p == "postgresql${patt::postgres_release}-server") {
    package { $p: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'],
                  alias  => "postgresql_${patt::postgres_release}_server"}
   }else{
    package { $p: ensure => 'installed', require => Exec['dnf_module_disable_postgresql'] }
   }
  }
 }
}

# # TODO
# # conditional
# # 'haproxy'

}

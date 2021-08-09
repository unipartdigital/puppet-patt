class patt::packages_apt()
{
 include ::apt

 $base = [
  'checkpolicy',
  'cryptsetup-bin',
  'gnupg',
  'lvm2',
  'nftables',
  'policycoreutils',
  'psmisc',
  'python3',
  'selinux-basics',
  'selinux-policy-default',
  'semodule-utils',
  'tuned',
  'util-linux',
  'wget',
  'xfsprogs',
 ]

 $base.each|$b| {
  unless defined(Package["$b"]) {
   package { $b: ensure => 'installed' }
  }
 }

 $base_peer = [
  'python3-yaml',
  'python3-cryptography',
  'python3-pip',
 ]

 $base_pg_node = [
  'cython3',
  'gcc',
  'libpython3-all-dev',
  'python3-dev',
  'python3-psycopg2',
  'python3-scapy',
 ]

 if "${patt::is_peer_installer}" == "true" {
  notify {"peer installer":}
  package { "make" : ensure => 'installed' }

  $base_peer.each|$b| {
   unless defined(Package["$b"]) {
    package { $b: ensure => 'installed' }
   }
  }
 }

 if "${patt::is_etcd}" == "true" {
  notify {"etcd peer install":}

  Exec {'systemd_mask_etcd':
   command => '/bin/bash -c "cd /etc/systemd/system && ln -sf /dev/null etcd.service"',
   unless  => '/bin/test -n "$(etcd --version)"',
  # don't let dpkg start the service at first install
  }
  Package{'etcd': ensure => installed, require => [Exec['systemd_mask_etcd']]}
 }

 if "${patt::is_postgres}" == "true" {
  notify {"postgres peer install":}

  $base_pg_node.each|$b| {
   unless defined(Package["$b"]) {
    package { $b: ensure => 'installed' }
   }
  }

  $repo_release = "${facts['os']['distro']['codename']}-pgdg"
  apt::source {'pgdg':
   comment  => 'apt.postgresql.org',
   location => 'http://apt.postgresql.org/pub/repos/apt',
   release  => "$repo_release",
   repos    => 'main',
   key      => {
    source => 'https://www.postgresql.org/media/keys/ACCC4CF8.asc',
    id     => 'B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8',
   },
  }

  File{'/etc/postgresql-common/':,
   ensure => "directory",
   owner  => "root",
   group  => "root",
   mode   => '755',
  }

  File{'/etc/postgresql-common/createcluster.conf':,
   ensure  => file,
   content => inline_epp(@(END)),
create_main_cluster = false
start_conf = 'disabled'
data_directory = /dev/null
ssl = off
END
   owner   => root,
   group   => root,
   mode    => '0644',
   require => [File["/etc/postgresql-common/"]],
  }

  Package{"postgresql-${patt::postgres_release}":
   ensure => installed,
   require => [Apt::Source['pgdg'], File['/etc/postgresql-common/createcluster.conf']],
   alias  => "postgresql_${patt::postgres_release}_server",
  }

 }

 if "${patt::is_haproxy}" == "true" {
   notify {"haproxy peer install":}

   Exec {'systemd_mask_haproxy':
    command => '/bin/bash -c "cd /etc/systemd/system && ln -sf /dev/null haproxy.service"',
    unless  => '/bin/test "$(haproxy -v)"',
   # don't let dpkg start the service at first install
   }
   Package{'haproxy': ensure => installed, require => [Exec['systemd_mask_haproxy']]}
 }

}

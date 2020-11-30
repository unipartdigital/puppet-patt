class patt::require(
)
{

 user {'patt':
  comment => 'patt installer',
  home => '/home/patt',
  managehome => true,
  ensure   => present,
 }

 file { "/home/patt":
        ensure => "directory",
        owner  => "patt",
        group  => "patt",
        mode   => '711',
        require =>  [User[patt]],
 }

 file {'/etc/sudoers.d/90-patt-users':
      content => "patt ALL=(ALL) NOPASSWD:ALL",
      ensure => file,
      mode => '0640',
      owner => 'root',
      group => 'root',
      require => [User[patt]],
 }

 contain patt::sshkeys

}

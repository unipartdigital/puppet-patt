class patt::sshkeys(
 $keydir="/etc/puppetlabs/code/environments/production/modules/patt/ssh-keys"
)
{
$prv=generate("$keydir/00-generator.sh", "$patt::cluster_name", "private", "$keydir")
$pub=generate("$keydir/00-generator.sh", "$patt::cluster_name", "public" , "$keydir")

 file{"/home/patt/.ssh/":
    ensure  =>  directory,
    owner   => patt,
    group   => patt,
    mode    => '0700',
    require => [User[patt]],
 }

 file { '/home/patt/.ssh/id_rsa':
    content => $prv,
    owner   => patt,
    group   => patt,
    mode    => '0600',
    require => [User[patt], File["/home/patt/.ssh/"]],
 }

 file { '/home/patt/.ssh/authorized_keys':
    content => $pub,
    owner   => patt,
    group   => patt,
    mode    => '0600',
    require => [User[patt], File["/home/patt/.ssh/"]],
 }

 file { '/home/patt/.ssh/config':
    ensure  => file,
    owner   => patt,
    group   => patt,
    mode    => '0600',
    require => [User[patt], File["/home/patt/.ssh/"]],
 }

}
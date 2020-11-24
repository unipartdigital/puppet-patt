class patt::sshkeys(
 $base_dir="/etc/puppetlabs/code/environments/production/modules/patt/ssh-keys",
 $key_dir="/dev/shm/patt",
 # don't store keys across reboot
)
{

$is_any_empty = reduce([$patt::installer_ssh_id_pub, $patt::installer_ssh_id_priv], false) |$a, $b| {
    $a or ($b == '')
}

if $is_any_empty {
 $prv=generate("$base_dir/00-generator.sh", "$patt::cluster_name", "private", "$key_dir")
 $pub=generate("$base_dir/00-generator.sh", "$patt::cluster_name", "public" , "$key_dir")
}else{
 $prv=$patt::installer_ssh_id_priv
 $pub=$patt::installer_ssh_id_pub
}

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
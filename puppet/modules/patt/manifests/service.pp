class patt::service (
)
{

 require patt::sslcerts

 file{"/var/log/patt/":
    ensure  =>  directory,
    owner   => patt,
    group   => patt,
    mode    => '0754',
    require => [User[patt]],
 }
 exec { 'patt_installer':
    command => "$patt::install::install_dir/patt_cli.py yaml -f /usr/local/etc/cluster_config.yaml",
    user => 'patt',
    environment => ['HOME=/home/patt'],
    require => File["/var/log/patt/"],
 }
}
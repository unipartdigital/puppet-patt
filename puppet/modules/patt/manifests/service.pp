class patt::service (
)
{

 require patt::aws_cred
 require patt::sslcerts
 require patt::packages
 require patt::install

 file{"/var/log/patt/":
    ensure  =>  directory,
    owner   => patt,
    group   => patt,
    mode    => '0754',
    require => [User[patt]],
 }
 exec { 'patt_installer':
    command => "/bin/echo $patt::install_dir/patt_cli.py yaml -f /usr/local/etc/cluster_config.yaml | su - patt",
    user => 'root',
    environment => ['HOME=/home/patt'],
    require => File["/var/log/patt/"],
 }
}

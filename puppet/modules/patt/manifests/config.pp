class patt::config (
){
 file { '/usr/local/etc/cluster_config.yaml':
    content => epp('patt/patt.yaml'),
    owner   => root,
    group   => root,
    mode    => '0644',
 }

 contain patt::sslcerts

}

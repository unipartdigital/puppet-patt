class patt::install (
)
{

 $base_install_dir = dirname ("$patt::install_dir")

 file {
  "$base_install_dir":
   ensure => 'directory',
   owner => 'root',
   group => 'root',
   mode  => '0775',
 }

 file {
  "$patt::install_dir":
   ensure => 'directory',
   source => 'puppet:///modules/patt/patt',
   recurse => 'remote',
   path => $patt::install_dir,
   owner => 'root',
   group => 'root',
   mode  => '0644',
  require => [File["$base_install_dir"]]
 }

 file {
  "${patt::install_dir}/patt_cli.py":
   ensure => 'file',
   source => 'puppet:///modules/patt/patt/patt_cli.py',
   recurse => 'false',
   path => "${patt::install_dir}/patt_cli.py",
   owner => 'root',
   group => 'root',
   mode  => '0755',
 }

 file {
  "${patt::install_dir}/dscripts/data_vol.py":
   ensure => 'file',
   source => 'puppet:///modules/patt/patt/dscripts/data_vol.py',
   recurse => 'false',
   path => "${patt::install_dir}/dscripts/data_vol.py",
   owner => 'root',
   group => 'root',
   mode  => '0755',
   require => [File["$patt::install_dir"]]
 }

 exec { 'make_dep':
    command => "/bin/echo 'make -C ${patt::install_dir} paramiko' | su - patt",
    user => 'root',
    require =>  [User[patt]],
 }

}

class patt::install (
)
{
 file {
  "$patt::install_dir":
   ensure => 'directory',
   source => 'puppet:///modules/patt/patt',
   recurse => 'remote',
   path => $patt::install_dir,
   owner => 'root',
   group => 'root',
   mode  => '0644',
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
    command => "/usr/bin/python3 -c \"import paramiko;import sys; paramiko.__version__[:3] >= str('2.7') or sys.exit(1)\" || /usr/bin/pip3 install -U --user paramiko",
    user => 'patt',
    environment => ['HOME=/home/patt'],
    require =>  [User[patt]],
 }

}

class patt::packages()
{

 case $facts['osfamily']{
  'Debian':{
    contain patt::packages_apt
  }
  'RedHat':{
    contain patt::packages_dnf
  }
   default:{
    notify {"warning using default package class: $facts['osfamily']":
    withpath => true,
   }
  }
 }

}

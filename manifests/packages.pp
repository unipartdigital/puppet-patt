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
  }
 }


}

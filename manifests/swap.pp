class patt::swap ()
{

$mem_syst = $facts['memory']['system']['total_bytes']
if has_key($facts['memory'], 'swap') {
 $mem_swap = $facts['memory']['swap']['total_bytes']
}else{
 $mem_swap = 0
}

 if ($mem_syst <= 2147483648) {      # <2GIB
  $exp_swap = $mem_syst * 3
 }elsif ($mem_syst <= 4294967296) {  # <4GIB
  $exp_swap = $mem_syst * 2
 }elsif ($mem_syst <= 8589934592) {  # <8GIB
  $exp_swap = $mem_syst * 1 + 2147483648
 }elsif ($mem_syst <= 17179869184) { # <16GIB
  $exp_swap = $mem_syst / 2 + 4294967296
 }else{
  $exp_swap = $mem_syst / 4 + 2147483648
 }

 if ($mem_swap < $exp_swap) {
  Exec { '/var/cache/swap.0':
   command => "/bin/dd if=/dev/zero bs=1M count=$(($exp_swap / 1024 / 1024)) of=/var/cache/swap.0",
   onlyif  => "/bin/test ! -f /var/cache/swap.0",
  }

  Exec { 'mkswap_/var/cache/swap.0':
   command => "/bin/chmod 600 /var/cache/swap.0 && /sbin/mkswap /var/cache/swap.0",
   onlyif  => "/bin/file /var/cache/swap.0 | grep -q -v ' swap '",
   require => [Exec['/var/cache/swap.0']],
  }

  Exec { 'swapon_/var/cache/swap.0':
   command => "/bin/chmod 600 /var/cache/swap.0 && /sbin/swapon /var/cache/swap.0",
   onlyif  => "/bin/test \
              `/sbin/swapon --noheadings --show=Name | grep -q '^/var/cache/swap.0' ; echo $?` != 0",
   require => [Exec['mkswap_/var/cache/swap.0']],
  }
 }
}

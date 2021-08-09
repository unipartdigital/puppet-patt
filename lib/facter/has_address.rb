#has_address.rb

Facter.add('all_ip') do
  setcode do
    ips = Facter::Core::Execution.execute('/sbin/ip -br -o addr show scope global | \
sed -e "s/^.*\(UP\|UNKNOWN\) *//" | \
tr "\n" " " | \
sed -e "s|\/[0-9]\+||g"')
  end
end

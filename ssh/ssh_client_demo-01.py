
import sys, os
import ssh_client

if len(sys.argv) < 2:
    raise ValueError ("usage %s destination" % sys.argv[0])

c1 = ssh_client.ssh_client (sys.argv[1])

sftp = c1.new_sftp()
my_name = os.path.basename(__file__)
sftp.put (my_name, '/tmp/' + my_name)
sftp.get ('/tmp/' + my_name, '/tmp/' + my_name)

c1.interactive_shell()

c1.close()

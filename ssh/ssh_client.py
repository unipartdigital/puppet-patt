"""
ssh_client a high level paramiko http://www.paramiko.org/ wrapper

ref: https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py

exec command return a CmdResp object
with the following attribute
            hostname <string>
            stdin    <fd wb>
            stdout   <fd r>
            stderr   <fd r>
            pid      <int>
            status   <int>
"""

import base64
import getpass
import os
import socket
import sys
import traceback
from paramiko.py3compat import input

import paramiko

try:
    import interactive
except ImportError:
    from . import interactive


class ssh_client:

    class CmdResp:
        def __init__(self, hostname=None):
            self.hostname = ""
            self.stdin = -1
            self.stdout = -1
            self.stderr = -1
            self.pid = -1
            self.status = -1

    """
    mandatory param:
    - destination: hostname or ip address
    """
    def __init__(self, destination, login=None, password=None, port=22, log_file=None):
        (l,s,h) = destination.rpartition('@')
        self.hostname = h
        if login:
            self.username = login
        elif l != '':
            self.username = l
        else:
            self.username = getpass.getuser()
        self.port = port
        self.log_file = log_file
        self.password = password
        self.client=None
        self.UseGSSAPI = (
            paramiko.GSS_AUTH_AVAILABLE
        )  # enable "gssapi-with-mic" authentication, if supported by your python installation
        self.DoGSSAPIKeyExchange = (
            paramiko.GSS_AUTH_AVAILABLE
        )  # enable "gssapi-kex" key exchange, if supported by your python installation


    def open(self, timeout=None):
        if self.client:
            if self.client._transport is not None:
                return
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
            print("Connecting:{}".format(self.hostname))
            if not self.UseGSSAPI and not self.DoGSSAPIKeyExchange:
                self.client.connect(self.hostname, self.port, self.username, self.password, timeout=timeout)
            else:
                try:
                    self.client.connect(
                        self.hostname,
                        self.port,
                        self.username,
                        gss_auth=UseGSSAPI,
                        gss_kex=DoGSSAPIKeyExchange,
                        timeout=timeout
                    )
                except Exception:
                    self.client.connect(self.hostname,
                                        self.port,
                                        self.username,
                                        self.password,
                                        timeout=timeout)
        except Exception as e:
            print("*** Caught exception: %s: %s" % (e.__class__, e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            try:
                self.client.close()
            except:
                pass
            sys.exit(1)


    """
    return a new channel
    """
    def new_channel(self):
        if not self.client:
            self.open()
        return self.client._transport.open_session()

    """
    return a new sftp
    """
    def new_sftp(self):
        if not self.client:
            self.open()
        return self.client._transport.open_sftp_client()

    def close(self):
        self.client.close()

    """
    open on interactive shell
    """
    def interactive_shell(self, term='linux'):
        rows, columns = os.popen('stty size', 'r').read().split()
        c = self.new_channel()
        c.get_pty(term, int (columns), int (rows), 0, 0)
        c.invoke_shell()
        interactive.interactive_shell(c)

    """
    exec command
    """
    def exec (self, cmd, bufsize=-1):
        cmd = 'echo $$ && exec ' + cmd
        try:
            c = self.new_channel()
            c.exec_command(cmd)
            r = ssh_client.CmdResp()
            r.hostname = self.hostname
            r.stdin = c.makefile_stdin("wb", bufsize)
            r.stdout = c.makefile("r", bufsize)
            r.stderr = c.makefile_stderr("r", bufsize)
            r.pid = int(r.stdout.readline())
            r.status = c.recv_exit_status()
            return r
        except:
            raise

    """
    exec command on channel
    """
    def exec_channel (self, c,  cmd, bufsize=-1):
        try:
            cmd = 'echo $$ && exec ' + cmd
            c.exec_command(cmd)
            r = ssh_client.CmdResp()
            r.hostname = self.hostname
            r.stdin = c.makefile_stdin("wb", bufsize)
            r.stdout = c.makefile("r", bufsize)
            r.stderr = c.makefile_stderr("r", bufsize)
            r.pid = int(r.stdout.readline())
            r.status = c.recv_exit_status()
            return r
        except:
            raise

    """
    send a single file using mktemp on target
    mode set the mode in remote file as os.chmod()
    return the destination path as string or None.
    """
    def mktemp_send_file (self, src, mode=None):
        tmp_dir = None
        try:
            r = ssh_client.CmdResp()
            r = self.exec ('mktemp -d')
            if r.status == 0:
                tmp_dir = r.stdout.read().decode().strip()
                sftp = self.new_sftp()
                src = os.path.abspath (src)
                file_name = os.path.basename (src)
                dst = tmp_dir + '/' + file_name
                sftp.put (src, dst)
                if mode:
                    sftp.chmod (dst, mode)
                return dst
            else:
                print ("{}".format (r.stderr.read().decode()), file=sys.stderr)
                raise IOError
        except:
            raise

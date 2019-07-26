"""
ssh_client a high level paramiko http://www.paramiko.org/ wrapper

ref: https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
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

    """
    mandatory param:
    - destination: hostname or ip address
    """
    def __init__(self, destination, login=None, password=None, port=22, log_file=None):
        self.hostname = destination
        if login:
            self.username = login
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


    def open(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
            print("*** Connecting...")
            if not self.UseGSSAPI and not self.DoGSSAPIKeyExchange:
                self.client.connect(self.hostname, self.port, self.username, self.password)
            else:
                try:
                    self.client.connect(
                        self.hostname,
                        self.port,
                        self.username,
                        gss_auth=UseGSSAPI,
                        gss_kex=DoGSSAPIKeyExchange,
                    )
                except Exception:
                    self.client.connect(self.hostname, self.port, self.username, self.password)
        except Exception as e:
            print("*** Caught exception: %s: %s" % (e.__class__, e))
            traceback.print_exc()
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

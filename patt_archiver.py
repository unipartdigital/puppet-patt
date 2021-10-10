#!/usr/bin/env python3

import logging
import os
import tempfile
# from pathlib import Path
# import shutil
# from string import Template
# import time
import patt

logger = logging.getLogger('patt_archiver')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_archiver', result=result, hide_stdout=hide_stdout)

valid_cluster_char="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

"""
Base Class archivers
"""
class Archiver(object):
    def __init__(self):
        self.archiver_type = None

    """
    install policycoreutils-python-utils packages
    should be run on ssh/sftp peer
    """
    def ssh_archiving_init(self, nodes):
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   args=['ssh_archiving_init'], sudo=True)
        log_results (result)

    """
    gen a ssh key on each peer and return all the public key (on success)
    should be run on postgres peer
    """
    def ssh_keygen(self, cluster_name, nodes, postgres_user='postgres'):
        cluster_name="".join(
            ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
             else i for i in cluster_name])
        assert cluster_name[0] in valid_cluster_char
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)

        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   args=['ssh_archive_keygen'] + [cluster_name] +
                                   [self.archiver_type] + [postgres_user],
                                   sudo=True, log_call=True)
        log_results (result, hide_stdout=True)
        assert all(x == True for x in [bool(n.out) for n in result])
        return [n.out for n in result]


    """
    add new user into the archive servers
    """
    def user_add(self, nodes, user_name, archive_base_dir,
                 initial_group="archiver", user_shell="/bin/false"):
        archive_base_dir = os.path.abspath(archive_base_dir)
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   payload=[],
                                   args=['ssh_archive_user_add'] + [user_name] +
                                   [archive_base_dir] + [initial_group] + [user_shell], sudo=True)
        log_results (result)
        if any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')]):
            return False
        else:
            return all(x == True for x in [bool(n.out == "drwx--x--x {}.{} {}".format (
                user_name, initial_group, archive_base_dir + '/' + user_name)) for n in result])

    """
    append 'Match Group' and 'ChrootDirectory' directive into the main /etc/sshd_config file
    """
    def sftpd22_chroot (self, nodes, archive_base_dir, group="archiver"):
        archive_base_dir = os.path.abspath(archive_base_dir)
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   payload=[],
                                   args=['sshd_configure'] + [archive_base_dir] + [group], sudo=True)
        log_results (result)
        return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


    """
    create a dedicated sftpd only service
    """
    def archiving_standalone_sftpd(self, nodes, archive_base_dir,
                                   group="archiver", listen_addr="::0", listen_port=2222):
        result_all = []
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        tmpl="./config/sftpd.service"
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/systemd/system/{}".format (os.path.basename (tmpl))] +
                                   ['--dictionary_key_val'] + ["listen_port={}".format(listen_port)] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        r = not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
        result_all.append (r)

        archive_base_dir = os.path.abspath(archive_base_dir)
        tmpl="./config/sftpd_config"
        result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                                   payload=tmpl,
                                   args=['-t'] + [os.path.basename (tmpl)] +
                                   ['-o'] + ["/etc/ssh/{}".format (os.path.basename (tmpl))] +
                                   ['--dictionary_key_val'] +
                                   ["listen_address=[{}]:{}".format(listen_addr, listen_port)] +
                                   ['--dictionary_key_val'] +
                                   ["chroot={}".format(archive_base_dir)] +
                                   ['--dictionary_key_val'] +
                                   ["group={}".format(group)] +
                                   ['--dictionary-rhel'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-fedora'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-centos'] +
                                   ["subsystem=/usr/libexec/openssh/sftp-server"] +
                                   ['--dictionary-debian'] +
                                   ["subsystem=/usr/lib/openssh/sftp-server"] +
                                   ['--dictionary-ubuntu'] +
                                   ["subsystem=/usr/lib/openssh/sftp-server"] +
                                   ['--chmod'] + ['644'],
                                   sudo=True)
        log_results (result)
        r = not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
        result_all.append(r)
        logger.debug("archiving_standalone_sftpd result_all: {}".format(result_all))
        return result_all

    """
    disable dedicated sftpd port
    """
    def sftpd_disable (self, nodes):
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   args=['sftpd_command'] + ['disable'], sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
    """
    enable dedicated sftpd port
    """
    def sftpd_enable (self, nodes, port=2222):
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   args=['sftpd_command'] + ['enable'] + [port], sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


    """
    add the public keys into the archive server
    """
    def authorize_keys(self, cluster_name, nodes, keys=[]):
        cluster_name="".join(
            ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
             else i for i in cluster_name])
        assert cluster_name[0] in valid_cluster_char
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        with tempfile.NamedTemporaryFile(mode='w+', encoding='ascii') as tmpl_file:
            for k in keys + [""]:
                print("{}".format (k), file=tmpl_file)
            tmpl_file.flush()
            result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                       payload=tmpl_file.name,
                                       args=['ssh_authorize_keys'] + [cluster_name] +
                                       [os.path.basename (tmpl_file.name)], sudo=True)
            log_results (result)
        return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    """
    gen an initial known_hosts or check if valid
    """
    def ssh_known_hosts(self, cluster_name, nodes, archiving_server, archiving_server_port=22):
        cluster_name="".join(
            ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
             else i for i in cluster_name])
        assert cluster_name[0] in valid_cluster_char
        logger.info ("processing {}".format ([n.hostname for n in nodes]))
        patt.host_id(nodes)
        patt.check_dup_id (nodes)

        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                   args=['ssh_known_hosts'] + [cluster_name] +
                                   [archiving_server] + [archiving_server_port] + ['postgres'],
                                   sudo=True)
        log_results (result)
        return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])


    """
    return a list of tuple of node [(archive_peers, archive_service)]
    """
    def archiver_peers_service(self, archive_store, archive_peers):
        result=[]
        sh_store = (patt.to_nodes(
            [c['host'] for c in archive_store if c['method'] == 'sh' and 'host' in c],
            None, None))
        for p in archive_peers:
            for s in sh_store:
                if p.hostname == s.hostname:
                    result.append((p, s))
        return result


    """
    return the contain of <postgres_home>/.aws/credentials file (first found)
    return None otherwise
    """
    def aws_credentials_get(self, nodes=[]):
        comd="./dscripts/tmpl2file.py"
        for n in nodes:
            try:
                result = patt.exec_script (nodes=[n], src="dscripts/d27.archiver.sh",
                                           payload=comd,
                                           args=['aws_credentials_dump'] +
                                           [os.path.basename (comd)], sudo=True)
            except:
                continue
            else:
                for r in result:
                    if r.out:
                        return r.out
            finally:
                log_results (result, hide_stdout=True)


    """
    add the aws credentials into each postgres peer
    aws_credentials can be made optional with: error_on_file_not_found==False
    """
    def aws_credentials(self, nodes, aws_credentials=None, error_on_file_not_found=False):
        patt.host_id(nodes)
        # patt.check_dup_id (nodes)
        source = patt.Source()
        running_node = source.whoami(nodes)
        with tempfile.TemporaryDirectory() as tmp_dir:
            if type (running_node) is patt.Node:
                # installing from peer
                tmp = self.aws_credentials_get([running_node])
                if tmp:
                    with open (tmp_dir + '/' + 'awsc', "w") as awsc:
                        awsc.write(tmp)
                        awsc.write('\n')
                        awsc.flush()
                        awsc.close()
                        aws_credentials = awsc.name
            if aws_credentials and error_on_file_not_found:
                assert os.path.isfile (aws_credentials)
            if aws_credentials and os.path.isfile (aws_credentials):
                comd="./dscripts/tmpl2file.py"
                result = patt.exec_script (nodes=nodes, src="./dscripts/d27.archiver.sh",
                                           payload=[comd, aws_credentials],
                                           args=['aws_credentials'] +
                                           [os.path.basename (comd)] +
                                           [os.path.basename (aws_credentials)], sudo=True)
                log_results (result)
                return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
            return True


    """
    create the first s3 bucket defined in archive_store
    """
    def s3_create_bucket(self, nodes, archive_store):
        patt.host_id(nodes)
        comd="./dscripts/create_bucket.py"
        s3_store = [s for s in  archive_store if 'method' in s and s['method'] == 's3']
        if s3_store:
            logger.debug ("s3_create_bucket: {}".format(s3_store))
            endpoint=s3_store[0]['endpoint']
            bucket=s3_store[0]['prefix']
            profile=s3_store[0]['profile']
            region=s3_store[0]['region']
            if 'force_path_style' in s3_store[0] and s3_store[0]['force_path_style'].strip().lower=="false":
                force_path_style=False
            else:
                force_path_style=True
            result = patt.exec_script (nodes=nodes, src="dscripts/d27.archiver.sh",
                                       payload=comd,
                                       args=['s3_create_bucket'] + [os.path.basename (comd)] +
                                       [endpoint] + [os.path.basename (bucket)] + [profile] + [region] +
                                       [force_path_style] + ['postgres'],
                                       sudo=True)
            log_results (result)
            return any (x.out == os.path.basename (bucket) for x in result if hasattr(x, 'out'))
        else:
            return True

    """
    base class no backup or archiving, assertion always True
    """
    def archiving_add(self, cluster_name, nodes, port):
        return True

    def s3_config(self, postgres_version, cluster_name, nodes, archive_store):
        return True

    def sh_config(self, postgres_version, cluster_name, nodes, archive_store):
        return True

    def backup_service_setup(self, nodes, postgres_version, tmpl=""):
        return True

    def backup_service_command(self, nodes, command, postgres_version):
        return True

#!/usr/bin/env python3

import patt
import logging
import os
import tempfile
from pathlib import Path
import shutil
from string import Template
import time

logger = logging.getLogger('patt_walg')

def log_results(result, hide_stdout=False):
    patt.log_results(logger='patt_walg', result=result, hide_stdout=hide_stdout)

valid_cluster_char="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

"""
install postgres packages and dep on each nodes
"""
def walg_init(walg_version, walg_url, walg_sha256, nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['walg_version'], sudo=False)
    ok = all(x == walg_version for x in [n.out for n in result])
    if ok: return True

    if walg_url is None: walg_url = ""
    if walg_sha256 is None: walg_sha256 = ""
    payload=None
    walg_local_pkg="./pkg/{}".format(os.path.basename (walg_url))
    if os.path.isfile(walg_local_pkg):
        payload=walg_local_pkg

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh", payload=payload,
                                args=['init'] + [walg_version] + [walg_url] + [walg_sha256], sudo=False)
    log_results (result)
    return all(x == True for x in [bool(n.out) for n in result])

"""
install util packages to allow sftp access
"""
def walg_ssh_archiving_init(nodes):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                args=['ssh_archiving_init'], sudo=True)
    log_results (result)
    #return all(x == True for x in [bool(n.out) for n in result])

"""
gen a walg ssh key on each peer and return all the public key (on success)
"""
def walg_ssh_gen(cluster_name, nodes, postgres_user='postgres'):
    cluster_name="".join(
        ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
         else i for i in cluster_name])
    assert cluster_name[0] in valid_cluster_char
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_archive_keygen'] + [cluster_name] + [postgres_user],
                               sudo=True, log_call=True)
    log_results (result, hide_stdout=True)
    assert all(x == True for x in [bool(n.out) for n in result])
    return [n.out for n in result]

"""
gen an initial known_hosts or check if valid
"""
def walg_ssh_known_hosts(cluster_name, nodes, archiving_server, archiving_server_port=22):
    cluster_name="".join(
        ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
         else i for i in cluster_name])
    assert cluster_name[0] in valid_cluster_char
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_known_hosts'] + [cluster_name] +
                               [archiving_server] + [archiving_server_port],
                               sudo=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
add the public keys into the archive server
"""
def walg_authorize_keys(cluster_name, nodes, keys=[]):
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
        result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                   payload=tmpl_file.name,
                                   args=['ssh_authorize_keys'] + [cluster_name] +
                                   [os.path.basename (tmpl_file.name)], sudo=True)
        log_results (result)
    return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
preapare the archive server for chroot sftp
"""
def walg_archiving_standalone_sftpd(cluster_name, nodes, listen_addr="::0", listen_port=2222):
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)

    tmpl="./config/sftpd.service"
    result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                               payload=tmpl,
                               args=['-t'] + [os.path.basename (tmpl)] +
                               ['-o'] + ["/etc/systemd/system/{}".format (os.path.basename (tmpl))] +
                               ['--chmod'] + ['644'],
                               sudo=True)
    log_results (result)
    assert not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

    tmpl="./config/sftpd_config"
    result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                               payload=tmpl,
                               args=['-t'] + [os.path.basename (tmpl)] +
                               ['-o'] + ["/etc/ssh/{}".format (os.path.basename (tmpl))] +
                               ['--dictionary_key_val'] +
                               ["listen_address=[{}]:{}".format(listen_addr, listen_port)] +
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
    assert not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

"""
preapare the archive server for chroot sftp
"""
def walg_archiving_add(cluster_name, nodes, port):
    cluster_name="".join(
        ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
         else i for i in cluster_name])
    assert cluster_name[0] in valid_cluster_char
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    if not port == 22:
        assert port > 1024, "error: restricted to unreserved or default ssh port only"
        walg_archiving_standalone_sftpd(cluster_name=cluster_name, nodes=nodes,
                                        listen_addr="::0", listen_port=port)

    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               args=['ssh_archiving_add'] + [cluster_name] + [port], sudo=True)
    log_results (result)
    return all(x == True for x in [bool(n.out == "drwx--x--x {}.{} {}".format (
        cluster_name, "walg", "/var/lib/walg/" + cluster_name)) for n in result])

"""
s3 json config
"""
def walg_s3_json(postgres_version, cluster_name, nodes, walg_store):
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    comd="./dscripts/tmpl2file.py"
    tmpl="./config/walg-s3.json"
    count=0
    isok = []
    logger.debug ("walg_s3_json: {}".format(walg_store))
    for c in walg_store:
        logger.debug ("walg_s3_json: {}".format(c))
        if 'method' in c and c['method'] == 's3':
            endpoint=c['endpoint']
            assert endpoint, "missing endpoint definition"
            prefix=c['prefix']
            assert prefix, "missing prefix definition"
            if not (prefix.endswith(cluster_name) or prefix.endswith(cluster_name + '/')):
                prefix=prefix + '/' + cluster_name
            region=c['region']
            assert region, "missing region definition"
            if 'force_path_style' in c:
                force_path_style=c['force_path_style']
            else:
                force_path_style='true'
            if 'profile' in c:
                profile=c['profile']
            else:
                profile=''

            if count == 0:
                s3_config_file=".walg.json"
            else:
                s3_config_file="walg-{}-s3.json".format(count)

            result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh", payload=[comd, tmpl],
                                       args=['s3_json'] + [postgres_version] + [cluster_name] +
                                       [endpoint] + [prefix] + [region] + [profile] +
                                       [force_path_style] + [s3_config_file] +
                                       ['postgres'] + [os.path.basename (comd)] + [os.path.basename (tmpl)],
                                       sudo=True)
            isok.append(not any(x == True for x in [bool(n.error) for n in result if hasattr(n, 'error')]))
            log_results (result)
        count += 1
    return all(x == True for x in isok)

"""
sh json config
"""
def walg_sh_json(postgres_version, cluster_name, nodes, walg_store):
    cluster_name="".join(
        ['-' if i in [j for j in cluster_name if j not in valid_cluster_char + '-']
         else i for i in cluster_name])
    assert cluster_name[0] in valid_cluster_char
    logger.info ("processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    patt.check_dup_id (nodes)
    comd="./dscripts/tmpl2file.py"
    tmpl="./config/walg-sh.json"
    count=0
    isok = []
    logger.debug ("walg_sh_json: {}".format(walg_store))
    for c in walg_store:
        logger.debug ("walg_sh_json: {}".format(c))
        if 'method' in c and c['method'] == 'sh':
            host=c['host']
            assert host, "missing ssh host definition"
            if 'prefix' in c:
                prefix=c['prefix']
            if not prefix:
                prefix=cluster_name
            if not (prefix.endswith(cluster_name) or prefix.endswith(cluster_name + '/')):
                prefix=prefix + '/' + cluster_name
            (login, hostname, port) = patt.ipv6_nri_split (host)
            if not login:
                login = cluster_name
            if not port:
                port = 22
            identity_file=None
            if 'identity_file' in c:
                identity_file=c['identity_file']
            if not identity_file:
                identity_file="walg_rsa"

            if count == 0:
                sh_config_file=".walg.json"
            else:
                sh_config_file="walg-{}-sh.json".format(count)

            result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh", payload=[comd, tmpl],
                                       args=['sh_json'] + [postgres_version] + [cluster_name] +
                                       [hostname] + [port] + [prefix] + [login] +
                                       [identity_file] + [sh_config_file] +
                                       ['postgres'] + [os.path.basename (comd)] + [os.path.basename (tmpl)],
                                       sudo=True)
            isok.append(not any(x == True for x in [bool(n.error) for n in result if hasattr(n, 'error')]))
            log_results (result)
        count += 1
    return all(x == True for x in isok)

"""
return a list of tuple of node [(sftpd_peers, sftpd_service)]
"""
def sftpd_peers_service(walg_store, sftpd_peers):
    result=[]
    sh_store = (patt.to_nodes(
        [c['host'] for c in walg_store if c['method'] == 'sh' and 'host' in c],
        None, None))
    for p in sftpd_peers:
        for s in sh_store:
            if p.hostname == s.hostname:
                result.append((p, s))
    return result

"""
return the contain of <postgres_home>/.aws/credentials file (first found)
return None otherwise
"""
def walg_aws_credentials_get(nodes=[]):
    comd="./dscripts/tmpl2file.py"
    for n in nodes:
        try:
            result = patt.exec_script (nodes=[n], src="dscripts/d27.walg.sh",
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
 walg_aws_credentials can be made optional with: error_on_file_not_found==False
"""
def walg_aws_credentials(nodes, aws_credentials=None, error_on_file_not_found=False):
    patt.host_id(nodes)
    # patt.check_dup_id (nodes)
    source = patt.Source()
    running_node = source.whoami(nodes)
    with tempfile.TemporaryDirectory() as tmp_dir:
        if type (running_node) is patt.Node:
            # installing from peer
            tmp = walg_aws_credentials_get([running_node])
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
            result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                                       payload=[comd, aws_credentials],
                                       args=['aws_credentials'] +
                                       [os.path.basename (comd)] +
                                       [os.path.basename (aws_credentials)], sudo=True)
            log_results (result)
            return not any (x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])
        return True

"""
create the first s3 bucket defined in walg_store
"""
def walg_s3_create_bucket(nodes, walg_store):
    patt.host_id(nodes)
    comd="./dscripts/create_bucket.py"
    s3_store = [s for s in  walg_store if 'method' in s and s['method'] == 's3']
    if s3_store:
        logger.debug ("s3_create_bucket: {}".format(s3_store))
        endpoint=s3_store[0]['endpoint']
        bucket=s3_store[0]['prefix']
        profile=s3_store[0]['profile']
        region=s3_store[0]['region']
        if 'force_path_style' in s3_store[0] and s3_store[0]['force_path_style'].strip().lower == "false":
            force_path_style=False
        else:
            force_path_style=True
        result = patt.exec_script (nodes=nodes, src="dscripts/d27.walg.sh",
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
configure the systemd schedule backup service (named after the postgres version)
"""
def walg_backup_service_setup(nodes, postgres_version,
                              tmpl="./config/backup_walg.service"):
    logger.info ("walg_s3_backup_service processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    comd="./dscripts/tmpl2file.py"
    pg_data_rhl_fam="/var/lib/pgsql/{}/data".format(postgres_version)
    pg_data_deb_fam="/var/lib/postgresql/{}/data".format(postgres_version)
    systemd_service="{}-{}.service".format(os.path.basename (tmpl).rpartition('.')[0], postgres_version)
    result = patt.exec_script (nodes=nodes, src="./dscripts/tmpl2file.py",
                               payload=tmpl,
                               args=['-t'] + [os.path.basename (tmpl)] +
                               ['-o'] + ["/etc/systemd/system/{}".format (systemd_service)] +
                               ['--dictionary_key_val'] +
                               ["backup_walg={}".format(
                                   "/usr/local/libexec/patt/dscripts/backup_walg.py")] +
                               ['--dictionary_key_val'] +
                               ["cluster_config={}".format("/usr/local/etc/cluster_config.yaml")] +
                               ['--dictionary-rhel'] +
                               ["pg_data={}".format(pg_data_rhl_fam)] +
                               ['--dictionary-fedora'] +
                               ["pg_data={}".format(pg_data_rhl_fam)] +
                               ['--dictionary-centos'] +
                               ["pg_data={}".format(pg_data_rhl_fam)] +
                               ['--dictionary-debian'] +
                               ["pg_data={}".format(pg_data_deb_fam)] +
                               ['--dictionary-ubuntu'] +
                               ["pg_data={}".format(pg_data_deb_fam)] +
                               ['--chmod'] + ['644'],
                               sudo=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

def walg_backup_service_command(nodes, command, postgres_version):
    logger.info ("walg_s3_backup_service processing {}".format ([n.hostname for n in nodes]))
    patt.host_id(nodes)
    result = patt.exec_script (nodes=nodes, src="./dscripts/d27.walg.sh",
                               payload="dscripts/backup_walg.py",
                               args=['backup_walg_service'] + [command] + [postgres_version] +
                               ["/usr/local/libexec/patt/dscripts/backup_walg.py"],
                               sudo=True)
    log_results (result)
    return not any(x == True for x in [bool(n.error) for n in result if hasattr(n,'error')])

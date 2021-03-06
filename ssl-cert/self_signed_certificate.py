#!/usr/bin/python3

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509.oid import NameOID
from cryptography import x509
import datetime
from ipaddress import ip_address
import argparse
import yaml
import sys
import os
from pathlib import Path

class Object(object):
    pass

class Config(object):
    def __init__(self):

        self.ca   = {'subject': {}, 'meta': {}, 'data': {}, 'key': {}}
        self.cert = {'subject': {}, 'meta': {}, 'data': {}, 'key': {}}

    def from_argparse_cli(self, args):
        self.ca['subject']['country_name'] = args.ca_country_name
        self.ca['subject']['state_or_province_name'] = args.ca_state_or_province_name
        self.ca['subject']['locality_name'] = args.ca_locality_name
        self.ca['subject']['organization_name'] = args.ca_organization_name
        self.ca['subject']['common_name'] = args.ca_common_name
        self.ca['meta']['path'] = args.ca_path
        self.ca['data']['not_valid_after_days'] = args.ca_not_valid_after
        self.ca['key']['path'] = args.ca_key_path
        self.ca['key']['pass_phrase'] = args.ca_key_pass_phrase
        self.ca['key']['size'] = args.ca_key_size

        self.cert['subject']['country_name'] = args.cert_country_name
        self.cert['subject']['state_or_province_name'] = args.cert_state_or_province_name
        self.cert['subject']['locality_name'] = args.cert_locality_name
        self.cert['subject']['organization_name'] = args.cert_organization_name
        self.cert['subject']['common_name'] = args.cert_common_name
        self.cert['meta']['path'] = args.cert_path
        self.cert['data']['not_valid_after_days'] = args.cert_not_valid_after
        if args.cert_dns:
            self.cert['data']['dns'] = args.cert_dns[0]
        else:
            self.cert['data']['dns'] = []
        if args.cert_ip:
            self.cert['data']['ip'] = args.cert_ip[0]
        else:
            self.cert['data']['ip'] = []
        self.cert['key']['path'] = args.cert_key_path
        self.cert['key']['pass_phrase'] = args.cert_key_pass_phrase
        self.cert['key']['size'] = args.cert_key_size

    def to_yaml(self):
        result = yaml.dump(self)
        print (result.replace("!!python/object", "#!!python/object"))
        sys.exit(0)

    def from_yaml_file(self, yaml_file):
        result=None
        try:
            with open(yaml_file, 'r') as f:
                try:
                    result=yaml.safe_load(f)
                    for k in result.keys():
                        if k in self.__dict__.keys():
                            setattr(self, k, result[k])
                except yaml.YAMLError as e:
                    print(str(e), file=sys.stderr)
                    raise
                except:
                    raise
        except:
            pass
"""
Generate our key
"""
def private_key (pass_phrase=None, key_path=None, key_size=4096):
    if key_path and os.path.isfile (key_path):
        with open(key_path, "rb") as f:
            key=f.read()
            if pass_phrase:
                key = load_pem_private_key(key, pass_phrase.encode('utf8'), default_backend())
            else:
                key = load_pem_private_key(key, pass_phrase, default_backend())
            return key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    if pass_phrase:
        e=serialization.BestAvailableEncryption(pass_phrase.encode('utf8'))
    else:
        e=serialization.NoEncryption()
    # Write our key to disk for safe keeping
    if key_path is not None:
        Path(os.path.dirname(key_path)).mkdir(parents=True, exist_ok=True, mode=0o711)
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=e,
            ))
        os.chmod (key_path, 0o600)
    return key

"""
create a certificate,
will load the certificate from path if provided and suitable
"""
def mk_certificate_thin (country_name,
                         state_or_province_name,
                         locality_name,
                         organization_name,
                         common_name,
                         private_key,
                         public_key=None,
                         certificate_path=None,
                         ca_path=None,
                         is_root=False,
                         not_valid_after_days=365,
                         dns=[],
                         ip=[]):
    ca=None
    if certificate_path and os.path.isfile (certificate_path):
        with open(certificate_path, "rb") as f:
            cert=f.read()
            cert = x509.load_pem_x509_certificate(cert, default_backend())
            tval = cert.not_valid_after - datetime.datetime.utcnow()
            # return cert if more than 7 days remaining
            # it will force a new cert otherwise
            if tval.days > 7:
                return cert
    if ca_path and os.path.isfile (ca_path):
        with open(ca_path, "rb") as f:
            ca=f.read()
            ca = x509.load_pem_x509_certificate(ca, default_backend())

    # Various details about who we are. For a self-signed certificate the
    # subject and issuer are always the same.
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    #
    if isinstance(ca, x509.Certificate):
        # update the issuer info if a CA is provided
        issuer = ca.issuer

    ext = []
    if not is_root:
        # add DNS & IP extension if not CA
        ext += [x509.DNSName(d) for d in dns]
        ext += [x509.IPAddress(ip_address(i)) for i in ip]

    if public_key is None:
        public_key=private_key.public_key()

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=not_valid_after_days)
    ).add_extension(
        x509.SubjectAlternativeName(ext),
        critical=False,
    )
    if is_root:
        cert = cert.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True,
        )
    cert = cert.sign(private_key, hashes.SHA256(), default_backend())

    # Write our certificate out to disk.

    if certificate_path:
        Path(os.path.dirname(certificate_path)).mkdir(parents=True, exist_ok=True, mode=0o711)
        with open(certificate_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert.public_bytes(serialization.Encoding.PEM)

"""
use openssl cli to verify the certificate chain
"""
def x509_verify(cfg):
    import subprocess
    ca_path=None
    cmd=['/usr/bin/openssl', 'verify']
    if 'path' in cfg.ca['meta']:
        cmd.append('-CAfile')
        cmd.append(cfg.ca['meta']['path'])
        if 'path' in cfg.cert['meta']:
            cmd.append(cfg.cert['meta']['path'])
        else:
            raise ValueError
    try:
        res = subprocess.run(cmd, shell=False, check=False, capture_output=True, text=True)
        print (res.stdout)
        print (res.stderr,file=sys.stderr)
        sys.exit(res.returncode)
    except:
        raise

def x509_show(cfg):
    import subprocess
    ca_path=None
    inf=[]
    cmd=['/usr/bin/openssl', 'x509', '-text', '-noout']
    if 'path' in cfg.ca['meta']:
        inf.append(cfg.ca['meta']['path'])
        if cfg.cert['meta'] and 'path' in cfg.cert['meta']:
            inf.append(cfg.cert['meta']['path'])
    try:
        for i in inf:
            res = subprocess.run(cmd + ['-in', i], shell=False, check=True, capture_output=True, text=True)
            print (res.stdout)
            print (res.stderr,file=sys.stderr)
    except:
        raise

if __name__ == "__main__":
    cfg = Config()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='interface')

    yml = subparsers.add_parser('yaml')
    yml.add_argument('-f','--yaml_config_file', help='config file', required=True)
    yml.add_argument('--verify', help='run openssl verify', required=False, action='store_true')
    yml.add_argument('--show', help='output certificate in text format', required=False, action='store_true')
    yml.add_argument('--over_ca_path', help='override path to ca certificat', default=None, required=False)
    yml.add_argument('--over_ca_key_path', help='override path to private key', default=None, required=False)
    yml.add_argument('--over_cert_path', help='override path to certificat', default=None, required=False)
    yml.add_argument('--over_cert_key_path', help='override path to private key', default=None, required=False)

    cli = subparsers.add_parser('cli')
    cli.add_argument('--ca_country_name', help='Country Name', required=False)
    cli.add_argument('--ca_state_or_province_name', help='State or Province Name', required=False)
    cli.add_argument('--ca_locality_name', help='Locality Name', required=False)
    cli.add_argument('--ca_organization_name', help='Organization Name', required=False)
    cli.add_argument('--ca_common_name', help='Common Name', required=False)
    cli.add_argument('--ca_not_valid_after', help='not valid after n days', default=365, type=int)
    cli.add_argument('--ca_path', help='path to ca certificat', default=None, required=False)
    cli.add_argument('--ca_key_pass_phrase', help='private key passphrase', default=None, required=False)
    cli.add_argument('--ca_key_size', help='private key size', default=4096, type=int, required=False)
    cli.add_argument('--ca_key_path', help='path to private key', default=None, required=False)

    cli.add_argument('--cert_country_name', help='Country Name', required=False)
    cli.add_argument('--cert_state_or_province_name', help='State or Province Name', required=False)
    cli.add_argument('--cert_locality_name', help='Locality Name', required=False)
    cli.add_argument('--cert_organization_name', help='Organization Name', required=False)
    cli.add_argument('--cert_common_name', help='Common Name', required=False)
    cli.add_argument('--cert_dns', help='list of dns names', action='append', nargs="+", required=False, default=[])
    cli.add_argument('--cert_ip', help='list of IPs', action='append', required=False,nargs="+", default=[])
    cli.add_argument('--cert_not_valid_after', help='not valid after n days', type=int, default=365)
    cli.add_argument('--cert_path', help='path to certificat', default=None, required=False)
    cli.add_argument('--cert_key_pass_phrase', help='private key passphrase', default=None, required=False)
    cli.add_argument('--cert_key_size', help='private key size', default=4096, type=int, required=False)
    cli.add_argument('--cert_key_path', help='path to private key', default=None, required=False)

    cli.add_argument('--yaml_dump', help="dump the cli options in yaml format", action='store_true')
    cli.add_argument('--verify', help='run openssl verify', required=False, action='store_true')

    args = parser.parse_args()
    if args.interface == 'cli':
        cfg.from_argparse_cli (args)
        if args.yaml_dump:
            cfg.to_yaml()
    elif args.interface == 'yaml':
        cfg.from_yaml_file (args.yaml_config_file)

        if args.over_ca_path:
            cfg.ca['meta']['path'] = args.over_ca_path
        if args.over_ca_key_path:
            cfg.ca['key']['path'] = args.over_ca_key_path
        if args.over_cert_path:
            cfg.cert['meta']['path'] = args.over_cert_path
        if args.over_cert_key_path:
            cfg.cert['key']['path'] = args.over_cert_key_path

        if args.verify:
            x509_verify(cfg)
            sys.exit(0)

        if args.show:
            x509_show(cfg)
    else:
        parser.print_help()
        sys.exit(1)

    public_key=None
    ca_key=None

    if 'path' in cfg.ca['key'] or 'common_name' in cfg.ca['subject']:
        ca_key = private_key(key_path=cfg.ca['key']['path'],
                             pass_phrase=cfg.ca['key']['pass_phrase'],
                             key_size=cfg.ca['key']['size']
                             )

    if 'common_name' in cfg.ca['subject'] and cfg.ca['subject']['common_name']:
        ca_crt = mk_certificate_thin(country_name=cfg.ca['subject']['country_name'],
                                     state_or_province_name=cfg.ca['subject']['state_or_province_name'],
                                     locality_name=cfg.ca['subject']['locality_name'],
                                     organization_name=cfg.ca['subject']['organization_name'],
                                      common_name=cfg.ca['subject']['common_name'],
                                     private_key=ca_key,
                                     certificate_path=cfg.ca['meta']['path'],
                                     is_root=True,
                                     not_valid_after_days=cfg.ca['data']['not_valid_after_days']
                                     )

    if 'common_name' in cfg.cert['subject'] and cfg.cert['subject']['common_name']:
        srv_key = private_key(key_path=cfg.cert['key']['path'],
                              pass_phrase=cfg.cert['key']['pass_phrase'],
                              key_size=cfg.cert['key']['size']
                              )

        certificate_path=None
        if cfg.cert['meta'] and 'path' in cfg.cert['meta']:
            certificate_path=cfg.cert['meta']['path']

        srv_crt = mk_certificate_thin(country_name=cfg.cert['subject']['country_name'],
                                      state_or_province_name=cfg.cert['subject']['state_or_province_name'],
                                      locality_name=cfg.cert['subject']['locality_name'],
                                      organization_name=cfg.cert['subject']['organization_name'],
                                      common_name=cfg.cert['subject']['common_name'],
                                      private_key=ca_key,
                                      public_key=srv_key.public_key(),
                                      certificate_path=certificate_path,
                                      ca_path=cfg.ca['meta']['path'],
                                      not_valid_after_days=cfg.cert['data']['not_valid_after_days'],
                                      dns=cfg.cert['data']['dns'],
                                      ip=cfg.cert['data']['ip']
                                      )

        if args.verify is None:
            print (srv_crt.public_bytes(serialization.Encoding.PEM).decode('utf8'))

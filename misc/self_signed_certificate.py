#!/usr/bin/python3

from cryptography.hazmat.primitives.asymmetric import rsa
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

class Object(object):
    pass

class Config(object):
    def __init__(self):

        self.certificate = {'subject': {}, 'meta': {}, 'data': {}}
        self.private_key = {}

    def from_argparse_cli(self, args):
        self.private_key['path'] = args.private_key_path
        self.private_key['pass_phrase'] = args.private_key_pass_phrase
        self.private_key['size'] = args.private_key_size
        self.certificate['subject']['country_name'] = args.cert_country_name
        self.certificate['subject']['state_or_province_name'] = args.cert_state_or_province_name
        self.certificate['subject']['locality_name'] = args.cert_locality_name
        self.certificate['subject']['organization_name'] = args.cert_organization_name
        self.certificate['subject']['common_name'] = args.cert_common_name
        self.certificate['meta']['path'] = args.cert_path
        self.certificate['data']['not_valid_after_days'] = args.cert_not_valid_after
        self.certificate['data']['dns'] = args.cert_dns
        self.certificate['data']['ip'] = args.cert_ip

    def to_yaml(self):
        result = yaml.dump(self)
        print (result.replace("!!python/object", "#!!python/object"))
        sys.exit(0)

    def from_yaml_file(self, yaml_file):
        result=None
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

"""
Generate our key
"""
def private_key (pass_phrase=None, key_path=None, key_size=4096):
    if key_path and os.path.isfile (key_path):
        with open(key_path, "rb") as f:
            key=f.read()
            key = load_pem_private_key(key, pass_phrase)
            return key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    if pass_phrase:
        e=serialization.BestAvailableEncryption(pass_phrase.encode('utf8'))
    else:
        e=serialization.NoEncryption()
    # Write our key to disk for safe keeping
    if key_path is not None:
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=e,
            ))
    return key

def mk_certificate (country_name,
                    state_or_province_name,
                    locality_name,
                    organization_name,
                    common_name,
                    private_key,
                    certificat_path=None,
                    not_valid_after_days=365,
                    dns=[],
                    ip=[]):
    # Various details about who we are. For a self-signed certificate the
    # subject and issuer are always the same.
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    ext = []
    ext += [x509.DNSName(d) for d in dns]
    ext += [x509.IPAddress(ip_address(i)) for i in ip]

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Our certificate will be valid for 10 years
        datetime.datetime.utcnow() + datetime.timedelta(days=not_valid_after_days)
    ).add_extension(
        x509.SubjectAlternativeName(ext),
        critical=False,
        # Sign our certificate with our private key
    ).sign(key, hashes.SHA256())
    # Write our certificate out to disk.

    if certificat_path:
        with open(certificat_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert.public_bytes(serialization.Encoding.PEM)


if __name__ == "__main__":
    cfg = Config()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='interface')

    yml = subparsers.add_parser('yaml')
    yml.add_argument('-f','--yaml_config_file', help='config file', required=True)

    cli = subparsers.add_parser('cli')
    cli.add_argument('--private_key_pass_phrase', help='private key passphrase', default=None, required=False)
    cli.add_argument('--private_key_size', help='private key size', default=4096, required=False)
    cli.add_argument('--private_key_path', help='path to private key', default=None, required=False)

    cli.add_argument('--cert-country_name', help='Country Name', required=True)
    cli.add_argument('--cert-state_or_province_name', help='State or Province Name', required=True)
    cli.add_argument('--cert-locality_name', help='Locality Name', required=True)
    cli.add_argument('--cert-organization_name', help='Organization Name', required=True)
    cli.add_argument('--cert-common_name', help='Common Name', required=True)
    cli.add_argument('--cert-dns', help='list of dns names', action='append', required=False, default=[])
    cli.add_argument('--cert-ip', help='list of IPs', action='append', required=False, default=[])
    cli.add_argument('--cert-not_valid_after', help='not valid after n days', default=365, required=False)
    cli.add_argument('--cert-path', help='path to certificat', default=None, required=False)
    cli.add_argument('--yaml_dump', help="dump the cli options in yaml format", action='store_true', required=False)

    args = parser.parse_args()
    if args.interface == 'cli':
        cfg.from_argparse_cli (args)
        if args.yaml_dump:
            cfg.to_yaml()
    elif args.interface == 'yaml':
        cfg.from_yaml_file (args.yaml_config_file)
    else:
        parser.print_help()
        sys.exit(1)

    key = private_key(key_path=cfg.private_key['path'],
                      pass_phrase=cfg.private_key['pass_phrase'],
                      key_size=cfg.private_key['size']
                      )

    crt = mk_certificate(country_name=cfg.certificate['subject']['country_name'],
                         state_or_province_name=cfg.certificate['subject']['state_or_province_name'],
                         locality_name=cfg.certificate['subject']['locality_name'],
                         organization_name=cfg.certificate['subject']['organization_name'],
                         common_name=cfg.certificate['subject']['common_name'],
                         private_key=key,
                         certificat_path=cfg.certificate['meta']['path'],
                         not_valid_after_days=cfg.certificate['data']['not_valid_after_days'],
                         dns=cfg.certificate['data']['dns'],
                         ip=cfg.certificate['data']['ip']
                         )
    if cfg.certificate['meta']['path'] is None:
        print (crt.decode('utf8'))

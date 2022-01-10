#!/usr/bin/python3

"""
 tmpl2file a simple template processor

 apply a dictionary to a template file and write into --output or stdout
 template is done via String.Template
 https://python.readthedocs.io/en/latest/library/string.html#template-strings
 a key key1 will be applied if there is a matching tag $key1
 if your template contain '$' (ie a shell script) use $$ to escape the symbole.
 all tags in the template file should have a match in the dictionary.

 predefined keys:
 - $home is set on the current user home directory
"""

import argparse
import sys
import os
import io
import hashlib
from string import Template
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN
from stat import *

def os_release ():
    os_release_dict = {}
    with open("/etc/os-release") as osr:
        lines=osr.readlines()
        for i in lines:
            if '=' in i:
                k,v=i.split('=',1)
                if k.upper() in ['ID', 'VERSION_ID']:
                    v=v.strip()
                    if v.startswith('"') and v.endswith('"'):
                        v=v[1:-1].strip()
                    os_release_dict[k.upper()]=v
                if 'VERSION_ID' in os_release_dict:
                    os_release_dict['MAJOR_VERSION_ID'] = os_release_dict['VERSION_ID'].split('.')[0]
    return os_release_dict

os_id = ['rhel', 'fedora', 'centos', 'rocky', 'debian', 'ubuntu']

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock_dir', help='lock directory', required=False, default="/tmp")
    parser.add_argument('-t', '--tmpl', help='template file', required=True)
    parser.add_argument('-o', '--output', help='template file', required=False)
    parser.add_argument('--chmod', help='chmod the output file octal notation like 755', required=False)
    parser.add_argument('--skip', help='optional skip comment', required=False)
    parser.add_argument('--touch', help='touch filename if output has changed', required=False)

    parser.add_argument('-d', '--dictionary_key_val', help='-d  key1=value1 -d key2=value2', required=False,
                         action='append', type=lambda kv: kv.split("=",1), dest='key_val')
    for i in os_id:
        parser.add_argument('--dictionary-{}'.format(i),
                            help='--dictionary-{}  key1=value1 (to set on {})'.format(i, i), required=False,
                            action='append', type=lambda kv: kv.split("=",1), dest='{}_key_val'.format(i))

    args = parser.parse_args()

    os.chdir (os.path.dirname (__file__))

    ###
    lock_filename = args.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
    if not os.path.exists(lock_filename):
        lockf = open(lock_filename, "w+")
        lockf.close()
    lockf = open(lock_filename, "r")
    lock_fd = lockf.fileno()
    flock(lock_fd, LOCK_EX | LOCK_NB)
    ###

    osr = os_release()

    d = {}
    if args.key_val:
        d = dict(args.key_val)
        d['home']=os.path.expanduser("~")
    for i in os_id:
        if hasattr(args, "{}_key_val".format (i)) and getattr(args,"{}_key_val".format (i)):
            if 'ID' in osr and osr['ID'] == i:
                d.update (dict(getattr(args,"{}_key_val".format (i))))

    template_file = args.tmpl
    if args.output:
        output = args.output
    else:
        output = None
    tmpl = None
    output_mod=None
    if args.chmod:
        output_mod=int("0o{}".format(args.chmod), 8)

    skip_comments = lambda c, fd: (
        line for line in fd if not (line.strip().startswith(c) and not line.startswith('#!')))
    with open(template_file, 'r') as t:
        try:
            if isinstance(args.skip, str):
                tmpl=Template ("".join(skip_comments(args.skip, t)))
            else:
                tmpl=Template (t.read())
        except:
            raise

    if output:
        try:
            write_out=True
            if os.path.isfile(output):
                buf = io.StringIO()
                if d:
                    print(tmpl.substitute(d), file=buf)
                else:
                    print(tmpl.safe_substitute(d), file=buf)
                src_md5=hashlib.md5()
                src_md5.update(buf.getvalue().encode('utf8'))
                src_hexdigest=src_md5.hexdigest()
                with open(output, 'r') as f:
                    dst_hexdigest=hashlib.md5(f.read().encode('utf-8')).hexdigest()
                if src_hexdigest == dst_hexdigest:
                    write_out=False
            if write_out:
                with open(output, 'w') as f:
                    if d:
                        print(tmpl.substitute(d), file=f)
                    else:
                        print(tmpl.safe_substitute(d), file=f)
                if args.touch:
                    touch (args.touch)
            if output_mod:
                mode = oct(S_IMODE(os.stat(output).st_mode))
                if oct(output_mod) != mode:
                    os.chmod(output, output_mod)
        except:
            raise
    else:
        try:
            if d:
                print(tmpl.substitute(d))
            else:
                print(tmpl.safe_substitute(d))
        except:
            raise


    ###
    flock(lock_fd, LOCK_UN)
    lockf.close()
    try:
        os.remove(lock_filename)
    except OSError:
        pass
    ###

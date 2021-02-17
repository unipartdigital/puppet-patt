#!/usr/bin/python3

"""
 tmpl2file a simple template processor

 apply a dictionary to a template file and write into --output or stdout
 template is done via String.Template
 https://python.readthedocs.io/en/latest/library/string.html#template-strings
 a key key1 will be applied if there is a matching tag $key1
 if your template contain '$' (ie a shell script) use $$ to escape the symbole.
 all tags in the template file should have a match in the dictionary.
"""

import argparse
import sys
import os
from string import Template
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock_dir', help='lock directory', required=False, default="/tmp")
    parser.add_argument('-t', '--tmpl', help='template file', required=True)
    parser.add_argument('-o', '--output', help='template file', required=False)
    parser.add_argument('--chmod', help='chmod the output file octal notation like 755', required=False)
    parser.add_argument('-d', '--dictionary_key_val', help='-d  key1=value1 -d key2=value2', required=False,
                         action='append', type=lambda kv: kv.split("=",1), dest='key_val')

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

    if args.key_val:
        d = dict(args.key_val)
    else:
        d = {}

    template_file = args.tmpl
    if args.output:
        output = args.output
    else:
        output = None
    tmpl = None
    output_mod=None
    if args.chmod:
        output_mod=int("0o{}".format(args.chmod), 8)

    with open(template_file, 'r') as t:
        try:
            tmpl=Template (t.read())
        except:
            raise

    if output:
        try:
            with open(output, 'w') as f:
                print(tmpl.substitute(d), file=f)
            if output_mod:
                os.chmod(output, output_mod)
        except:
            raise
    else:
        try:
            print(tmpl.substitute(d))
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

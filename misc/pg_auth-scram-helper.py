# -*- mode: python -*-

"""
 implement a helper script to set pg_authid.rolpassword using SCRAM-SHA-256

 code subset borrowed from scramp, An implementation of the SCRAM protocol
 https://github.com/tlocke/scramp  Tony Locke <tlocke@tlocke.org.uk>
 license MIT
"""

import hashlib
import argparse
import hmac as hmaca
from base64 import b64decode, b64encode
from os import urandom
import unicodedata
from stringprep import (
    in_table_a1,
    in_table_b1,
    in_table_c12,
    in_table_c21_c22,
    in_table_c3,
    in_table_c4,
    in_table_c5,
    in_table_c6,
    in_table_c7,
    in_table_c8,
    in_table_c9,
    in_table_d1,
    in_table_d2,
)

def saslprep(source):
    # mapping stage
    #   - map non-ascii spaces to U+0020 (stringprep C.1.2)
    #   - strip 'commonly mapped to nothing' chars (stringprep B.1)
    data = "".join(" " if in_table_c12(c) else c for c in source if not in_table_b1(c))

    # normalize to KC form
    data = unicodedata.normalize("NFKC", data)
    if not data:
        return ""

    # check for invalid bi-directional strings.
    # stringprep requires the following:
    #   - chars in C.8 must be prohibited.
    #   - if any R/AL chars in string:
    #       - no L chars allowed in string
    #       - first and last must be R/AL chars
    # this checks if start/end are R/AL chars. if so, prohibited loop
    # will forbid all L chars. if not, prohibited loop will forbid all
    # R/AL chars instead. in both cases, prohibited loop takes care of C.8.
    is_ral_char = in_table_d1
    if is_ral_char(data[0]):
        if not is_ral_char(data[-1]):
            raise ScramException(
                "malformed bidi sequence", SERVER_ERROR_INVALID_ENCODING
            )
        # forbid L chars within R/AL sequence.
        is_forbidden_bidi_char = in_table_d2
    else:
        # forbid R/AL chars if start not setup correctly; L chars allowed.
        is_forbidden_bidi_char = is_ral_char

    # check for prohibited output
    # stringprep tables A.1, B.1, C.1.2, C.2 - C.9
    for c in data:
        # check for chars mapping stage should have removed
        assert not in_table_b1(c), "failed to strip B.1 in mapping stage"
        assert not in_table_c12(c), "failed to replace C.1.2 in mapping stage"

        # check for forbidden chars
        for f, msg in (
            (in_table_a1, "unassigned code points forbidden"),
            (in_table_c21_c22, "control characters forbidden"),
            (in_table_c3, "private use characters forbidden"),
            (in_table_c4, "non-char code points forbidden"),
            (in_table_c5, "surrogate codes forbidden"),
            (in_table_c6, "non-plaintext chars forbidden"),
            (in_table_c7, "non-canonical chars forbidden"),
            (in_table_c8, "display-modifying/deprecated chars forbidden"),
            (in_table_c9, "tagged characters forbidden"),
            (is_forbidden_bidi_char, "forbidden bidi character"),
        ):
            if f(c):
                raise ScramException(msg, SERVER_ERROR_INVALID_ENCODING)

    return data

class Scram (object):
    LOOKUP = {
        "SCRAM-SHA-1": (hashlib.sha1, False, 4096, 0),
        "SCRAM-SHA-1-PLUS": (hashlib.sha1, True, 4096, 1),
        "SCRAM-SHA-256": (hashlib.sha256, False, 4096, 2),
        "SCRAM-SHA-256-PLUS": (hashlib.sha256, True, 4096, 3),
        "SCRAM-SHA-512": (hashlib.sha512, False, 4096, 4),
        "SCRAM-SHA-512-PLUS": (hashlib.sha512, True, 4096, 5),
        "SCRAM-SHA3-512": (hashlib.sha3_512, False, 10000, 6),
        "SCRAM-SHA3-512-PLUS": (hashlib.sha3_512, True, 10000, 7),
    }

    def __init__ (self, mechanisms="SCRAM-SHA-256"):
        assert mechanisms in [n for n in self.LOOKUP.keys()], "no support for {}".format(mechanisms)
        self.mechanisms = mechanisms
        (
            self.hf,
            self.use_binding,
            self.iteration_count,
            self.strength,
        ) = self.LOOKUP[mechanisms]

    def hmac(hf, key, msg):
        return hmaca.new(key, msg=msg, digestmod=hf).digest()

    def h(hf, msg):
        return hf(msg).digest()

    def xor(bytes1, bytes2):
            return bytes(a ^ b for a, b in zip(bytes1, bytes2))

    def hi(hf, password, salt, iterations):
        u = ui = Scram.hmac(hf, password, salt + b"\x00\x00\x00\x01")
        for i in range(iterations - 1):
            ui = Scram.hmac(hf, password, ui)
            u = Scram.xor(u, ui)
        return u

    def uenc(string):
        return string.encode("utf-8")

    def salted_password(self, password, salt):
        return Scram.hi(self.hf, Scram.uenc(saslprep(password)), salt, self.iteration_count)

    def client_key(self,  salted_password):
        return Scram.hmac(self.hf, salted_password, b"Client Key")

    def stored_key(self, client_key):
        return Scram.h(self.hf, client_key)

    def server_key(self, salted_password):
        return Scram.hmac(self.hf, salted_password, b"Server Key")

class Pgauthid (object):
    def  __init__ (self, mechanisms="SCRAM-SHA-256"):
        self.scram = Scram(mechanisms)
    # /*----------
    # * The format is:
    # * SCRAM-SHA-256$<iteration count>:<salt>$<StoredKey>:<ServerKey>
    # *----------
    # */
    def rolpassword (self, password, salt=None):
       assert self.scram.mechanisms == "SCRAM-SHA-256"
       salt = salt.encode('utf-8') if isinstance(salt, str) else salt
       if salt: assert len (salt) == 16
       salt = urandom (16) if not salt else salt

       salted_password = self.scram.salted_password (password, salt)
       client_key = self.scram.client_key (salted_password)
       stored_key =  self.scram.stored_key (client_key)
       server_key = self.scram.server_key (salted_password)
       return b"SCRAM-SHA-256$" + "{}".format(self.scram.iteration_count).encode('utf-8') + b':' + b64encode(salt) + b'$' + b64encode(stored_key) + b':' + b64encode(server_key)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p','--password', help='role password', required=False, default='')
    parser.add_argument('-s','--salt', help='fixed salt string', required=False, default='')
    args = parser.parse_args()
    p = Pgauthid()
    print (p.rolpassword (args.password, args.salt).decode('ascii'))

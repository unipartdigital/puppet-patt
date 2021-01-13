#!/usr/bin/python3
import os

"""
Simple file locking class

import file_lock as fl
try:
    lock = fl.file_lock("/tmp/myprog.lock")
    with lock:
        time.sleep(360)
except:
    raise

or simply:

import file_lock as fl
lock = fl.file_lock("/tmp/myprog.lock")
with lock:
    time.sleep(360)

"""

class file_lock(object):
    class file_lock_exception (Exception):
        pass

    def __init__(self, file_name):
        self.is_locked = False
        self.lockfile = file_name

    def aquire (self):
        try:
            fd = os.open( self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR )
            with os.fdopen( fd, 'a' ) as f:
                f.write('')
        except FileExistsError:
            raise file_lock.file_lock_exception
        else:
            self.is_locked = True
            return True

    def release (self):
        if self.is_locked:
            os.unlink(self.lockfile)
            self.is_locked = False

    def __enter__(self):
        self.aquire()
        return self

    def __exit__(self, type, value, traceback):
        self.release()

    def __del__(self):
        self.release()

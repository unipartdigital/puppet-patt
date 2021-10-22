#!/usr/bin/python3

import argparse
import yaml
import os
import sys
from tempfile import TemporaryFile
from shutil import copyfileobj, rmtree
import logging
from logging.handlers import TimedRotatingFileHandler
import subprocess
import hashlib
import psycopg2
import fcntl

"""
BackupDumping python wraper around pg_dump and pg_dumpall

dump the global objects (roles and tablespaces) and then each database not in the exclude list
if dumping_root_dir = None dump in stdout
otherwise dump into a directory structure ( dumping_root_dir / db_system_id / 000 )
ooo always contain the latest dump + a stamp file (if all ok)
older dump are rotated into 001, 002 .. dumping_rotate (in reverse order)
dump greater than dumping_rotate are deleted
deletion stop if no more than 2 stamp files are found.

a fd lock ensure that only one script dump in the same directory at a time.
the 000 directory is removed if an exception is raised.
"""

logger = logging.getLogger('backup_pg_dump')

class Config(object):
    def __init__(self):
        self.dumping_db_exclude = []
        self.dumping_db_exclude_default = ['postgres', 'template1', 'template0']
        self.dumping_role_exclude = ['postgres', 'replication', 'rewind_user']
        self.dumping_log_file = None
        self.dumping_log_level = logging.INFO
        self.dumping_root_dir = None
        self.dumping_format = 'c'
        self.dumping_compress = 3
        self.dumping_rotate = 7

    """
    basic equality
    """
    def __eq__(self, other):
        for k in self.__dict__.keys():
            if getattr(self, k) != getattr(other,k): return False
        return True

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

    def to_yaml(self):
        result = yaml.dump(self)
        print (result.replace("!!python/object", "#!!python/object"))
        sys.exit(0)

"""
return (md5sum, file_path) or (None, None) on error
"""
def file_md5sum(file_path=None, file_fd=None):
    try:
        if file_path:
            with open(file_path, 'r') as f:
                file_hexdigest=hashlib.md5(f.read().encode('utf-8')).hexdigest()
        elif file_fd:
            file_fd.seek(0)
            file_hexdigest=hashlib.md5(file_fd.read().encode('utf-8')).hexdigest()
    except:
        return (None, None)
    else:
        return (file_hexdigest, file_path)

def lock_dir (path):
    if path is None: return None
    try:
        lockfd = os.open(path ,os.O_RDONLY)
        fcntl.flock(lockfd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    except:
        raise
    else:
        return lockfd

class BackupInfo(object):
    pass

class BackupDumpingError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return self.message

class DumpGlobalObjectsError(BackupDumpingError):
    pass

class DumpDbError(BackupDumpingError):
    pass

class BackupDumping(object):

    def __init__(self):
        self.pg_dump_all = "pg_dumpall"
        self.pg_dump = "pg_dump"

    def _cmd(self, command, args=[], use_shell=False, fd=None):
        s_out = fd if fd else subprocess.PIPE
        stdout = None
        stderr = None
        status = -1
        try:
            args = args if isinstance(args, list) else [args]
            cmd = command + args
            logger.debug (cmd)
            logger.debug ("_cmd: {}".format (cmd))
            sr = subprocess.run (cmd, stdout=s_out, stderr=subprocess.PIPE,
                                 encoding='utf8', shell=use_shell)
            logger.debug ("_cmd: sr.returncode == {}".format(sr.returncode))
            if sr.returncode == 0:
                status = 0
                stdout = sr.stdout
                if sr.stderr: logger.info(sr.stderr)
            else:
                status = sr.returncode
                stderr = sr.stderr
                if sr.stdout: logger.info (sr.stdout)
                if sr.stderr: logger.error(sr.stderr)
        except Exception as e:
            self.stderr = True
            logger.error (e)
        finally:
            return (stdout, stderr, status)


    def system_identifier(self):
        conn = psycopg2.connect("dbname=postgres")
        try:
            cur = conn.cursor()
            cur.execute("SELECT system_identifier FROM pg_control_system();")
            result = cur.fetchone()
        except:
            raise BackupDumpingError("system identifier error")
        else:
            return result[0]
        finally:
            conn.close()

    def db_list_all(self, exclude=[], exclude_default=['postgres', 'template1', 'template0']):
        exclude = exclude + exclude_default if isinstance(exclude, list) else None
        conn = psycopg2.connect("dbname=postgres")
        try:
            cur = conn.cursor()
            if exclude:
                cur.execute("""
                SELECT d.datname as dbname FROM pg_catalog.pg_database d where d.datname not in %s;
                """, (tuple(exclude),))
            else:
                cur.execute("SELECT d.datname as dbname FROM pg_catalog.pg_database d;")
            result = cur.fetchall()
        except:
            raise BackupDumpingError("db list all error")
        else:
            return ([i[0] for i in result if len(i) > 0])
        finally:
            conn.close()

    def comment (self, starts_with_pattern=[], r=sys.stdin, w=sys.stdout):
        for line in r:
            if line.lower().startswith (tuple ([p.lower() for p in starts_with_pattern])):
                w.write ("--  " + line)
            else:
                w.write (line)

    """
    run 'pg_dumpall --globals-only'
    plain format, no compression
    permit to comment ALTER/CREATE ROLE for role in skip_roles
    """
    def dump_global_objects (self, fd=sys.stdout, file=None,
                             skip_roles=['postgres', 'replication', 'rewind_user']):
        pattern = ["CREATE ROLE {};".format(i) for i in skip_roles]
        pattern = pattern + ["ALTER ROLE {} ".format(i) for i in skip_roles]
        options = ['--file', file] if file else []
        fd = None if file else fd
        fdr, fdw = os.pipe()
        fdr = os.fdopen (fdr)
        try:
            if file:
                result = self._cmd ([self.pg_dump_all], ['--globals-only'] + options, fd=fd)
                try:
                    with open (file, 'r+') as f:
                        with TemporaryFile('w+') as tmp:
                            self.comment (starts_with_pattern=pattern, r=f, w=tmp)
                            tmp.seek(0)
                            l = file_md5sum(file_path=f.name)
                            r = file_md5sum(file_fd=tmp)
                            logger.debug (l)
                            logger.debug (r)
                            if l[0] == r[0] and l[0]:
                                pass
                            else:
                                tmp.seek(0)
                                f.seek(0)
                                copyfileobj (tmp, f)
                                f.truncate()
                                f.flush()
                except:
                    raise
                else:
                    pass
                finally:
                    pass
            else:
                result = self._cmd ([self.pg_dump_all], ['--globals-only'] + options, fd=os.fdopen(fdw))
                self.comment (starts_with_pattern=pattern, r=fdr, w=sys.stdout)
            if result[1] is None and result[2] == 0:
                pass
            else:
                if result[1]: logger.error (result[1])
                raise DumpGlobalObjectsError ("dump global objects error")
        except Exception as e:
            logger.error(e)
            raise
        else:
            if fd: fd.flush()
            logger.info ("dump_global_objects: done")
            return True
        finally:
            fdr.close()

    def dump_db (self, dbname, format='c', compress=0, fd=sys.stdout, file=None):
        if format not in ('p', 'c', 'd', 't'):
            raise DumpDbError ("format {} not in 'p' 'c' 'd' 't'".format (format))
        if format == 'd' and fd == sys.stdout:
            raise DumpDbError ("not a file based output formats, use file targeting a directory")
        if compress not in (0,1,2,3,4,5,6,7,8,9):
            raise DumpDbError ("compress {} not in 0..9".format (compress))
        if format == 't' and compress not in (0,):
            raise DumpDbError ("tar archive format currently does not support compression")
        options = ['--compress', str(compress)]
        options = options + ['--file', file] if file else options
        fd = None if file else fd
        logger.info (options)
        try:
            result = self._cmd ([self.pg_dump], ['-F', format] + options + [dbname], fd=fd)
            if result[1] is None and result[2] == 0:
                pass
            else:
                if result[1]: logger.error (result[1])
                raise DumpGlobalObjectsError ("dump global objects error")
        except Exception as e:
            logger.error(e)
            raise
        else:
            if fd: fd.flush()
            logger.info ("dump_db {}: done".format(dbname))
            return True

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-f','--yaml_config_file', help='config file', required=False)
    parser.add_argument('--yaml_dump', help="dump a sample yaml format config", action='store_true')
    parser.add_argument('-g', '--globals_only', help="dump only global objects, no databases",
                        action='store_true')
    parser.add_argument('-d', '--db', help="dump only databases DB")
    parser.add_argument('-l', '--list_db', help="list all databases", action='store_true')
    parser.add_argument('-c', '--compress', help="compression level 0 (no) .. 9", type=int)
    parser.add_argument('-F', '--dumping_format', help="dumping fmt [p]lain, [c],ustom, [d]irectory, [t]ar")
    parser.add_argument('-D', '--dumping_root_dir', help="dumping direcory use '-' for stdout")

    cfg = Config()
    args = parser.parse_args()
    if args.yaml_dump:
        cfg.to_yaml()
    elif args.yaml_config_file:
        cfg.from_yaml_file (args.yaml_config_file)
    elif any([args.db, args.globals_only, args.list_db]):
        pass
    else:
        parser.print_help()
        sys.exit(11)

    #assert not cfg == Config(), "not configured {}".format(args.yaml_config_file)

    log_handlers=[logging.StreamHandler()]
    if cfg.dumping_log_file:
        time_logger_handler = TimedRotatingFileHandler(
            filename=cfg.dumping_log_file, when='D', # 'H' Hours 'D' Days
            interval=1, backupCount=10, encoding=None, utc=False)
        log_handlers.append(time_logger_handler)

    logging.basicConfig(level=cfg.dumping_log_level,
                        format='%(levelname)s: %(asctime)s:%(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S',
                        handlers=log_handlers)

    pgd = BackupDumping()
    dbs = pgd.db_list_all(
        exclude=cfg.dumping_db_exclude,
        exclude_default=cfg.dumping_db_exclude_default
    )
    if args.list_db:
        print ("{}".format(dbs))
        sys.exit(0)

    system_identifier = pgd.system_identifier()
    compress = args.compress if args.compress is not None else cfg.dumping_compress
    dumping_format = args.dumping_format if args.dumping_format else cfg.dumping_format
    dumping_root_dir = args.dumping_root_dir if args.dumping_root_dir is not None else cfg.dumping_root_dir
    dumping_root_dir = dumping_root_dir if dumping_root_dir != '-' else None
    dumping_dir = os.path.abspath("{}/{}".format(
        dumping_root_dir, system_identifier)) if dumping_root_dir else None
    if dumping_dir:
        try:
            os.mkdir (dumping_dir)
        except FileExistsError:
            pass
        except Exception as e:
            raise

    lockfd = lock_dir (dumping_dir)

    def count_stamp_file (dumping_dir, ring=[]):
        count = 0
        for i in ring:
            stamp = "{}/{}/stamp".format(dumping_dir, i)
            if os.path.exists (stamp): count += 1
        return count

    assert cfg.dumping_rotate > 0 and cfg.dumping_rotate < 1000, "0 < dumping_rotate < 1000"
    ring = ['{:0>3}'.format(i) for i in range(0,cfg.dumping_rotate)]
    ring_max = ['{:0>3}'.format(i) for i in range(cfg.dumping_rotate, 1000)]
    for i in list(set(ring_max) - set(ring)):
        if os.path.isdir ("{}/{}".format(dumping_dir, i)):
            logger.warning ("not part of the ring: {}/{}".format(dumping_dir, i))
    to_delete = "{}/{}".format (dumping_dir, ring[-1])
    stamp_cnt = count_stamp_file(dumping_dir, ring)
    if os.path.isdir (to_delete):
        stamp_cnt = count_stamp_file(dumping_dir, ring)
        if stamp_cnt > 2:
            rmtree(to_delete)
        else:
            logger.warning ("only {} stamp found: skip delete".format (stamp_cnt))
    for idx in reversed (range(0,len(ring))):
        if idx < 1: continue
        newer="{}/{}".format (dumping_dir, ring[idx - 1])
        older="{}/{}".format (dumping_dir, ring[idx])
        if os.path.isdir (newer):
            logger.info ("os.rename({}, {})".format(newer, older))
            try:
                os.rename(newer, older)
            except FileExistsError:
                if stamp_cnt <= 2:
                    logger.warning ("ignore os.rename({}, {})".format(newer, older))
                else:
                    raise
            except Exceptions as e:
                raise
    if dumping_dir:
        dumping_dir = "{}/{}".format (dumping_dir, ring[0])
        try:
            os.mkdir (dumping_dir, mode=0o750)
        except FileExistsError:
            pass
        except Exception as e:
            raise

    try:
        if args.yaml_config_file or args.globals_only:
            logger.info ("dump_global_objects")
            gfile = None if dumping_dir is None else "{}/{}.pg_dump.sql".format(
                dumping_dir, '00-globals-only')
            r = pgd.dump_global_objects(skip_roles=cfg.dumping_role_exclude, file=gfile)
            if args.globals_only is None: sys.exit(not r)

            if args.yaml_config_file or args.db:
                dbs = dbs if not args.db else [d for d in dbs if d == args.db ]
                for d in dbs:
                    logger.info ("dump {}".format (d))
                    db_file=None if dumping_dir is None else "{}/{}.pg_dump.F{}".format(
                        dumping_dir, d, dumping_format)
                    pgd.dump_db (dbname=d,
                                 format=dumping_format,
                                 compress=compress,
                                 file=db_file)
    except Exception as e:
        if os.path.isdir (dumping_dir):
            rmtree(dumping_dir)
        raise
    else:
        if os.path.isdir (dumping_dir):
            stamp = "{}/stamp".format(dumping_dir)
            with open(stamp, 'a'):
                os.utime(stamp, None)

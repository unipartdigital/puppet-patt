# -*- mode: python -*-

import argparse
import yaml
import os
import sys
import json
from types import SimpleNamespace
import logging
from logging.handlers import TimedRotatingFileHandler
import subprocess
from datetime import datetime
from datetime import timedelta
import time
from threading import Lock
import locale
import hashlib
import psycopg2

"""
 wrapper arround wal-g tool, allow to take full backup of a local postgres db at regular interval.
 can be used as a systemd simple service cf: config/backup_walg.service
"""

logger = logging.getLogger('backup_walg')

class Config(object):
    def __init__(self):
        self.backup_cleanup_keep_days = 0
        self.backup_cleanup_keep_hours = 0
        self.backup_cleanup_keep_seconds = 0
        self.backup_cleanup_dry_run = True
        self.backup_full_push_days = 0
        self.backup_full_push_hours = 0
        self.backup_full_push_seconds = 0
        self.backup_log_level = logging.INFO
        self.backup_log_file = None
        self.backup_keep_away_schedule = [
            {'Mon': ['08:00-20:00']},
            {'Tue': ['08:00-20:00']},
            {'Wed': ['08:00-20:00']},
            {'Thu': ['08:00-20:00']},
            {'Fri': ['08:00-20:00']},
            {'Sat': []},
            {'Sun': []}
        ]

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
def file_md5sum(file_path):
    try:
        with open(file_path, 'r') as f:
            file_hexdigest=hashlib.md5(f.read().encode('utf-8')).hexdigest()
    except:
        return (None, None)
    else:
        return (file_hexdigest, file_path)

class BackupInfo(object):
    pass

class BackupWalgError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return self.message

def is_postgres_read_write():
    conn = psycopg2.connect("dbname=postgres")
    try:
        cur = conn.cursor()
        cur.execute("SHOW transaction_read_only;")
        result = cur.fetchone()
        cur.close()
        conn.close()
    except:
        raise
    else:
        if type (result) == tuple:
            return result[0] == 'off'
    finally:
        conn.close()

class BackupWalg(object):
    def __init__(self, command="/usr/local/bin/wal-g"):
        self.command = [command]
        self.walg_version = None
        self.version ()
        self.date_fmt = [] #'%Y-%m-%dT%H:%M:%S.%fZ'
        self.last_backup = None
        self.last_backup_check_time = None
        self.files_md5 = None
        try:
            self.backup_state()
        except:
            pass

    def _walg_cmd(self, args=[], use_shell=False):
        stdout = None
        stderr = None
        status = -1
        try:
            args = args if isinstance(args, list) else [args]
            cmd = self.command + args
            logger.debug (cmd)
            logger.debug ("_walg_cmd: {}".format (cmd))
            sr = subprocess.run (cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 encoding='utf8', shell=use_shell)
            logger.debug ("_walg_cmd: sr.returncode == {}".format(sr.returncode))
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

    def version (self):
        if self.walg_version: return self.walg_version
        r = self._walg_cmd("--version")
        self.walg_version = r[0].split()[2] if r[2] == 0 and r[0] else None
        return self.walg_version

    """
    return a list of backups found via wal-g backup-list or []
    order is reversed most recent backup first
    """
    def _backup_list (self):
        r = self._walg_cmd(['backup-list', '--detail', '--json'])
        lobj = json.loads(r[0], object_hook=lambda d: SimpleNamespace(**d)) if r[2] == 0 else []
        for e in reversed(lobj):
            if e.date_fmt not in self.date_fmt: self.date_fmt.append(e.date_fmt)
            yield e

    def _last_backup (self):
        for i in self._backup_list():
            self.last_backup = i
            self.last_backup_check_time = datetime.utcnow()
            break

    def backup_state (self, update_seconds=1800):
        update=timedelta(days=0, hours=0, seconds=update_seconds)
        now = datetime.utcnow()
        if self.last_backup_check_time and (now - self.last_backup_check_time) > update:
            self._last_backup ()
        if not self.last_backup:
            self._last_backup ()
        return self.last_backup

    """
    db dir backup
    """
    def backup_local_full(self, db_directory=None):
        db_directory = db_directory if db_directory else os.getenv('PGDATA', default='')
        assert db_directory, "backup_local_full db_directory not set"
        r = self._walg_cmd(['backup-push', db_directory, '--full'])
        try:
            assert r[2] == 0, "Error: backup_local_full"
        except AssertionError as e:
            raise BackupWalgError(r[1]) from e

    """
    delete backup older than days, hours, secondes from now
    """
    def backup_cleanup_keep (self, days=0, hours=0, seconds=0, dry_run=True):
        now = datetime.utcnow()
        delta = timedelta(days=days, hours=hours, seconds=seconds)
        up_to = now - delta
        assert up_to != now, "Error: {} == {}".format (up_to, now)
        logger.info("cleanup < {} start".format(up_to.strftime('%Y-%m-%dT%H:%M:%S.%fZ')))
        options = [] if dry_run else ['--confirm']
        r = self._walg_cmd(['delete', 'before', up_to.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                            '--use-sentinel-time'] + options)
        try:
            assert r[2] == 0, "Error: backup_cleanup_up_to"
        except AssertionError as e:
            raise BackupWalgError(r[1]) from e
        else:
            logger.info("cleanup < {} end".format(up_to.strftime('%Y-%m-%dT%H:%M:%S.%fZ')))

"""
 return abbreviated weekday name (e.g., Sun) using the 'C' LC_TIME
"""
def week_day(time):
    with Lock():
        try:
            lc_time = locale.setlocale(locale.LC_TIME)
            locale.setlocale(locale.LC_TIME, "C")
            return time.strftime("%a")
        finally:
            locale.setlocale(locale.LC_TIME, lc_time)

"""
 return the remaing seconds before leaving the keep away (if in keep away schedule)
 return False otherwise
"""
def is_keep_away_schedule (keep_away_schedule=[]):
    now = datetime.utcnow()
    now_day_name = week_day(now)
    today_kas = [val for sublist in [d[k] for d in keep_away_schedule for k,v in d.items() if
     k.lower() == week_day(now).lower()] for val in sublist]
    r = [(l,s,h) for l,s,h in [i.rpartition('-') for i in today_kas if i and '-' in i and ':' in i]]
    for i in r:
        try:
            lh, s, lm = i[0].rpartition(':')
            hh, s, hm = i[2].rpartition(':')
            lh = int (lh)
            lm = int (lm)
            hh = int (hh)
            hm = int (hm)
            assert not (hh == 0 and hm == 0), "day last is 23:59"
            assert (lh < 24 and lm < 60), "{} < 24 and {} < 60".format (hh, hm)
            assert (hh < 24 and hm < 60), "{} < 24 and {} < 60".format (hh, hm)
            assert lh <= hh, "range check error ({} < {})".format (lh, hh)
        except:
            logger.error ("is_keep_away_schedule",exc_info=True)
            continue
        else:
            l = timedelta(days=0, hours=lh, seconds=lm * 60)
            h = timedelta(days=0, hours=hh, seconds=hm * 60)
            n = timedelta(days=0, hours=now.hour, minutes=now.minute, seconds=now.second)

            logger.debug ("is_keep_away_schedule ({} < {}) and ({} < {}) -> {}".format(
                l, n, n, h, (l < n) == True and (n < h) == True))
            if (l < n) == True and (n < h) == True:
                logger.debug("l {}".format(l))
                logger.debug("n {}".format(n))
                logger.debug("h {}".format(h))
                return (h - n).total_seconds()
    return False

def backup_schedule (cleanup_keep_days=0,
                     cleanup_keep_hours=0,
                     cleanup_keep_seconds=600,
                     cleanup_dry_run=True,
                     fbackup_push_days=0,
                     fbackup_push_hours=0.1,
                     fbackup_push_seconds=60,
                     keep_away_schedule=[],
                     files_watch=[]):

    bwg = BackupWalg()
    sleep_counter = 2
    while True:
        if not is_postgres_read_write():
            logger.warning ("attempt to backup a read only db")
            time.sleep(360)
            continue
        if not bwg.last_backup:
            bwg.backup_local_full()
            bwg.backup_state()
        else:
            if not bwg.files_md5:
                bwg.files_md5 = [file_md5sum(i) for i in files_watch]
            tmp_md5sum = [file_md5sum(i) for i in files_watch]
            for f5 in bwg.files_md5:
                if f5 not in tmp_md5sum:
                    logger.info ("files_watch: {} changed".format(f5))
                    raise BackupWalgError("files_watch: {} changed".format(f5))

            k = is_keep_away_schedule(keep_away_schedule)
            if k:
                logger.info("keep_away_schedule: sleep {} seconds".format(k))
                time.sleep(k/2)
                continue
            bwg.backup_cleanup_keep (
                days=cleanup_keep_days,
                hours=cleanup_keep_hours,
                seconds=cleanup_keep_seconds,
                dry_run=cleanup_dry_run
            )
            last_backup_time = datetime.strptime(bwg.last_backup.start_time, bwg.last_backup.date_fmt)
            now = datetime.utcnow()
            schedule = timedelta (
                days=fbackup_push_days, hours=fbackup_push_hours, seconds=fbackup_push_seconds)
            if now - last_backup_time >= schedule:
                bwg.backup_local_full()
                bwg.backup_state()
                sleep_counter = 2
            else:
                logger.info ("skip backup full: {} - {} < {}".format(now, last_backup_time, schedule))

            remain = schedule - (now - last_backup_time)
            if remain.total_seconds() > 0:
                logger.info ("remain: {}".format (remain))
                sleep_duration = min (schedule / sleep_counter, remain)
            else:
                sleep_duration = schedule / sleep_counter
            sleep_duration = timedelta (seconds=sleep_duration.total_seconds())
            logger.info ("sleep {}".format(sleep_duration))
            time.sleep(sleep_duration.total_seconds())
            sleep_counter = sleep_counter + 1

if __name__ == "__main__":

    cfg = Config()
    parser = argparse.ArgumentParser()
    parser.add_argument('-f','--yaml_config_file', help='config file', required=False)
    parser.add_argument('--yaml_dump', help="dump a sample yaml format config",
                         action='store_true', required=False)

    args = parser.parse_args()
    if args.yaml_dump:
        cfg.to_yaml()
    elif args.yaml_config_file:
        cfg.from_yaml_file (args.yaml_config_file)
    else:
        parser.print_help()
        sys.exit(11)

    assert not cfg == Config(), "not configured {}".format(args.yaml_config_file)

    log_handlers=[logging.StreamHandler()]
    if cfg.backup_log_file:
        time_logger_handler = TimedRotatingFileHandler(
            filename=cfg.backup_log_file, when='D', # 'H' Hours 'D' Days
            interval=1, backupCount=10, encoding=None, utc=False)
        log_handlers.append(time_logger_handler)

    logging.basicConfig(level=cfg.backup_log_level,
                        format='%(levelname)s: %(asctime)s:%(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S',
                        handlers=log_handlers)

    backup_schedule (cleanup_keep_days=cfg.backup_cleanup_keep_days,
                     cleanup_keep_hours=cfg.backup_cleanup_keep_hours,
                     cleanup_keep_seconds=cfg.backup_cleanup_keep_seconds,
                     cleanup_dry_run=cfg.backup_cleanup_dry_run,
                     fbackup_push_days=cfg.backup_full_push_days,
                     fbackup_push_hours=cfg.backup_full_push_hours,
                     fbackup_push_seconds=cfg.backup_full_push_seconds,
                     keep_away_schedule=cfg.backup_keep_away_schedule,
                     files_watch=[args.yaml_config_file, os.path.abspath(__file__)])

import time
import sqlite3
import os
import logging
logging.basicConfig()
logger = logging.getLogger(os.path.basename(__file__))
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
# logger.setLevel(logging.ERROR)

"""
 recorder
  allow to record in a sqlite3 db the statvfs of each mount point
  at regular interval (interval can be as low as 0.3 second).

 player
  dump the data stored by the recorder for a specified mount point
"""

class PersistenceSQL3(object):
    def __init__(self, database):
        self.sql3 = sqlite3.connect(database=database)
    def __enter__(self):
        return self.sql3
    def __exit__(self, type, value, traceback):
        self.sql3.close()

class SystemService(object):
    class Fs(object):
        def __init__(self, path=None, statvfs=None):
            self.path = path
            self.statvfs = statvfs

    def _default_db_path():
        p = "{}/.cache".format(os.path.expanduser("~"))
        if os.path.isdir (p) :
            return "{}/patt_monitoring-fs.sql3".format (p)
        return "/var/tmp/patt_monitoring-fs-{}.sql3".format(os.getuid())

    def local_mounts(exclude_path=[]):
        result=[]
        with open ("/proc/mounts") as mf:
            for line in mf.readlines():
                if line.startswith("/dev/"):
                    tmp = line.split()[1]
                    if tmp in exclude_path:
                        pass
                    else:
                        result.append(line.split()[1])
        return result

    def statvfs (self):
        self.fs = [self.Fs(path=n, statvfs=os.statvfs(n)) for n in self.local_mounts]
        self.stamp = time.mktime(time.gmtime())


    """
    """
    def db_create (self):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                cur.execute("""create table if not exists stat_vfs
                (
                 id integer primary key,
                 name text,
                 fs_total integer,
                 fs_avail integer,
                 inode_total integer,
                 inode_avail integer,
                 begin_stamp integer,
                 renew_stamp integer
                );
                """)
                cur.execute(
                    "select count (id) from stat_vfs;")
                r = cur.fetchone()
                if r[0] < 1:  # initialize with first call foreach fs
                    m_div = 1024 / 1024
                    for i in self.fs:
                        f_bsize = i.statvfs.f_bsize
                        name = i.path
                        f_total = i.statvfs.f_blocks * f_bsize / m_div
                        f_avail = i.statvfs.f_bavail * f_bsize / m_div
                        inode_total = i.statvfs.f_files
                        inode_avail = i.statvfs.f_favail
                        begin_stamp = self.stamp
                        renew_stamp = self.stamp

                        cur.execute("""insert into stat_vfs
                        (name, fs_total, fs_avail, inode_total, inode_avail, begin_stamp, renew_stamp)
                        values (?, ?, ?, ?, ?, ?, ?);
                        """,(name, f_total, f_avail, inode_total, inode_avail, begin_stamp, renew_stamp))
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()

    def __init__(self, database="{}".format(f"{_default_db_path()}"), exclude_path=[], mode='recorder'):
        self.database=database
        if mode == 'recorder':
            self.local_mounts = SystemService.local_mounts(exclude_path=exclude_path)
            self.statvfs()
            self.db_create()
        else:
            self.fs = []

    def statvfs_upsert (self):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                self.statvfs ()
                m_div = 1024 / 1024
                for i in self.fs:
                    f_bsize = i.statvfs.f_bsize
                    name = i.path
                    f_total = i.statvfs.f_blocks * f_bsize / m_div
                    f_avail = i.statvfs.f_bavail * f_bsize / m_div
                    inode_total = i.statvfs.f_files
                    inode_avail = i.statvfs.f_favail
                    begin_stamp = self.stamp
                    renew_stamp = self.stamp
                    cur.execute("""
                    update stat_vfs set renew_stamp = ? where
                    id = (select id from stat_vfs where
                    name = ? and
                    fs_total = ? and
                    fs_avail = ? and
                    inode_total = ? and
                    inode_avail = ?
                    order by id desc limit 1) and
                    id = (select id from stat_vfs where name = ? order by id desc limit 1);
                    """,(renew_stamp, name, f_total, f_avail, inode_total, inode_avail, name))

                    cur.execute("""insert into stat_vfs
                    (name, fs_total, fs_avail, inode_total, inode_avail, begin_stamp, renew_stamp)
                    select ?, ?, ?, ?, ?, ?, ? where (select Changes() = 0);
                    """, (name, f_total, f_avail, inode_total, inode_avail, begin_stamp, renew_stamp))
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()

    def statvfs_list_mnt (self):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                cur.execute("""
                select distinct (name) from stat_vfs;
                """)
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [i for i in c][0]


    """
    """
    def statvfs_get_data (self, name, stamp_start=None, step=None, stamp_stop=None):
        #assert name in [n.path for n in self.fs]
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
            logger.debug("param name: {}".format(name))
            logger.debug("param stamp_start: {}".format(stamp_start))
            logger.debug("param stamp_stop: {}".format(stamp_stop))

            if not stamp_start:
                try:
                    cur = db3.cursor()
                    cur.execute("""
                    select min (begin_stamp) from stat_vfs where stat_vfs.name = ?;
                    """, (name,))
                except Exception as e:
                    logger.error (e)
                    raise
                else:
                    stamp_start = [c for c in cur][0][0]
                    logger.debug ("statvfs_get_data min_stamp = {}".format(stamp_start))
                    assert int(stamp_start)

            if not stamp_stop:
                try:
                    cur = db3.cursor()
                    cur.execute("""
                    select max (renew_stamp) from stat_vfs where stat_vfs.name = ?;
                    """, (name,))
                except Exception as e:
                    logger.error (e)
                    raise
                else:
                    stamp_stop = [c for c in cur][0][0]
                    logger.debug ("statvfs_get_data max_stamp = {}".format(stamp_stop))
                    assert int(stamp_stop)

            if not step:
                try:
                    cur = db3.cursor()
                    cur.execute("""
                    SELECT MIN (renew_stamp - begin_stamp) from stat_vfs where name = ? and
                    renew_stamp <> begin_stamp and
                    ? <= stat_vfs.begin_stamp and
                    ? >= stat_vfs.renew_stamp;
                    """, (name, stamp_start, stamp_stop))
                except Exception as e:
                    logger.error (e)
                    raise
                else:
                    step = [c for c in cur][0][0]
                    logger.debug ("statvfs_get_data min_step = {}".format(step))
                    step = step if step else 3
            try:
                cur = db3.cursor()
                cur.execute("""
                select id, stamp, fs_total, fs_avail, inode_total, inode_avail from stat_vfs,
                (with recursive stamps(stamp) as (
                   values(?)
                   union all
                   select stamp + ?
                   from stamps
                   where stamp < ?
                 )
                 select stamp from stamps
                ) where stat_vfs.name = ? and
                stamp >= stat_vfs.begin_stamp and
                stamp <= stat_vfs.renew_stamp;
                """, (stamp_start, step, stamp_stop, name))
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [r for r in c]

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='mode')

    recorder = subparsers.add_parser('recorder')
    recorder.add_argument('-x','--exclude_path', help='exclude mount point', action='append', required=False, default=[])
    recorder.add_argument('-i', '--interval', help='min time between event recording', required=False, type=float)

    player = subparsers.add_parser('player')
    player.add_argument('-l', '--list', help='list all recorded mount point', required=False, action="store_true")
    player.add_argument('-n', '--name', help='data for (mount point)', required=False)
    player.add_argument('--stamp_start', help='data after', required=False)
    player.add_argument('--stamp_stop',  help='data befor', required=False)
    player.add_argument('-i', '--irange', help='interpolation range ', required=False)

    args = parser.parse_args()

    try:
        assert args.mode
    except AssertionError:
        parser.print_help()

    if args.mode == 'recorder':
        ss = SystemService(exclude_path=args.exclude_path)
        interval = args.interval if args.interval else 0.3
        assert float(interval)
        while True:
            ss.statvfs_upsert()
            time.sleep(interval)
    elif args.mode == 'player':
        name =  args.name
        ssp = SystemService(mode='player')
        if args.list:
            [print (m) for m in ssp.statvfs_list_mnt()]
        else:
            try:
                assert args.name
            except AssertionError:
                player.print_help()
            else:
                [print (str(i)[1:-1]) for i in ssp.statvfs_get_data(args.name, stamp_start=args.stamp_start, step=args.irange, stamp_stop=args.stamp_stop)]

import time
import sqlite3
import os
import logging
from datetime import datetime, timezone
from datetime import timedelta
from contextlib import nullcontext

logger = logging.getLogger(os.path.basename(__file__))
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
# logger.setLevel(logging.ERROR)

"""
 recorder
  allow to record in a sqlite3 db the statvfs of each mount point
  at regular interval (interval can be as low as 0.3 second).

 player
  dump the data stored by the recorder for a specified mount point
  plot the data stored by the recorder for a specified mount point
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

    def _default_db_path(name="patt_monitoring-fs.sql3"):
        p = "{}/.cache".format(os.path.expanduser("~"))
        if os.path.isdir (p) :
            return "{}/{}".format (p, name)
        return "/var/tmp/{}-{}.sql3".format(name, os.getuid())

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
    PRAGMA journal_mode=WAL;
    PRAGMA schema.journal_size_limit=6815744; (6.5MB)
    https://www.sqlite.org/wal.html
    update stat_vfs_schema_version using ie `date +%s` on schema change
    """
    def db_create (self):
        stat_vfs_schema_version = '1631441163';
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                cur.execute("""create table if not exists stat_vfs_schema_version
                (version TEXT NOT NULL, id INT DEFAULT 1 NOT NULL
                CHECK(id == 1), UNIQUE (id));
                """)
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()
            try:
                cur = db3.cursor()
                cur.execute(
                    "select version from stat_vfs_schema_version;")
                r = cur.fetchone()
                if r and r[0] == stat_vfs_schema_version:
                    logger.debug("skip remaining db_update: {} == {}".format(r[0], stat_vfs_schema_version))
                    return
                # skip the remaining process
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
                cur.execute("create index if not exists stat_vfs_name_idx on stat_vfs(name);")
                try:
                    sqlite3_maj = int(sqlite3.sqlite_version.split('.')[0])
                    sqlite3_min = int(sqlite3.sqlite_version.split('.')[1])
                    use_journal_mode_wal = sqlite3_maj >= 3 and sqlite3_min > 7
                except:
                    use_journal_mode_wal = None
                logger.debug("db_create: use_journal_mode_wal == {}".format( use_journal_mode_wal))
                if use_journal_mode_wal:
                    cur.execute("""
                    PRAGMA journal_mode=WAL;
                    """)
                    cur.execute("""
                    PRAGMA journal_size_limit=6815744;
                    """)
                for row in db3.execute("SELECT journal_mode from PRAGMA_journal_mode;"):
                    logger.info("db_create: journal_mode {}".format (row[0]))

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
                cur.execute("""
                UPDATE stat_vfs_schema_version SET version = ? WHERE id = 1;
                """, (stat_vfs_schema_version,))
                cur.execute("""
                -- If no update happened (i.e. the row didn't exist) then insert one
                INSERT INTO  stat_vfs_schema_version (id, version) select 1, ?
                WHERE (Select Changes() = 0);
                """, (stat_vfs_schema_version,))
                db3.commit()

    def __init__(self, database="{}".format(f"{_default_db_path()}"), exclude_path=[], mode='recorder'):
        self.database=database
        self.last_db_cleanup = datetime.now(timezone.utc)
        if mode == 'recorder':
            self.local_mounts = SystemService.local_mounts(exclude_path=exclude_path)
            self.statvfs()
            self.db_create()
        else:
            self.fs = []

    """
    param:
    max_keep_sample = 15000, numer of row to keep should not be too high or max_db_size may have no effect.
    max_db_size=1024, when dbsize > max_db_size in KB, cleanup (delete + vacuum) each hour
    """
    def db_cleanup (self, max_keep_sample=15000, max_db_size=1024, cleanup_interval=timedelta(hours=1)):
        if datetime.now(timezone.utc) - self.last_db_cleanup < cleanup_interval: return
        if os.path.exists(self.database):
            db_size = os.stat(os.path.abspath(self.database)).st_size
            if int(db_size / 1024) < int(max_db_size): return

        with PersistenceSQL3(database=self.database) as db3:
            # db3.set_trace_callback(logger.debug)
            db3.row_factory = sqlite3.Row
            try:
                logger.debug ("db_cleanup")
                cur = db3.cursor()
                cur.execute("""
                SELECT name, count (*) as cnt from stat_vfs
                GROUP BY name
                HAVING cnt >= ?
                ORDER BY cnt DESC;""",
                            [max_keep_sample])
                r = cur.fetchall()
                if not r:
                    self.last_db_cleanup = datetime.now(timezone.utc)
                    return
                for e in r:
                    logger.info ("db_cleanup: {}".format([i for i in e]))
                    cur.execute("""
                    DELETE from stat_vfs where id in
                    (SELECT id from stat_vfs where name = ? order by id DESC LIMIT
                    (SELECT (SELECT count (*) from stat_vfs where name = ?) - ?)
                    );
                    """,
                                (e["name"], e["name"], max_keep_sample))
            except:
                raise
            else:
                retry = 1200
                count = 0
                for i in range(retry):
                    count += 1
                    try:
                        db3.commit()
                    except sqlite3.OperationalError:
                        if count % 10 == 0: logger.debug("retry: {}/{}".format(count, retry))
                        if count == retry: raise
                        time.sleep(0.1)
                        continue
                    else:
                        break
                self.last_db_cleanup = datetime.now(timezone.utc)

        with PersistenceSQL3(database=self.database) as db3:
            try:
                db3.isolation_level = None
                db3.execute('VACUUM')
                db3.isolation_level = ''
            except:
                raise

    def statvfs_upsert (self, db_connection=None):
        if db_connection is None:
            cm = PersistenceSQL3(database=self.database)
        else:
            cm = nullcontext(db_connection)
        # logger.debug ("{}".format(cm))
        with cm as db3:
            # db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
            self.db_cleanup()
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
                retry = 1200
                count = 0
                for i in range(retry):
                    count += 1
                    try:
                        db3.commit()
                    except sqlite3.OperationalError:
                        if count % 10 == 0: logger.debug("retry: {}/{}".format(count, retry))
                        if count == retry: raise
                        time.sleep(0.1)
                        continue
                    else:
                        break

    def statvfs_list_mnt (self):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                cur.execute("""
                select distinct (name) from stat_vfs order by length(name),name;
                """)
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [i for i in c][0]


    """
    """
    def statvfs_get_data (self, name, stamp_start=None, step=None, stamp_stop=None, smooth=False):
        dt_format = "%Y-%m-%dT%H:%M:%S%Z"
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
            else:
                try:
                    stamp_start = int(float(stamp_start))
                except ValueError:
                    stamp_start = time.mktime(time.strptime(stamp_start, dt_format))
                assert int(float(stamp_start))

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
            else:
                try:
                    stamp_stop = int(float(stamp_stop))
                except ValueError:
                    stamp_stop = time.mktime(time.strptime(stamp_stop, dt_format))
                assert int(float(stamp_stop))

            if stamp_start < 0:
                stamp_start = stamp_stop + stamp_start

            assert stamp_start < stamp_stop

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
                # moving avg
                if smooth:
                    cur.execute("""
                    select id, stamp, fs_total,
                    avg (fs_avail) OVER (order by id ROWS BETWEEN ? PRECEDING AND CURRENT ROW),
                    inode_total,
                    avg (inode_avail) OVER (order by id ROWS BETWEEN ? PRECEDING AND CURRENT ROW)
                    from stat_vfs,
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
                    """, (smooth, smooth, stamp_start, step, stamp_stop, name))
                # raw
                else:
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
    """
    """
    def statvfs_get_min_fs(self, name=None, stamp_start=None, stamp_stop=None, limit=None):
        dt_format = "%Y-%m-%dT%H:%M:%S%Z"
        limit = 10 if limit is None else limit
        assert limit > 0 and limit < 30

        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            # db3.set_trace_callback(logger.debug)
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
            else:
                try:
                    stamp_start = int(float(stamp_start))
                except ValueError:
                    stamp_start = time.mktime(time.strptime(stamp_start, dt_format))
                assert int(float(stamp_start))

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
            else:
                try:
                    stamp_stop = int(float(stamp_stop))
                except ValueError:
                    stamp_stop = time.mktime(time.strptime(stamp_stop, dt_format))
                assert int(float(stamp_stop))

            if stamp_start < 0:
                stamp_start = stamp_stop + stamp_start

            logger.debug("statvfs_get_min_fs param name: {}".format(name))
            logger.debug("statvfs_get_min_fs param stamp_start: {}".format(stamp_start))
            logger.debug("statvfs_get_min_fs param stamp_stop: {}".format(stamp_stop))
            assert stamp_start < stamp_stop

        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            if logger.level == logging.DEBUG:
                db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                cur.execute("""
                select id, begin_stamp, fs_total, cast ((m / 1024 / 1024) as int),
                (fs_total - m) / fs_total * 100.0,  row_number() OVER(ORDER BY id) as rn  from
                (select id, begin_stamp, fs_total, cast (min(fs_avail) as float) as m
                from stat_vfs where name = ?  and
                ((stat_vfs.begin_stamp between ? and ?) or
                 stat_vfs.renew_stamp between ? and ?)
                group by id order by min(fs_avail) ASC limit ?) order by id;
                """, (name, stamp_start, stamp_stop, stamp_start, stamp_stop, limit))
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [r for r in c]

class GnuPlot(object):
    def __init__(self, gnuplot="/usr/bin/gnuplot"):
        from subprocess import Popen, PIPE
        self.gnuplot = Popen(args=[gnuplot], stdin=PIPE, stderr=PIPE)

    def send (self, input):
        if not isinstance(input, list):
            input = [input]
        for i in input:
            self.gnuplot.stdin.write(i.encode("utf-8") + "\n".encode("utf-8"))
            self.gnuplot.stdin.flush()
            logger.debug(i)

    def close (self):
        try:
            r = self.gnuplot.communicate("quit".encode("utf-8") + "\n".encode("utf-8"))
            self.gnuplot.terminate()
        except:
            self.gnuplot.kill()
            raise

if __name__ == "__main__":

    log_handlers=[logging.StreamHandler()]
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)s: %(asctime)s:%(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S',
                        handlers=log_handlers)

    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='mode')

    recorder = subparsers.add_parser('recorder')
    recorder.add_argument('-x','--exclude_path', help='exclude mount point', action='append',
                          required=False, default=[])
    recorder.add_argument('-i', '--interval', help='min time between event recording',
                          required=False, type=float)

    player = subparsers.add_parser('player')
    player.add_argument('-f', '--file', help='use specified db file', required=False)
    player.add_argument('-l', '--list', help='list all recorded mount point',
                        required=False, action="store_true")
    player.add_argument('-n', '--name', help='data for (mount point)', required=False)
    player.add_argument('--stamp_start',
                        help='data after, a negative value n, mean n til last recorded value',
                        required=False)
    player.add_argument('--stamp_stop',  help='data before', required=False)
    player.add_argument('-i', '--irange', help='interpolation range (ms)', required=False, type=int)
    player.add_argument('-s', '--smooth', help='apply n points window avg  (7 looks good)',
                        required=False, type=int)
    player.add_argument('-m', '--min_fs', help='get only n minimals fs value on given time window', type=int)

    player.add_argument('-p', '--plot', help='plot', required=False, action='store_true', default=None)

    args = parser.parse_args()

    try:
        assert args.mode
    except AssertionError:
        parser.print_help()

    if args.mode == 'recorder':
        ss = SystemService(exclude_path=args.exclude_path)
        interval = args.interval if args.interval else 0.3
        assert float(interval)

        with PersistenceSQL3(database=ss.database) as db3:
            while True:
                ss.statvfs_upsert(db3)
                time.sleep(interval)
    elif args.mode == 'player':
        name =  args.name
        if args.file:
            ssp = SystemService(database=args.file, mode='player')
        else:
            ssp = SystemService(mode='player')
        if args.list:
            [print (m) for m in ssp.statvfs_list_mnt()]
        else:
            try:
                assert args.name
            except AssertionError:
                player.print_help()
            else:
                stamp_start=args.stamp_start
                step=args.irange
                assert step is None or step > 0
                stamp_stop=args.stamp_stop
                smooth=args.smooth
                assert smooth is None or smooth >= 0
                if args.plot is None:
                    if args.min_fs:
                        [print (str(i)[1:-1]) for i in ssp.statvfs_get_min_fs(
                            args.name, stamp_start=stamp_start, stamp_stop=stamp_stop, limit=args.min_fs
                        )]
                    else:
                        [print (str(i)[1:-1]) for i in ssp.statvfs_get_data(
                            args.name, stamp_start=stamp_start, step=step, stamp_stop=stamp_stop,
                            smooth=smooth)]
                else:
                    from tempfile import NamedTemporaryFile
                    with NamedTemporaryFile(mode='w+', encoding='utf-8') as data_file:
                        p = GnuPlot()
                        p.send ("set xtics rotate")
                        p.send (["set xdata time",
                                 'set timefmt "%s"',
                                 'set format x "%Y-%m-%dT%H:%M:%SUTC"'])
                        [print (str(i)[1:-1], file=data_file) for i in ssp.statvfs_get_data(
                        args.name, stamp_start=stamp_start, step=step, stamp_stop=stamp_stop,
                            smooth=smooth)]
                        data_file.flush()
                        if os.stat(data_file.name).st_size == 0:
                            p.close()
                            raise ValueError ('no data')
                        p.send ("""
# define axis
# remove border on top and right and set color to gray
set style line 11 lc rgb '#808080' lt 1
set border 3 back ls 11
set tics nomirror
# define grid
set style line 12 lc rgb '#808080' lt 0 lw 1
set grid back ls 12

# color definitions
set style line 1 lc rgb '#8b1a0e' pt 1 ps 1 lt 1 lw 2 # --- red
set style line 2 lc rgb '#5e9c36' pt 9 ps 1 lt 1 lw 2 # --- green
set key bottom right Left
set yrange[0:130]

plot "{0}" using 2:(($3 - $4) * 100 / $3) with lines title '% space use' ls 1, \
""    using 2:(($5 - $6) * 100 / $5) with lines title '% inodes use' ls 2,     \

""".format(data_file.name, name))
                        while True:
                            try:
                                print ("'q' + 'enter' to quit")
                                quit = input()
                                assert quit == 'q'
                            except AssertionError:
                                p.send ("replot")
                                continue
                            else:
                                break
                        p.close()

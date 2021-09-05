from df_recorder import SystemService, PersistenceSQL3, sqlite3, time, logging, os, GnuPlot

logging.basicConfig()
logger = logging.getLogger(os.path.basename(__file__))
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)
# logger.setLevel(logging.ERROR)

"""
all functions are bounded to max 1hour (3600 seconds) worth of data
"""

class MonitorFs(SystemService):

    """
    get the data
    default 1800 seconds arround the pivot ±30min
    """
    def statvfs_b_get_data (self, mnt_name=None, stamp_pivot=None, stamp_delta=1800):
        dt_format = "%Y-%m-%dT%H:%M:%S%Z"
        step = 1 if stamp_delta <= 3600 else 1
        #assert stamp_delta < 3600
        if stamp_pivot is None:
            stamp_pivot = time.mktime(time.gmtime()) - stamp_delta
        try:
            stamp_pivot = int(float(stamp_pivot))
        except ValueError:
            stamp_pivot = time.mktime(time.strptime(stamp_pivot, dt_format))
        assert int(float(stamp_pivot))
        stamp_start = stamp_pivot - stamp_delta
        stamp_stop = stamp_pivot  + stamp_delta
        assert (stamp_start < stamp_stop) and (stamp_start > 0)
        return self.statvfs_get_data (
            mnt_name, stamp_start=stamp_start, step=step, stamp_stop=stamp_stop, smooth=False
        )

    """
    """
    def statvfs_b_get_fs_agg(self, mnt_name=None, stamp_pivot=None, stamp_delta=1800,
                                 agg="min", limit=None):
        dt_format = "%Y-%m-%dT%H:%M:%S%Z"
        assert agg.lower() in ("min", "max")
        if limit is None:
            if stamp_delta <= 60:
                limit = 5
            elif stamp_delta <= 1800:
                limit = 7
            else:
                limit = 10
        assert limit > 0 and limit < 30
        step = None if stamp_delta <= 3600 else 3
        assert stamp_delta < 43200
        if stamp_pivot is None:
            stamp_pivot = time.mktime(time.gmtime()) - stamp_delta
        try:
            stamp_pivot = int(float(stamp_pivot))
        except ValueError:
            stamp_pivot = time.mktime(time.strptime(stamp_pivot, dt_format))
        assert int(float(stamp_pivot))
        stamp_start = stamp_pivot - stamp_delta
        stamp_stop = stamp_pivot  + stamp_delta
        assert (stamp_start < stamp_stop) and (stamp_start > 0)

        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                cur.execute("""
                select id, begin_stamp, fs_total, cast ((m / 1024 / 1024) as int),
                (fs_total - m) / fs_total * 100.0,  row_number() OVER(ORDER BY id) as rn  from
                (select id, begin_stamp, fs_total, cast ({0}(fs_avail) as float) as m
                from stat_vfs where name = ?  and
                ((stat_vfs.begin_stamp between ? and ?) or
                 stat_vfs.renew_stamp between ? and ?)
                group by id order by min(fs_avail) ASC limit ?) order by id;
                """.format(agg), (mnt_name, stamp_start, stamp_stop, stamp_start, stamp_stop, limit))
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [r for r in c]

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name', help='data for (mount point)', required=True)
    parser.add_argument('-p', '--stamp_pivot', help='get delta data around p', required=False)
    parser.add_argument('-d', '--stamp_delta', help='number of seconds', default=3600, type=int)

    args = parser.parse_args()
    mnt_name=args.name
    stamp_pivot=args.stamp_pivot
    stamp_delta=args.stamp_delta

    ssp = MonitorFs()


    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w+', encoding='utf-8') as data_file:
        with NamedTemporaryFile(mode='w+', encoding='utf-8') as max_data_file:

            p = GnuPlot()

            [print (str(i)[1:-1], file=max_data_file) for i in ssp.statvfs_b_get_fs_agg(
                mnt_name=mnt_name,
                stamp_pivot=stamp_pivot,
                stamp_delta=stamp_delta)]
            max_data_file.flush()
            # if os.stat(max_data_file.name).st_size == 0:
            #     p.close()
            #     raise ValueError ('no data')
            p.send ("reset session")
            p.send ("set xtics rotate")
            p.send("set title 'disk usage for {} ending the '.strftime('%Y-%m-%d UTC', time(0))".format(
                args.name))
            p.send (["set xdata time",
                     'set timefmt "%s"',
                     '#set format x "%Y-%m-%dT%H:%M:%SUTC"',
                     'set format x "%H:%M:%S"',
                     'set datafile separator ","'])

            [print (str(i)[1:-1], file=data_file) for i in ssp.statvfs_b_get_data(
                mnt_name=mnt_name,
                stamp_pivot=stamp_pivot,
                stamp_delta=stamp_delta)]

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

set terminal canvas standalone mousing
set output '/tmp/output.html'

set yrange[0:130]
plot "{0}" using 2:(($3 - $4) * 100 / $3) with lines title '% space use' ls 1, \
""    using 2:(($5 - $6) * 100 / $5) with lines title '% inodes use' ls 2,     \
"{1}" using 2:($4>500?$5:-1) ev 3 with points pt 14 lc rgb "blue" title 'free >500MB', \
"" using 2:($4<=500?$5:-1)  ev 1 with points pt 3 lc rgb "red" title 'free <500MB', \
"" using 2:($4<500?$5+5*$6-30:-1):4 ev 1 with labels center offset 0,0 tc rgb "red" notitle,  \
"" using 2:($4>500?$5-5*$6+10:-1):4 ev 3 with labels center offset 0,0 tc rgb "blue" notitle,  \
#""    using 2:5  lc rgb "black" with impulses title ''
            """.format(data_file.name, max_data_file.name))

            # while True:
            #     try:
            #         print ("'q' + 'enter' to quit")
            #         quit = input()
            #         assert quit == 'q'
            #     except AssertionError:
            #         p.send ("replot")
            #         continue
            #     else:
            #         break
            p.close()
#"" using 2:($6<5?$5 + 5*$6:$5 + 3*$6 - 11):4 with labels offset 0,0.8 title '',  \

# -*- mode: python -*-

from df_recorder import SystemService, PersistenceSQL3, sqlite3, time, logging, os, GnuPlot
from xhtml import Xhtml

logging.basicConfig()
logger = logging.getLogger(os.path.basename(__file__))
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
# logger.setLevel(logging.ERROR)

"""
all functions are bounded to max 24hour (86400 seconds) worth of data
"""
class MonitorFsValueError(Exception):
    pass

class MonitorFs(SystemService):

    """
    get the data
    default 1800 seconds arround the pivot ±30min
    """
    def statvfs_b_get_data (self, mnt_name=None, stamp_pivot=None, stamp_delta=1800):
        dt_format = "%Y-%m-%dT%H:%M:%S%Z"
        step = 1 if stamp_delta <= 3600 else 3
        assert stamp_delta < 43200 # 86400 / 2
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


    def statvfs_flog_db_create (self):
        v = self.db_create()
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                logger.debug("statvfs_flog_db_create: create table if not exists stat_vfs_flog")
                cur.execute("""create table if not exists stat_vfs_flog
                (
                 id integer primary key,
                 path text,
                 ctime integer
                );
                """)
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()
    """
    store/remove the timestamped full path into db
    """
    def statvfs_flog_db_store_ctrl (self, command, fpath):
        self.statvfs_flog_db_create()
        logger.debug("statvfs_flog_db_store_ctrl {} {}".format (command, fpath))
        assert command in ("add", "del")
        assert '%' not in fpath
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                if command == "del":
                    cur.execute("""
                    delete from stat_vfs_flog where path = ?;
                    """, (fpath.strip(),))
                elif command == "add":
                    cur.execute("""
                    update stat_vfs_flog set (path, ctime) = (select ?, strftime('%s')) where path = ?;
                    """, (fpath.strip(), fpath.strip()))
                    cur.execute("""insert into stat_vfs_flog (path, ctime) select ?, strftime('%s')
                    where (select changes() = 0);
                    """, (fpath.strip(),))
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()

    def statvfs_flog_db_store_f_expired (self, cduration = 60):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                cur.execute("""
                select path from stat_vfs_flog where ((SELECT strftime('%s') - ?) > ctime);
                """, (cduration,))
            except Exception as e:
                logger.error (e)
                raise
            else:
                for c in cur:
                    yield [r for r in c]

    """
    storage cleanup
    """
    def statvfs_flog_cleanup (self, cduration=60):
        for f in self.statvfs_flog_db_store_f_expired (cduration):
            path = f[0] if f else 'undef'
            try:
                if os.path.isfile(path):
                    logger.info ("unlink: {}".format(path))
                    os.unlink (path)
                else: logger.warning ("statvfs_flog_cleanup not found: {}".format(path))
            except Exception as e:
                logger.error (e)
                continue
            else:
                self.statvfs_flog_db_store_ctrl ("del", path)

    def gnuplot_script (self, mnt_name, data_file_name, max_data_file_name, size_trigger=500):
        s = """
        set xtics rotate
        set title 'disk usage for {0}' noenhanced
        set xdata time
        set timefmt "%s"
        #set format x "%Y-%m-%dT%H:%M:%SUTC"
        set format x "%H:%M:%S"
        set datafile separator ","
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
        set key top right Left box ls 11 height 1 width 0 maxrows 2

        set encoding utf8

        set yrange[0:130]
        plot "{1}" using 2:(($3 - $4) * 100 / $3) with lines title ' % space use' ls 1,                 \
        ""    using 2:(($5 - $6) * 100 / $5) with lines title ' % inodes use' ls 2,                     \
        "{2}" using 2:($4>{3}?$5:-1) ev 3 with points pt 14 lc rgb "blue" title ' free >{3}MB',         \
        "" using 2:($4<={3}?$5:-1)  ev 1 with points pt 3 lc rgb "red" title ' free <{3}MB',            \
        "" using 2:($4<={3}?$5+5*$6-30:-1):4 ev 1 with labels center offset 0,0 tc rgb "red" notitle,   \
        "" using 2:($4>{3}?$5-5*$6+10:-1):4 ev 3 with labels center offset 0,0 tc rgb "blue" notitle,   \
        #""    using 2:5  lc rgb "black" with impulses title ''
""".format(mnt_name, data_file_name, max_data_file_name, size_trigger)
        return s

"""
 js_function_name: if not set use standalone mode
"""
def statvfs_plot2file (mnt_name, stamp_pivot=None, stamp_delta=1800, output=None, js_function_name=None):

    ssp = MonitorFs()

    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w+', encoding='utf-8') as data_file:
        with NamedTemporaryFile(mode='w+', encoding='utf-8') as max_data_file:
            [print (str(i)[1:-1], file=max_data_file) for i in ssp.statvfs_get_min_fs(
                name=mnt_name,
                stamp_pivot=stamp_pivot,
                stamp_delta=stamp_delta)]
            max_data_file.flush()

            [print (str(i)[1:-1], file=data_file) for i in ssp.statvfs_b_get_data(
                mnt_name=mnt_name,
                stamp_pivot=stamp_pivot,
                stamp_delta=stamp_delta)]
            data_file.flush()

            if os.stat(data_file.name).st_size == 0:
                raise MonitorFsValueError ('no data')

            p = GnuPlot()
            p.send(["reset session", "set termoption enhanced"])
            if output and js_function_name:
                p.send("set output '{}'".format(output))
                p.send("set terminal canvas name '{}' mousing jsdir '/scripts'".format(js_function_name))
            elif output:
                p.send("set output '{}'".format(output))
                p.send("set terminal canvas standalone mousing jsdir '/scripts'")
            else:
                p.send("set terminal canvas standalone mousing")

            p.send(ssp.gnuplot_script (
                mnt_name=mnt_name, data_file_name=data_file.name, max_data_file_name=max_data_file.name))
            p.close()

"""
 url: file name containing the plot canvas
 js_function_name: name set in gnuplot script -> set term canvas name 'MyPlot'
 title: html title
 max_plot: how may toggle_plot button to display
 fs_list list of fs to build the nav bar
"""
def html_document(url, js_function_name="", title="", max_plot=4,
                  url_icon='/icons', url_js='/scripts',
                  fs_list=[]):
    try:
        xhtml = Xhtml(version=5)
        head = xhtml.create_element ("head", Class="")
        xhtml.append(head)
        if title:
            html_title = xhtml.create_element ("title", Class="")
            xhtml.append_text (html_title, title)
            xhtml.append_child(head, html_title)

        style = xhtml.create_element ("style", Class="")
        xhtml.append_text (style, """
.sidenav {
  height: 100%;
  width: 0;
  position: fixed;
  z-index: 1;
  top: 0;
  left: 0;
  background-color: #111;
  overflow-x: hidden;
  transition: 0.5s;
  padding-top: 60px;
}

.sidenav a {
  padding: 8px 8px 8px 0;
  text-decoration: none;
  font-size: 19px;
  color: #818181;
  display: block;
  transition: 0.3s;
}

.sidenav a:hover {
  color: #f1f1f1;
}

.sidenav .closebtn {
  position: absolute;
  top: 0;
  right: 25px;
  font-size: 36px;
  margin-left: 50px;
}

td.mb1 {
  width: auto;
  padding-left: 5px;
  padding-right: 5px;
}

td.mb1-val {
  width: 14em;
}

table.mbleft{
  float: auto;
}

div.help {
  width: min-content;
  padding-right: 1em;
  padding-left: 1em;
  padding-top: 1em;
  padding-bottom: 1em;
  background-color: #EEE;
  display: none;
}
""")
        nav_js = xhtml.create_element ("script", Class="")
        xhtml.append_text (nav_js, """
function openNav() {
  document.getElementById('sidenav01').style.width = '30%';
}

function closeNav() {
  document.getElementById('sidenav01').style.width = '0';
}

function gnuplot_canvas() {
}

function toggle_help() {
  var div = document.getElementById('divhelp');
  if (div.style.display == 'block') {
    div.style.display = 'none';
  } else {
    div.style.display = 'block';
  }
}
""")
        xhtml.append_child (head, nav_js)

        style_ln = xhtml.create_element ("link", Attr=[
            ("type", "text/css"),
            ("href", "{}/gnuplot_mouse.css".format(url_js)),
            ("rel", "stylesheet")
        ])
        xhtml.append_child (head, style_ln)
        xhtml.append_child (head, style)
        # overwrite with inline style

        body = xhtml.create_element ("body", Class="", Attr=[
            ("onload", '{}();'.format(js_function_name))
        ])

        div_side_nav =  xhtml.create_element ("div", Id='sidenav01', Class="sidenav")
        div_side_nav_a1 = xhtml.create_element ("a" , Class="closebtn", Attr=[
            ('href', 'javascript:void(0)'), ('onclick', 'closeNav()')])
        xhtml.append_text (div_side_nav_a1, "×")
        xhtml.append_child (div_side_nav, div_side_nav_a1)

        for fs in fs_list:
            div_side_nav_a2 = xhtml.create_element ("a", Attr=[('href', '/df?m={}'.format(fs))])
            xhtml.append_text (div_side_nav_a2, "↪ {}".format(fs))
            xhtml.append_child (div_side_nav, div_side_nav_a2)

        div_side_nav_span = xhtml.create_element ("span", Attr=[
            ('style',"font-size:30px;cursor:pointer"),
            ('onclick',"openNav()")])
        xhtml.append_text (div_side_nav_span, "☰")
        xhtml.append_child (body, div_side_nav)
        xhtml.append_child (body, div_side_nav_span)

        div =  xhtml.create_element ("div", Class="gnuplot", Attr=[
            ('onclick','{}()'.format(js_function_name)),
            ('oncontextmenu','return false;'),
            ('onmouseup','{}()'.format(js_function_name))
        ])
        xhtml.append_child (body, div)

        div_table =  xhtml.create_element ("table", Class="mbleft")
        xhtml.append_child (div, div_table)
        div_table_tr =  xhtml.create_element ("tr")
        xhtml.append_child (div_table, div_table_tr)

        div_table_td_1 =  xhtml.create_element ("td", Class="mbh")
        xhtml.append_child (div_table_tr, div_table_td_1)
        div_table_td_2 =  xhtml.create_element ("td", Class="mbh")
        xhtml.append_child (div_table_tr, div_table_td_2)
        div_table_td_3 =  xhtml.create_element ("td", Class="mbh")
        xhtml.append_child (div_table_tr, div_table_td_3)


        # mouse box
        mouse_box_table = xhtml.create_element ("table", Class="mousebox")
        mouse_box_table_tr1 = xhtml.create_element ("tr", Class="mousebox")
        xhtml.append_child (mouse_box_table, mouse_box_table_tr1)
        # grid
        mouse_box_td_grid = xhtml.create_element ("td", Class="icon", Attr=[
            ('onclick', 'gnuplot.toggle_grid("{}")'.format(js_function_name))
        ])
        mouse_box_td_grid_img = xhtml.create_element ("img", Class="icon-img", Attr=[
            ('src', '/icons/grid.png'),
            ('alt', '#'),
            ('title', 'toggle grid')
        ])
        xhtml.append_child (mouse_box_td_grid, mouse_box_td_grid_img)
        xhtml.append_child (mouse_box_table_tr1, mouse_box_td_grid)
        # unzoom
        mouse_box_td_unzoom = xhtml.create_element ("td", Class="icon", Attr=[
            ('onclick', 'gnuplot.unzoom("{}")'.format(js_function_name))
        ])
        mouse_box_td_unzoom_img = xhtml.create_element ("img", Class="icon-img", Attr=[
            ('src', '/icons/previouszoom.png'),
            ('alt', 'unzoom'),
            ('title', 'unzoom')
        ])
        xhtml.append_child (mouse_box_td_unzoom, mouse_box_td_unzoom_img)
        xhtml.append_child (mouse_box_table_tr1, mouse_box_td_unzoom)
        # rezoom
        mouse_box_td_rezoom = xhtml.create_element ("td", Class="icon", Attr=[
            ('onclick', 'gnuplot.rezoom("{}")'.format(js_function_name))
        ])
        mouse_box_td_rezoom_img = xhtml.create_element ("img", Class="icon-img", Attr=[
            ('src', '/icons/nextzoom.png'),
            ('alt', 'rezoom'),
            ('title', 'rezoom')
        ])
        xhtml.append_child (mouse_box_td_rezoom, mouse_box_td_rezoom_img)
        xhtml.append_child (mouse_box_table_tr1, mouse_box_td_rezoom)
        # txtzoom
        mouse_box_td_txtzoom = xhtml.create_element ("td", Class="icon", Attr=[
            ('onclick', 'gnuplot.toggle_zoom_text("{}")'.format(js_function_name))
        ])
        mouse_box_td_txtzoom_img = xhtml.create_element ("img", Class="icon-img", Attr=[
            ('src', '/icons/textzoom.png'),
            ('alt', 'zoom text'),
            ('title', 'zoom text with plot')
        ])
        xhtml.append_child (mouse_box_td_txtzoom, mouse_box_td_txtzoom_img)
        xhtml.append_child (mouse_box_table_tr1, mouse_box_td_txtzoom)
        # help
        mouse_box_td_help = xhtml.create_element ("td", Class="icon", Attr=[
            ('onclick', 'toggle_help()')
        ])
        mouse_box_td_help_img = xhtml.create_element ("img", Class="icon-img", Attr=[
            ('src', '/icons/help.png'),
            ('alt', '?'),
            ('title', 'help')
        ])
        xhtml.append_child (mouse_box_td_help, mouse_box_td_help_img)
        xhtml.append_child (mouse_box_table_tr1, mouse_box_td_help)
        # toggle_plot
        mouse_box_table_tr2 = xhtml.create_element ("tr", Class="mousebox")
        xhtml.append_child (mouse_box_table, mouse_box_table_tr2)
        count = 0
        for i in ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨']:
            count += 1
            toggle_plot_td = xhtml.create_element (
                "td", Class="icon",
                Attr=[('onclick', 'gnuplot.toggle_plot("{}_plot_{}")'.format(js_function_name, count))])
            xhtml.append_text (toggle_plot_td, "{}".format(i))
            xhtml.append_child (mouse_box_table_tr2, toggle_plot_td)
            if count == max_plot: break
        # x,y
        xy_table = xhtml.create_element ("table", Class="mousebox", Attr=[('border', '1')])
        xy_table_tr1 = xhtml.create_element ("tr", Class="mousebox")
        xhtml.append_child (xy_table, xy_table_tr1)
        for xy in ['x', 'y']:
            xy_table_tr2 = xhtml.create_element ("tr", Class="mousebox")
            xy_table_td1 = xhtml.create_element ("td", Class="mb1")
            xhtml.append_text (xy_table_td1, xy)
            xy_table_td2 = xhtml.create_element ("td", Class="mb1 mb1-val",
                                                 Id="{}_{}".format(js_function_name, xy))
            xhtml.append_child (xy_table_tr2, xy_table_td1)
            xhtml.append_child (xy_table_tr2, xy_table_td2)
            xhtml.append_child (xy_table_tr1, xy_table_tr2)
        # canvas
        canvas = xhtml.create_element ("canvas", Id="{}".format(js_function_name), Attr=[
            ('width','600'), ('height','400')
        ])
        xhtml.append_text (canvas, "Sorry, your browser seems not to support the HTML 5 canvas element")
        # help
        help_div = xhtml.create_element ("div", Id="divhelp", Class="help")
        help_div_pre = xhtml.create_element ("pre", Class="help")
        xhtml.append_text (help_div_pre, """
Help

* Mouse Menu:
  - Zoom using right (Firefox, Konqueror) or center (Opera, Safari) mouse button
  - Mark point using left mouse button
  - ① ... ⑨ toggles plot on/off
  - # toggles grid on/off

* URL parameters:
  - m: mount point
  - pivot: number of seconds elapsed since the Epoch, default now - delta
  - delta: +/- number of seconds around the pivot, default 1800, max 43199
""")
        xhtml.append_child (help_div, help_div_pre)
        xhtml.append_child (body, help_div)
        # js
        for js in [# 'canvasmath.js',
                   'canvastext.js',
                   'gnuplot_common.js',
                   'gnuplot_dashedlines.js',
                   'gnuplot_mouse.js']:
            script = xhtml.create_element ("script", Attr=[
                ('src', '{}/{}'.format(url_js, js))
            ])
            xhtml.append_child (body, script)
        # plot js
        pscript = xhtml.create_element ("script", Attr=[('src', '{}/{}'.format('/plots', url))])
        xhtml.append_child (body, pscript)

        xhtml.append_child (div_table_td_1, mouse_box_table)
        xhtml.append_child (div_table_td_2, xy_table)
        xhtml.append_child (div_table_td_3, canvas)
        xhtml.append (body)
    except:
        raise
    else:
        return xhtml.to_string()
    finally:
        xhtml.unlink()

class CltException(Exception):
    pass
class SrvException(Exception):
    pass

def application(environ, start_response):
    dt_format = "%Y-%m-%dT%H:%M:%S%Z"
    standalone=False
    try:
        from mod_wsgi import version
        # Put code here which should only run when mod_wsgi is being used.
        from urllib import parse
        query = environ.get('QUERY_STRING', '')
        params = dict(parse.parse_qsl(query))
        logger.debug ("params: {}".format(params))

        m = params['m'] if 'm' in params else '/'
        pivot = params['pivot'] if 'pivot' in params else None
        delta = params['delta'] if 'delta' in params else None
        standalone = True if 'standalone' in params else False

        status_ok = '200 OK'
        status_ko_clt = '400 Bad Request'
        status_ko_srv = '501 Not Implemented'
        js_name = "df_plot"
        status = None
        out_dir = '/tmp' if standalone else '/var/www/gnuplot/plots'
        # a cache cleanup procedure is not implemented yet
        # you may need to use systemd: systemd-tmpfiles-clean.timer and /etc/tmpfiles.d
        try:
            ssp = MonitorFs()

            delta = int(delta) if delta else 1800
            pivot = pivot if pivot else time.mktime(time.gmtime()) - delta
            try:
                pivot = int(float(pivot))
            except ValueError:
                pivot = time.mktime(time.strptime(pivot, dt_format))

            p = int(pivot)|int('111', 2)
            out_ext = "html" if standalone else "js"
            fhtml=os.path.join(out_dir,
                               "{}-{}-{}.{}".format(m.replace('/','_'), bin(p), int(delta), out_ext))
            if os.path.isfile(fhtml):
                logger.info("use cache: {}".format(fhtml))
                ssp.statvfs_flog_db_store_ctrl("add", fhtml)
            else:
                logger.info("gen cache: {}".format(fhtml))
                statvfs_plot2file (
                    m, stamp_pivot=pivot, stamp_delta=delta, output=fhtml, js_function_name=js_name
                )
                ssp.statvfs_flog_db_store_ctrl("add", fhtml)
        except MonitorFsValueError as e:
            logger.error(e)
            status = status_ko_clt
            output = b'no data'
            response_headers = [('Content-type', 'text/plain'),
                                ('Content-Length', str(len(output)))]
            start_response(status, response_headers)
            return [output]
        except Exception as e:
            logger.error(e)
            status = status_ko_srv
            output = b'not implemented'
            response_headers = [('Content-type', 'text/plain'),
                                ('Content-Length', str(len(output)))]
            start_response(status, response_headers)
            return [output]
        else:
            status = status_ok
            if standalone:
                response_headers = [('Content-type', 'text/html')]

                filelike = open(file=fhtml, mode='rb')
                block_size = 4096

                start_response(status, response_headers)

                if 'wsgi.file_wrapper' in environ:
                    return environ['wsgi.file_wrapper'](filelike, block_size)
                else:
                    return iter(lambda: filelike.read(block_size), '')
            else:
                fs_list = [i for i in ssp.statvfs_list_mnt()]
                output = html_document(
                    url=os.path.basename(fhtml), js_function_name=js_name, title='df plot', fs_list=fs_list)
                response_headers = [('Content-type', 'text/html'),
                                    ('Content-Length', str(len(output)))]
                start_response(status, response_headers)
                return [output]

        finally:
            ssp.statvfs_flog_cleanup()
    except Exception as e:
        logger.error(e)
    else:
        pass
    finally:
        pass

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

    statvfs_plot2file (mnt_name, stamp_pivot=stamp_pivot, stamp_delta=stamp_delta)

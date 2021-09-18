# -*- mode: python -*-

from json import dumps
from df_recorder import SystemService, PersistenceSQL3, sqlite3, time, logging, os
from xhtml import Xhtml

logging.basicConfig()
logger = logging.getLogger(os.path.basename(__file__))
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
# logger.setLevel(logging.ERROR)

class MonitorFsValueError(Exception):
    pass

class MonitorFs(SystemService):

    def __init__(self, dbname=None):
        if dbname:
            self.database = _default_db_path(name=dbname)
        else:
            super().__init__()
            self.db_create()

    def statvfs_notice_db_create (self):
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            try:
                cur = db3.cursor()
                logger.debug("statvfs_notice_db_create: create table if not exists stat_vfs_limit")
                cur.execute("""create table if not exists stat_vfs_limit
                (
                 id integer primary key,
                 path text not null,
                 limit_mb integer,
                 limit_pc integer,
                UNIQUE (path),
                CHECK(limit_mb >= 0),
                CHECK(limit_pc >=0 and limit_pc <= 100)
                );
                """)
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()

    """
    limits take the form [{'path': None, 'mb': None, 'pcent': None}, ...]
    and represent free space to keep
    default apply for fs detected but not set
    """
    def statvfs_notice_add_limit (self, limits=[], limit_default_mb=500, limit_default_pcent= 5):
        self.statvfs_notice_db_create()
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            if logger.level == logging.DEBUG:
                db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                for l in limits:
                    pa = l['path'] if 'path' in l else None
                    mb = l['mb'] if 'mb' in l else None
                    pc = l['pcent'] if 'pcent' in l else None
                    if pa is None: continue
                    pa = pa[:-1] if (pa[-1] == '/' and pa != '/') else pa
                    cur.execute ("select id from stat_vfs_limit where path = ?;",(pa,))
                    r = cur.fetchone()
                    if not r:
                        cur.execute ("""
                        insert into stat_vfs_limit (path, limit_mb, limit_pc) values (?, ?, ?);
                        """, (pa, mb, pc))
                    elif mb and pc:
                        cur.execute ("""
                        update stat_vfs_limit set (path, limit_mb, limit_pc) = (?, ?, ?) where id = ?;
                        """, (pa, mb, pc, r[0]))
                    elif mb:
                        cur.execute ("""
                        update stat_vfs_limit set (path, limit_mb) = (?, ?) where id = ?;
                        """, (pa, mb, r[0]))
                    elif pc:
                        cur.execute ("""
                        update stat_vfs_limit set (path, limit_pc) = (?, ?) where id = ?;
                        """, (pa, pc, r[0]))
                    else:
                        cur.execute ("""
                        delete from stat_vfs_limit where id = ?;
                        """, (r[0],))
                for m in self.statvfs_list_mnt():
                    cur.execute ("""
                    insert or ignore into stat_vfs_limit (path, limit_mb, limit_pc) values (?, ?, ?);
                    """, (m, limit_default_mb, limit_default_pcent))
            except Exception as e:
                logger.error (e)
                raise
            else:
                db3.commit()

    def statvfs_notice_get_limit(self, name):
        result = {}
        name = name[:-1] if (name[-1] == '/' and name != '/') else name
        with PersistenceSQL3(database=self.database) as db3:
            db3.row_factory = sqlite3.Row
            if logger.level == logging.DEBUG:
                db3.set_trace_callback(logger.debug)
            try:
                cur = db3.cursor()
                cur.execute ("""
                select path, limit_mb, limit_pc from stat_vfs_limit where path = ?;
                """,(name,))
                r = cur.fetchone()
                if r:
                    result['path'] = r[0]
                    result['mb'] = r[1]
                    result['pcent'] = r[2]
                    return result
                else: raise MonitorFsValueError ('{} not found'.format(name))
            except Exception as e:
                logger.error(e)
                pass

    def statvfs_notice_check (self, past_seconds=1800):
        assert past_seconds > 0
        result = []
        for m in self.statvfs_list_mnt():
            l = self.statvfs_notice_get_limit(m)
            for n in self.statvfs_get_min_fs(m, 0 - past_seconds):
                id, stamp, fs_total, mb_free, pc_use, row_num = n
                if mb_free > l['mb'] or 100 - pc_use > l['pcent']:
                    logger.debug ("{} > {}: {}".format(mb_free, l['mb'], mb_free > l['mb']))
                    logger.debug ("{} > {}: {}".format(100 - pc_use, l['pcent'], 100 - pc_use > l['pcent']))
                    logger.debug ("""fs: {}, id: {}, stamp: {}, fs_total: {}, raw free: {},
                    pcent use: {}, row num: {}""".format(m, id, stamp, fs_total, mb_free, pc_use, row_num))
                else:
                    result.append([m, stamp, past_seconds/2, mb_free])
                    break
        return result

def application(environ, start_response):
    try:
        from mod_wsgi import version
        # Put code here which should only run when mod_wsgi is being used.
        from urllib import parse
        query = environ.get('QUERY_STRING', '')
        params = dict(parse.parse_qsl(query))
        logger.debug ("params: {}".format(params))

        past = params['past'] if 'past' in params else 1800

        status_ok = '200 OK'
        status_ko_clt = '400 Bad Request'
        status_ko_srv = '501 Not Implemented'
        status = None
        m_fs = MonitorFs()
        m_fs.statvfs_notice_add_limit ()
        # add default_limit
        result = m_fs.statvfs_notice_check(past)
    except MonitorFsValueError as e:
        logger.error(e)
        status = status_ko_clt
        r = {"df": {"error": True, "status": status}}
        output = dumps(r).encode("utf-8")
        response_headers = [('Content-type', 'text/json'),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
    except Exception as e:
        logger.error(e)
        status = status_ko_srv
        r = {"df": {"error": True, "status": status}}
        output = dumps(r).encode("utf-8")
        response_headers = [('Content-type', 'text/json'),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
    else:
        status = status_ok
        r = {"df": {"error": False, "status": status, "result": result}}
        output = dumps(r).encode("utf-8")
        response_headers = [('Content-type', 'text/html'),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
    finally:
        pass

if __name__ == "__main__":
    pass
    # m_fs = MonitorFs()
    # m_fs.statvfs_notice_add_limit(limits=[{'path': '/', 'mb': 100, 'pcent': 9}])
    # m_fs.statvfs_notice_add_limit(limits=[{'path': '/', 'mb': 100, 'pcent': None}])
    # m_fs.statvfs_notice_add_limit(limits=[{'path': '/', 'mb': None, 'pcent': 9}])
    # m_fs.statvfs_notice_add_limit(limits=[{'path': '/', 'mb': None, 'pcent': None}])
    # m_fs.statvfs_notice_check()

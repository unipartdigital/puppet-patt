#!/usr/bin/python3
# -*- mode: python -*-

"""
The MIT License (MIT)

Copyright (c) 2015 Compose, Zalando SE

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
patroni user role management extract from patroni/bootstrap.py
could be useful to set or update patroni roles while skipping the bootstrap
in example: switch from MD5 auth to SCRAM, new patroni.yaml
"""

import argparse
import yaml
import os
import sys
import psycopg2
import logging

logger = logging.getLogger('patroni_passwd')


"""
connect using the default local socket and
return True if postgres is readwrite, False if not
return None in case of error
"""
def is_postgres_read_write(cur):
    try:
        cur.execute("SHOW transaction_read_only;")
        result = cur.fetchone()
    except Exception as e:
        logger.warning (e)
        pass
    else:
        if type (result) == tuple:
            return result[0] == 'off'

"""
extract relevant authentications key/val from patroni.yaml
"""
def passwd_dict(patroni_config):
    yaml_auth={}
    try:
        if os.path.isfile(patroni_config):
            with open(patroni_config, 'r') as p:
                try:
                    result=yaml.safe_load(p)
                    logger.debug("yaml.safe_load({})".format(p))
                except Exception as e:
                    logger.error (e)
                    raise
                else:
                    assert result is not None, "{}: no yaml data".format (p.name)
                    if 'postgresql' in result and 'authentication' in result['postgresql']:
                        yaml_auth=result['postgresql']['authentication']
                    else:
                        logger.warning ("dict keys ['postgresql']['authentication'] not found")
    except Exception as e:
        logger.error (e)
    finally:
        return yaml_auth

def create_or_update_role(cur, name, password, options):
    options = list(map(str.upper, options))
    if 'NOLOGIN' not in options and 'LOGIN' not in options:
        options.append('LOGIN')
    if password:
        options.append('PASSWORD')
        options.append("'{}'".format (password))
    sql = """DO $$
BEGIN
    SET local synchronous_commit = 'local';
    PERFORM * FROM pg_authid WHERE rolname = %s;
    IF FOUND THEN
        ALTER ROLE "{0}" WITH {1};
    ELSE
        CREATE ROLE "{0}" WITH {1};
    END IF;
END;$$""".format(name, ' '.join(options))
    cur.execute(sql, [name])
    return cur

def sql_header(cur):
    cur.execute("SET log_statement TO none;")
    cur.execute("SET log_min_duration_statement TO -1;")
    cur.execute("SET log_min_error_statement TO 'log';")
    return cur

def sql_footer (cur):
    cur.execute("RESET log_min_error_statement;")
    cur.execute("RESET log_min_duration_statement;")
    cur.execute("RESET log_statement;")
    return cur

def rewind_sql (cur, rewind_username):
    for f in ('pg_ls_dir(text, boolean, boolean)', 'pg_stat_file(text, boolean)',
              'pg_read_binary_file(text)', 'pg_read_binary_file(text, bigint, bigint, boolean)'):
        sql = """DO $$
BEGIN
    SET local synchronous_commit = 'local';
    GRANT EXECUTE ON function pg_catalog.{0} TO "{1}";
END;$$""".format(f, rewind_username)
        cur.execute (sql)
        logger.debug (sql)
    return cur

def alter_role (patroni_config, users=['superuser', 'replication', 'rewind'], dbname="postgres"):
    conn = psycopg2.connect(dbname=dbname)
    try:
        cur = conn.cursor()
        if not is_postgres_read_write(cur):
            logger.warning ("not a read-write db")
            return
        dict_auth = passwd_dict(patroni_config)
        assert not dict_auth == {}, "empty dict"
        sql_header(cur)
        for u in users:
            logger.debug ("{}:\t username: {}\t password: ****".format (u, dict_auth[u]['username']))
            assert 'username' in dict_auth[u], "no username found for {}".format (dict_auth[u])
            assert 'password' in dict_auth[u], "no password found for {}".format (dict_auth[u])
            if u == 'superuser':
                logger.info ("create_or_update_role {} \t {} \t {}".format (
                dict_auth[u]['username'], '****', ['SUPERUSER']))
                create_or_update_role(
                    cur, dict_auth[u]['username'], dict_auth[u]['password'], ['SUPERUSER'])
            if u == 'replication':
                logger.info ("create_or_update_role {} \t {} \t {}".format (
                    dict_auth[u]['username'], '****', ['REPLICATION']))
                create_or_update_role(
                    cur, dict_auth[u]['username'], dict_auth[u]['password'], ['REPLICATION'])
            if u == 'rewind':
                logger.info ("create_or_update_role {} \t {} \t {}".format (
                    dict_auth[u]['username'], '****', []))
                create_or_update_role(
                    cur, dict_auth[u]['username'], dict_auth[u]['password'], [])
                logger.info ("grant exec to {}".format (dict_auth[u]['username']))
                rewind_sql (cur, dict_auth[u]['username'])
        sql_footer (cur)
    except Exception as e:
        logger.error (e)
        raise
    else:
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config_file', help='patroni config file', default="~/patroni.yaml")
    parser.add_argument('-v', '--verbose', action="store_const", dest="loglevel", const=logging.DEBUG,
                        default=logging.INFO)
    args = parser.parse_args()

    log_handlers=[logging.StreamHandler()]
    logging.basicConfig(level=args.loglevel,
                        format='%(levelname)s: %(asctime)s:%(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S',
                        handlers=log_handlers)

    alter_role(os.path.expanduser(args.config_file))

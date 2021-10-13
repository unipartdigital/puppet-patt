# -*- mode: python -*-

from patt_monitoring import EtcdService, PatroniService, DiskFreeService
from xhtml import Xhtml

OK_TEXT="all good"
KO_TEXT="ERROR"

"""
 cluster health
 return http status code 200 with minimal contain if all OK
 return http status code 202 with detailed contain if not OK
"""
def application(environ, start_response):
    status_ok = '200 OK'
    status_ko = '202 Accepted'

    xhtml = Xhtml()
    head = xhtml.create_element ("head", Class="")
    xhtml.append (head)

    body = xhtml.create_element ("body", Class="")
    xhtml.append (body)

    service_status=[]

    etcd=EtcdService()
    etcd_healthy=etcd.is_healthy()
    service_status.append(etcd_healthy)

    patroni=PatroniService()
    patroni.get_info()
    patroni_health=[
        ("have master", patroni.has_master()),
        ("have replica", patroni.has_replica()),
        ("match config",patroni.match_config()),
        ("replayed delta", patroni.replica_received_replayed_delta_ok()),
        ("timeline match", patroni.timeline_match()),
        ("replication health", patroni.replication_health())]

    patroni_healthy=all([n[1] == True for n in patroni_health])
    service_status.append(patroni_healthy)

    df = DiskFreeService()
    df_healthy=df.is_healthy()
    service_status.append(df_healthy)

    status = status_ok if all([x == True for x in service_status]) else status_ko

    h3_text_status = xhtml.create_element ("h3", Class="h3")

    if status == status_ok:
        xhtml.append_text (h3_text_status, OK_TEXT)
    else:
        xhtml.append_text (h3_text_status, KO_TEXT)
        ul_text_status = xhtml.create_element ("ul", Class="")
        li_text_status = xhtml.create_element ("li", Class="")
        #
        a_text_status = xhtml.create_element ("a", Class="")
        a_text_status.setAttribute("href", "{}".format("/health"))
        xhtml.append_text (a_text_status, "See also: /health")
        #
        xhtml.append_child (li_text_status, a_text_status)
        xhtml.append_child (ul_text_status, li_text_status)
        #
        xhtml.append_child (h3_text_status, li_text_status)


    xhtml.append_child (body, h3_text_status)

    output = xhtml.to_string()
    response_headers = [('Content-type', 'text/html'),
                        ('Content-Length', str(len(output)))]
    status = status_ok if all([x == True for x in service_status]) else status_ko
    try:
        from mod_wsgi import version
        # Put code here which should only run when mod_wsgi is being used.
        start_response(status, response_headers)
    except:
        pass
    return [output]

if __name__ == "__main__":
    print (application(None, None)[0].decode('utf-8'))

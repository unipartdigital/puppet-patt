# -*- mode: python -*-

from patt_monitoring import EtcdService, PatroniService
from xhtml import Xhtml

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
    xhtml.append(head)

    style = xhtml.create_element ("style", Class="")
    xhtml.append_text (style,
"""
div.table{display:table; padding: 10px; border: 1px ;   float:left; width: 50%;}
div.etcd_ok{display:table-cell; empty-cells:hide; padding: 10px; border: 1px solid green;}
div.etcd_ko{display:table-cell; empty-cells:hide; padding: 10px; border: 1px solid red;}
div.patroni_ok{display:table-cell; empty-cells:hide; padding: 10px; border: 1px solid green;}
div.patroni_ko{display:table-cell; empty-cells:hide; padding: 10px; border: 1px solid red;}
div.patroni_dump{display:table-cell; empty-cells:hide; padding: 10px; border: 1px solid gray; font-family: courier, monospace; white-space: pre-wrap;}
ul.etcd{list-style: none;}
ul.patroni{list-style: none;}
li.etcd_ok::before{content: '\\2600'; display: inline-block; width: 1em; margin-left: -1em; color: green;}
li.etcd_ko::before{content: '\\2020'; display: inline-block; width: 1em; margin-left: -1em; color: red;}
li.patroni_ok::before{content: '\\2600'; display: inline-block; width: 1em; margin-left: -1em; color: green;}
li.patroni_ko::before{content: '\\2020'; display: inline-block; width: 1em; margin-left: -1em; color: red;}
""")
    xhtml.append_child (head, style)

    body = xhtml.create_element ("body", Class="")
    xhtml.append (body)

    div_table = xhtml.create_element ("div", Class="div_table")
    xhtml.append_child (body, div_table)

    service_status=[]

    etcd=EtcdService()
    etcd_healthy=etcd.is_healthy()
    service_status.append(etcd_healthy)
    etcd_div_class="etcd_ok" if etcd_healthy else "etcd_ko"
    div_etcd = xhtml.create_element ("div", Class=etcd_div_class)
    h3_etcd = xhtml.create_element ("h3", Class="h3_etcd")
    xhtml.append_text (h3_etcd, "Etcd")
    xhtml.append_child (div_etcd, h3_etcd)

    etcd_cluster_health=etcd.cluster_health()
    ul_etcd = xhtml.create_element ("ul", Class="etcd")
    for e in etcd_cluster_health:
        class_li_etcd="etcd_ok "if e[1] else "etcd_ko"
        li_etcd = xhtml.create_element ("li", Class=class_li_etcd)
        hrr="[OK]" if e[1] else "[ER]"
        xhtml.append_text (li_etcd, "{} {}".format(hrr, e[0]))
        xhtml.append_child (ul_etcd, li_etcd)
    xhtml.append_child (div_etcd, ul_etcd)
    xhtml.append_child (div_table, div_etcd)
    #xhtml.append (div_etcd)

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
    patroni_div_class="patroni_ok" if patroni_healthy else "patroni_ko"
    div_patroni = xhtml.create_element ("div", Class=patroni_div_class)
    h3_patroni = xhtml.create_element ("h3", Class="h3_patroni")
    xhtml.append_text (h3_patroni, "Patroni")
    xhtml.append_child (div_patroni, h3_patroni)

    ul_patroni = xhtml.create_element ("ul", Class="patroni")
    for p in patroni_health:
        class_li_patroni="patroni_ok" if p[1] else "patroni_ko"
        li_patroni = xhtml.create_element ("li", Class=class_li_patroni)
        hrr="[OK]" if p[1] else "[ER]"
        xhtml.append_text (li_patroni, "{} {}".format(hrr, p[0]))
        xhtml.append_child (ul_patroni, li_patroni)
    xhtml.append_child (div_patroni, ul_patroni)
    #xhtml.append (div_patroni)
    xhtml.append_child (div_table, div_patroni)

    div_patroni_dump = xhtml.create_element ("div", Class="patroni_dump")
    h3_patroni_dump = xhtml.create_element ("h3", Class="h3_patroni_dump")
    xhtml.append_text (h3_patroni_dump, "Patroni Dump")
    xhtml.append_child (div_patroni_dump, h3_patroni_dump)

    pre_patroni = xhtml.create_element ("pre", Class="patroni_dump")
    code_patroni = xhtml.create_element ("code", Class="patroni_dump")
    xhtml.append_text (code_patroni, "\n{}".format(patroni.dump()))
    xhtml.append_child (pre_patroni, code_patroni)
    xhtml.append_child (div_patroni_dump, pre_patroni)
    # xhtml.append (div_patroni_dump)
    xhtml.append_child (div_patroni, div_patroni_dump)

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

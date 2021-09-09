from xml.dom.minidom import getDOMImplementation, Document
from sys import stdout

class Xml(object):
    pass

class Xhtml(Xml):

    def __init__(self, version=4):
        if version < 5:
            self.dom = getDOMImplementation().createDocument(
                "http://www.w3.org/1999/xhtml", "html",
                getDOMImplementation().createDocumentType(
                    "html",
                    "-//W3C//DTD HTML 4.01//EN",
                    "http://www.w3.org/TR/html4/strict.dtd"))
        else:
            self.dom = getDOMImplementation().createDocument(
                "http://www.w3.org/1999/xhtml", "html",
                getDOMImplementation().createDocumentType(
                    "html"))

        self.root = self.dom.documentElement
        self.id_count = 0

    def append (self, child):
        self.root.appendChild(child)

    def print (self, file=stdout, encoding='utf-8'):
        self.dom.writexml(file, addindent='   ', newl='\n', encoding=encoding)

    def to_string(self, encoding='utf-8'):
        return self.dom.toprettyxml(indent='   ', newl="\n", encoding=encoding)

    """
    Attr: [(attr1, val1), (attr2, val2)]
    """
    def create_element(self, Name, Id=None, Class=None, Attr=[()]):
        tmp = self.dom.createElement(Name)
        if Id:
            tmp.setAttribute ("id", Id)
        else:
            self.id_count += 1
            tmp.setAttribute ("id", "{}".format(self.id_count))
        if Class:
            tmp.setAttribute ("class", Class)
        else:
            tmp.setAttribute ("class", Name)
        for a in Attr:
            if a: tmp.setAttribute (a[0], a=[1])
        return tmp

    def create_text_node (self, text):
        return self.dom.createTextNode(text)

    def append_child (self, parent, child):
        parent.appendChild(child)

    def append_text (self, node, text):
        self.append_child (node, self.create_text_node (text))

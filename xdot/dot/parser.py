# Copyright 2008-2022 Jose Fonseca
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys

from .lexer import ParseError, DotLexer


EOF = -1
SKIP = -2

ID = 0
STR_ID = 1
HTML_ID = 2
EDGE_OP = 3

LSQUARE = 4
RSQUARE = 5
LCURLY = 6
RCURLY = 7
COMMA = 8
COLON = 9
SEMI = 10
EQUAL = 11
PLUS = 12

STRICT = 13
GRAPH = 14
DIGRAPH = 15
NODE = 16
EDGE = 17
SUBGRAPH = 18


def __getattr__(name: str):
    if name == "XDotParser":
        from ..ui._xdotparser import XDotParser
        return XDotParser
    return AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Parser:

    def __init__(self, lexer):
        self.lexer = lexer
        self.lookahead = next(self.lexer)

    def match(self, type):
        if self.lookahead.type != type:
            raise ParseError(
                msg='unexpected token {}'.format(self.lookahead.text),
                filename=self.lexer.filename,
                line=self.lookahead.line,
                col=self.lookahead.col)

    def skip(self, type):
        while self.lookahead.type != type:
            if self.lookahead.type == EOF:
                raise ParseError(
                    msg='unexpected end of file',
                    filename=self.lexer.filename,
                    line=self.lookahead.line,
                    col=self.lookahead.col)
            self.consume()

    def consume(self):
        token = self.lookahead
        self.lookahead = next(self.lexer)
        return token


class DotParser(Parser):

    def parse(self):
        self.parse_graph()
        if self.lookahead.type != EOF:
            # Multiple graphs beyond the first are ignored
            # https://github.com/jrfonseca/xdot.py/issues/112
            sys.stderr.write('warning: {}:{}:{}: ignoring extra token {}\n'.format(
                self.lexer.filename,
                self.lookahead.line,
                self.lookahead.col,
                self.lookahead.text
            ))

    def parse_graph(self):
        if self.lookahead.type == STRICT:
            self.consume()
        self.skip(LCURLY)
        self.consume()
        while self.lookahead.type != RCURLY:
            self.parse_stmt()
        self.consume()

    def parse_subgraph(self):
        id = None
        if self.lookahead.type == SUBGRAPH:
            self.consume()
            if self.lookahead.type == ID:
                id = self.lookahead.text
                self.consume()
                # A subgraph is also a node.
                self.handle_node(id, {})
        if self.lookahead.type == LCURLY:
            self.consume()
            while self.lookahead.type != RCURLY:
                self.parse_stmt()
            self.consume()
        return id

    def parse_stmt(self):
        if self.lookahead.type == GRAPH:
            self.consume()
            attrs = self.parse_attrs()
            self.handle_graph(attrs)
        elif self.lookahead.type == NODE:
            self.consume()
            self.parse_attrs()
        elif self.lookahead.type == EDGE:
            self.consume()
            self.parse_attrs()
        elif self.lookahead.type in (SUBGRAPH, LCURLY):
            self.parse_subgraph()
        else:
            id = self.parse_node_id()
            if self.lookahead.type == EDGE_OP:
                self.consume()
                node_ids = [id, self.parse_node_id()]
                while self.lookahead.type == EDGE_OP:
                    self.consume()
                    node_ids.append(self.parse_node_id())
                attrs = self.parse_attrs()
                for i in range(0, len(node_ids) - 1):
                    self.handle_edge(node_ids[i], node_ids[i + 1], attrs)
            elif self.lookahead.type == EQUAL:
                self.consume()
                self.parse_id()
            else:
                attrs = self.parse_attrs()
                self.handle_node(id, attrs)
        if self.lookahead.type == SEMI:
            self.consume()

    def parse_attrs(self):
        attrs = {}
        while self.lookahead.type == LSQUARE:
            self.consume()
            while self.lookahead.type != RSQUARE:
                name, value = self.parse_attr()
                name = name.decode('utf-8')
                attrs[name] = value
                if self.lookahead.type == COMMA:
                    self.consume()
            self.consume()
        return attrs

    def parse_attr(self):
        name = self.parse_id()
        if self.lookahead.type == EQUAL:
            self.consume()
            value = self.parse_id()
        else:
            value = b'true'
        return name, value

    def parse_node_id(self):
        node_id = self.parse_id()
        if self.lookahead.type == COLON:
            self.consume()
            port = self.parse_id()
            if self.lookahead.type == COLON:
                self.consume()
                compass_pt = self.parse_id()
            else:
                compass_pt = None
        else:
            port = None
            compass_pt = None
            # XXX: we don't really care about port and compass point
            # values when parsing xdot
        return node_id

    def parse_id(self):
        self.match(ID)
        id = self.lookahead.text
        self.consume()
        return id

    def handle_graph(self, attrs):
        pass

    def handle_node(self, id, attrs):
        pass

    def handle_edge(self, src_id, dst_id, attrs):
        pass


# Copyright 2008-2015 Jose Fonseca
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
import colorsys
import sys

from .lexer import ParseError, DotLexer

from ..ui.colors import lookup_color
from ..ui.pen import Pen
from ..ui import elements


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


class XDotAttrParser:
    """Parser for xdot drawing attributes.
    See also:
    - http://www.graphviz.org/doc/info/output.html#d:xdot
    """

    def __init__(self, parser, buf):
        self.parser = parser
        self.buf = buf
        self.pos = 0

        self.pen = Pen()
        self.shapes = []

    def __bool__(self):
        return self.pos < len(self.buf)

    def read_code(self):
        pos = self.buf.find(b" ", self.pos)
        res = self.buf[self.pos:pos]
        self.pos = pos + 1
        self.skip_space()
        res = res.decode('utf-8')
        return res

    def skip_space(self):
        while self.pos < len(self.buf) and self.buf[self.pos:self.pos+1].isspace():
            self.pos += 1

    def read_int(self):
        return int(self.read_code())

    def read_float(self):
        return float(self.read_code())

    def read_point(self):
        x = self.read_float()
        y = self.read_float()
        return self.transform(x, y)

    def read_text(self):
        num = self.read_int()
        pos = self.buf.find(b"-", self.pos) + 1
        self.pos = pos + num
        res = self.buf[pos:self.pos]
        self.skip_space()
        res = res.decode('utf-8')
        return res

    def read_polygon(self):
        n = self.read_int()
        p = []
        for i in range(n):
            x, y = self.read_point()
            p.append((x, y))
        return p

    def read_color(self):
        # See http://www.graphviz.org/doc/info/attrs.html#k:color
        c = self.read_text()
        c1 = c[:1]
        if c1 == '#':
            hex2float = lambda h: float(int(h, 16)/255.0)
            r = hex2float(c[1:3])
            g = hex2float(c[3:5])
            b = hex2float(c[5:7])
            try:
                a = hex2float(c[7:9])
            except (IndexError, ValueError):
                a = 1.0
            return r, g, b, a
        elif c1.isdigit() or c1 == ".":
            # "H,S,V" or "H S V" or "H, S, V" or any other variation
            h, s, v = map(float, c.replace(",", " ").split())
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            a = 1.0
            return r, g, b, a
        elif c1 == "[" or c1 == "(":
            sys.stderr.write('warning: color gradients not supported yet\n')
            return None
        else:
            return lookup_color(c)

    def parse(self):
        s = self

        while s:
            op = s.read_code()
            if op == "c":
                color = s.read_color()
                if color is not None:
                    self.handle_color(color, filled=False)
            elif op == "C":
                color = s.read_color()
                if color is not None:
                    self.handle_color(color, filled=True)
            elif op == "S":
                # http://www.graphviz.org/doc/info/attrs.html#k:style
                style = s.read_text()
                if style.startswith("setlinewidth("):
                    lw = style.split("(")[1].split(")")[0]
                    lw = float(lw)
                    self.handle_linewidth(lw)
                elif style in ("solid", "dashed", "dotted"):
                    self.handle_linestyle(style)
            elif op == "F":
                size = s.read_float()
                name = s.read_text()
                self.handle_font(size, name)
            elif op == "T":
                x, y = s.read_point()
                j = s.read_int()
                w = s.read_float()
                t = s.read_text()
                self.handle_text(x, y, j, w, t)
            elif op == "t":
                f = s.read_int()
                self.handle_font_characteristics(f)
            elif op == "E":
                x0, y0 = s.read_point()
                w = s.read_float()
                h = s.read_float()
                self.handle_ellipse(x0, y0, w, h, filled=True)
            elif op == "e":
                x0, y0 = s.read_point()
                w = s.read_float()
                h = s.read_float()
                self.handle_ellipse(x0, y0, w, h, filled=False)
            elif op == "L":
                points = self.read_polygon()
                self.handle_line(points)
            elif op == "B":
                points = self.read_polygon()
                self.handle_bezier(points, filled=False)
            elif op == "b":
                points = self.read_polygon()
                self.handle_bezier(points, filled=True)
            elif op == "P":
                points = self.read_polygon()
                self.handle_polygon(points, filled=True)
            elif op == "p":
                points = self.read_polygon()
                self.handle_polygon(points, filled=False)
            elif op == "I":
                x0, y0 = s.read_point()
                w = s.read_float()
                h = s.read_float()
                path = s.read_text()
                self.handle_image(x0, y0, w, h, path)
            else:
                sys.stderr.write("error: unknown xdot opcode '%s'\n" % op)
                sys.exit(1)

        return self.shapes

    def transform(self, x, y):
        return self.parser.transform(x, y)

    def handle_color(self, color, filled=False):
        if filled:
            self.pen.fillcolor = color
        else:
            self.pen.color = color

    def handle_linewidth(self, linewidth):
        self.pen.linewidth = linewidth

    def handle_linestyle(self, style):
        if style == "solid":
            self.pen.dash = ()
        elif style == "dashed":
            self.pen.dash = (6, )       # 6pt on, 6pt off
        elif style == "dotted":
            self.pen.dash = (2, 4)       # 2pt on, 4pt off

    def handle_font(self, size, name):
        self.pen.fontsize = size
        self.pen.fontname = name

    def handle_font_characteristics(self, flags):
        self.pen.bold = bool(flags & Pen.BOLD)
        self.pen.italic = bool(flags & Pen.ITALIC)
        self.pen.underline = bool(flags & Pen.UNDERLINE)
        self.pen.superscript = bool(flags & Pen.SUPERSCRIPT)
        self.pen.subscript = bool(flags & Pen.SUBSCRIPT)
        self.pen.strikethrough = bool(flags & Pen.STRIKE_THROUGH)
        self.pen.overline = bool(flags & Pen.OVERLINE)
        if self.pen.overline:
            sys.stderr.write('warning: overlined text not supported yet\n')

    def handle_text(self, x, y, j, w, t):
        self.shapes.append(elements.TextShape(self.pen, x, y, j, w, t))

    def handle_ellipse(self, x0, y0, w, h, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(elements.EllipseShape(self.pen, x0, y0, w, h, filled=True))
        self.shapes.append(elements.EllipseShape(self.pen, x0, y0, w, h))

    def handle_image(self, x0, y0, w, h, path):
        self.shapes.append(elements.ImageShape(self.pen, x0, y0, w, h, path))

    def handle_line(self, points):
        self.shapes.append(elements.LineShape(self.pen, points))

    def handle_bezier(self, points, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(elements.BezierShape(self.pen, points, filled=True))
        self.shapes.append(elements.BezierShape(self.pen, points))

    def handle_polygon(self, points, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(elements.PolygonShape(self.pen, points, filled=True))
        self.shapes.append(elements.PolygonShape(self.pen, points))


class DotParser(Parser):

    def __init__(self, lexer):
        Parser.__init__(self, lexer)
        self.graph_attrs = {}
        self.node_attrs = {}
        self.edge_attrs = {}

    def parse(self):
        self.parse_graph()
        self.match(EOF)

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
            self.graph_attrs.update(attrs)
            self.handle_graph(attrs)
        elif self.lookahead.type == NODE:
            self.consume()
            self.node_attrs.update(self.parse_attrs())
        elif self.lookahead.type == EDGE:
            self.consume()
            self.edge_attrs.update(self.parse_attrs())
        elif self.lookahead.type in (SUBGRAPH, LCURLY):
            self.parse_subgraph()
        else:
            id = self.parse_node_id()
            if self.lookahead.type == EDGE_OP:
                self.consume()
                node_ids = [id, self.parse_node_id()]
                while self.lookahead.type == EDGE_OP:
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


class XDotParser(DotParser):

    XDOTVERSION = '1.7'

    def __init__(self, xdotcode):
        lexer = DotLexer(buf=xdotcode)
        DotParser.__init__(self, lexer)

        self.nodes = []
        self.edges = []
        self.shapes = []
        self.node_by_name = {}
        self.top_graph = True
        self.width = 0
        self.height = 0

    def handle_graph(self, attrs):
        if self.top_graph:
            # Check xdot version
            try:
                xdotversion = attrs['xdotversion']
            except KeyError:
                pass
            else:
                if float(xdotversion) > float(self.XDOTVERSION):
                    sys.stderr.write('warning: xdot version %s, but supported is %s\n' %
                                     (xdotversion, self.XDOTVERSION))

            # Parse bounding box
            try:
                bb = attrs['bb']
            except KeyError:
                return

            if bb:
                xmin, ymin, xmax, ymax = map(float, bb.split(b","))

                self.xoffset = -xmin
                self.yoffset = -ymax
                self.xscale = 1.0
                self.yscale = -1.0
                # FIXME: scale from points to pixels

                self.width = max(xmax - xmin, 1)
                self.height = max(ymax - ymin, 1)

                self.top_graph = False

        for attr in ("_draw_", "_ldraw_", "_hdraw_", "_tdraw_", "_hldraw_", "_tldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                self.shapes.extend(parser.parse())

    def handle_node(self, id, attrs):
        try:
            pos = attrs['pos']
        except KeyError:
            return

        x, y = self.parse_node_pos(pos)
        w = float(attrs.get('width', 0))*72
        h = float(attrs.get('height', 0))*72
        shapes = []
        for attr in ("_draw_", "_ldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                shapes.extend(parser.parse())
        try:
            url = attrs['URL']
        except KeyError:
            url = None
        else:
            url = url.decode('utf-8')
        node = elements.Node(id, x, y, w, h, shapes, url)
        self.node_by_name[id] = node
        if shapes:
            self.nodes.append(node)

    def handle_edge(self, src_id, dst_id, attrs):
        try:
            pos = attrs['pos']
        except KeyError:
            return

        points = self.parse_edge_pos(pos)
        shapes = []
        for attr in ("_draw_", "_ldraw_", "_hdraw_", "_tdraw_", "_hldraw_", "_tldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                shapes.extend(parser.parse())
        if shapes:
            src = self.node_by_name[src_id]
            dst = self.node_by_name[dst_id]
            self.edges.append(elements.Edge(src, dst, points, shapes))

    def parse(self):
        DotParser.parse(self)
        return elements.Graph(self.width, self.height, self.shapes,
                              self.nodes, self.edges)

    def parse_node_pos(self, pos):
        x, y = pos.split(b",")
        return self.transform(float(x), float(y))

    def parse_edge_pos(self, pos):
        points = []
        for entry in pos.split(b' '):
            fields = entry.split(b',')
            try:
                x, y = fields
            except ValueError:
                # TODO: handle start/end points
                continue
            else:
                points.append(self.transform(float(x), float(y)))
        return points

    def transform(self, x, y):
        # XXX: this is not the right place for this code
        x = (x + self.xoffset)*self.xscale
        y = (y + self.yoffset)*self.yscale
        return x, y

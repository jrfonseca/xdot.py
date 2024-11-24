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

import colorsys
import re
import sys
from typing import Union

from packaging.version import Version

from ..dot.lexer import DotLexer
from ..dot.parser import DotParser

from ..ui.colors import lookup_color
from ..ui.pen import Pen
from ..ui import elements


class XDotAttrParser:
    """Parser for xdot drawing attributes.
    See also:
    - http://www.graphviz.org/doc/info/output.html#d:xdot
    """

    def __init__(self, parser, buf, broken_backslashes):

        # `\` should be escaped as `\\`, but older versions of graphviz xdot
        # output failed to properly escape it.  See also
        # https://github.com/jrfonseca/xdot.py/issues/92
        if not broken_backslashes:
            buf = re.sub(br'\\(.)', br'\1', buf)

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


class XDotParser(DotParser):

    XDOTVERSION = '1.7'

    def __init__(self, xdotcode, graphviz_version=None):
        lexer = DotLexer(buf=xdotcode)
        DotParser.__init__(self, lexer)

        # https://github.com/jrfonseca/xdot.py/issues/92
        self.broken_backslashes = False
        if graphviz_version is not None and \
                Version(graphviz_version) < Version("2.46.0"):
            self.broken_backslashes = True

        self.charset = 'utf-8'

        self.nodes = []
        self.edges = []
        self.shapes = []
        self.node_by_name = {}
        self.top_graph = True
        self.width = 0
        self.height = 0
        self.outputorder = 'breadthfirst'

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

            try:
                self.charset = attrs['charset'].decode('ascii')
            except KeyError:
                pass

            # Parse output order
            try:
                self.outputorder = attrs['outputorder'].decode(self.charset)
            except KeyError:
                pass

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
                parser = XDotAttrParser(self, attrs[attr], self.broken_backslashes)
                self.shapes.extend(parser.parse())

    def decode_attr(self, attrs, name):
        try:
            value = attrs[name]
        except KeyError:
            return None
        else:
            return value.decode(self.charset)

    @staticmethod
    def interpret_esc_nl(esc_string: Union[str, None]):
        r"""Interpret newline escape sequences.

        \n, \l and \r are replaced with newlines, other escaped
        characters such as \\ with themselves.
        """
        if esc_string is None:
            return None
        result = ""
        was_escape = False
        for ch in esc_string:
            if was_escape:
                was_escape = False
                if ch in ['n', 'l', 'r']:
                    result += "\n"
                else:
                    result += ch
            else:
                if ch == "\\":
                    was_escape = True
                else:
                    result += ch
        return result


    def handle_node(self, id, attrs):
        try:
            pos = attrs['pos']
        except KeyError:
            # Node without pos attribute, most likely a subgraph.  We need to
            # create a Node object nevertheless, when one doesn't exist
            # already, so that any edges to/from it don't get lost.
            if id not in self.node_by_name:
                # TODO: Extract the position from subgraph > graph > bb attribute.
                node = elements.Node(id, 0.0, 0.0, 0.0, 0.0, [], None, None)
                self.node_by_name[id] = node
            return

        x, y = self.parse_node_pos(pos)
        w = float(attrs.get('width', 0))*72
        h = float(attrs.get('height', 0))*72
        shapes = []
        for attr in ("_draw_", "_ldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr], self.broken_backslashes)
                shapes.extend(parser.parse())
        url = self.decode_attr(attrs, 'URL')
        tooltip = self.interpret_esc_nl(self.decode_attr(attrs, 'tooltip'))
        node = elements.Node(id, x, y, w, h, shapes, url, tooltip)
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
                parser = XDotAttrParser(self, attrs[attr], self.broken_backslashes)
                shapes.extend(parser.parse())
        if shapes:
            src = self.node_by_name[src_id]
            dst = self.node_by_name[dst_id]
            tooltip = self.interpret_esc_nl(self.decode_attr(attrs, 'tooltip'))
            self.edges.append(elements.Edge(src, dst, points, shapes, tooltip))

    def parse(self):
        DotParser.parse(self)
        return elements.Graph(self.width, self.height, self.shapes,
                              self.nodes, self.edges, self.outputorder)

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

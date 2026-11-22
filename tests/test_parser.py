#
# Copyright 2026 Jose Fonseca
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

"""Unit tests for the dot/xdot parsers and color lookup.

They don't open windows, but importing xdot.ui still needs a display."""


import warnings

import pytest
from pytest import approx

from xdot.dot.lexer import DotLexer, ParseError
from xdot.dot.parser import DotParser


#
# DotParser
#

class RecordingParser(DotParser):

    def __init__(self, dotcode):
        DotParser.__init__(self, DotLexer(buf=dotcode, filename='g.dot'))
        self.graphs = []
        self.nodes = []
        self.edges = []

    def handle_graph(self, attrs):
        self.graphs.append(attrs)

    def handle_node(self, id, attrs):
        self.nodes.append((id, attrs))

    def handle_edge(self, src_id, dst_id, attrs):
        self.edges.append((src_id, dst_id, attrs))


def parse(dotcode):
    parser = RecordingParser(dotcode)
    parser.parse()
    return parser


def test_edge_chain():
    p = parse(b'digraph { a -> b -> c [color=red] }')
    assert p.edges == [
        (b'a', b'b', {'color': b'red'}),
        (b'b', b'c', {'color': b'red'}),
    ]


def test_graph_attrs():
    p = parse(b'strict digraph { graph [rankdir=LR]; rankdir = TB; a }')
    assert p.graphs == [{'rankdir': b'LR'}]
    # `ID = ID` statements are skipped and don't make nodes
    assert p.nodes == [(b'a', {})]


def test_attr_without_value():
    p = parse(b'digraph { a [foo, bar="x"] [baz] }')
    assert p.nodes == [(b'a', {'foo': b'true', 'bar': b'x', 'baz': b'true'})]


def test_quoted_and_html_ids():
    p = parse(b'digraph { "a \\"b\\"" [label=<<b>x</b>>] }')
    assert p.nodes == [(b'a "b"', {'label': b'<b>x</b>'})]


def test_ports():
    p = parse(b'digraph { a:p:n -> b:s }')
    assert p.edges == [(b'a', b'b', {})]


def test_subgraphs():
    p = parse(b'digraph { subgraph cluster_x { a } { b } subgraph { c } }')
    # A named subgraph is also a node
    assert [id for id, attrs in p.nodes] == [b'cluster_x', b'a', b'b', b'c']


def test_extra_graphs_ignored(capsys):
    p = parse(b'digraph { a } digraph { b }')
    assert p.nodes == [(b'a', {})]
    assert capsys.readouterr().err == \
        'warning: g.dot:1:15: ignoring extra token digraph\n'


@pytest.mark.parametrize('dotcode, message', [
    (b'digraph {\n  a -> ;\n}', 'g.dot:2:8:unexpected token ;'),
    (b'digraph {\n  a -> b', 'g.dot:2:9:unexpected end of file'),
    (b'digraph', 'g.dot:1:8:unexpected end of file'),
])
def test_parse_error(dotcode, message):
    with pytest.raises(ParseError) as excinfo:
        parse(dotcode)
    assert str(excinfo.value) == message


def test_parse_error_without_location():
    assert str(ParseError('oops')) == 'oops'


#
# XDotParser
#

def xdot_graph(node_draw=b'', graph_attrs=b'', edge=b''):
    from xdot.ui._xdotparser import XDotParser
    draw = (node_draw + b' e 50 50 10 10').strip()
    xdotcode = b'''digraph {
        graph [bb="0,0,100,100" %s];
        a [pos="50,50", width=1, height=1, _draw_="%s"];
        %s
    }''' % (graph_attrs, draw, edge)
    return XDotParser(xdotcode).parse()


def xdot_text(s):
    s = s.encode('utf-8')
    return b'%d -%s' % (len(s), s)


@pytest.mark.parametrize('color, expected', [
    ('#ff0000', (1.0, 0.0, 0.0, 1.0)),
    ('#00ff0080', (0.0, 1.0, 0.0, 128 / 255)),
    ('0.0,1.0,1.0', (1.0, 0.0, 0.0, 1.0)),
    ('0.0 1.0 1.0', (1.0, 0.0, 0.0, 1.0)),
    ('.5, 1, 1', (0.0, 1.0, 1.0, 1.0)),
    ('navajowhite', (1.0, 0xde / 255, 0xad / 255, 1.0)),
    ('/greens3/2', (0xa1 / 255, 0xd9 / 255, 0x9b / 255, 1.0)),
])
def test_color(color, expected):
    graph = xdot_graph(b'c ' + xdot_text(color) + b' C ' + xdot_text(color))
    shape, = graph.nodes[0].shapes
    assert shape.pen.color == approx(expected, abs=1e-4)
    assert shape.pen.fillcolor == approx(expected, abs=1e-4)


@pytest.mark.parametrize('color, warning', [
    ('[#ff0000;0.5:#0000ff]', 'color gradients not supported'),
    ('nosuchcolor', "unknown color 'nosuchcolor'"),
])
def test_unsupported_color(color, warning, capsys):
    graph = xdot_graph(b'c ' + xdot_text(color))
    shape, = graph.nodes[0].shapes
    # The pen keeps its previous (default) color
    assert shape.pen.color == (0.0, 0.0, 0.0, 1.0)
    assert warning in capsys.readouterr().err


def test_outputorder():
    assert xdot_graph().outputorder == 'breadthfirst'
    assert xdot_graph(graph_attrs=b', outputorder=edgesfirst').outputorder == 'edgesfirst'


def test_newer_xdotversion_warns(capsys):
    xdot_graph(graph_attrs=b', xdotversion=99.0')
    assert 'warning: xdot version 99.0' in capsys.readouterr().err


def test_edge_without_pos_is_skipped():
    graph = xdot_graph(edge=b'a -> a;')
    assert graph.edges == []


def test_dot_parser_reexport():
    import xdot.dot.parser
    from xdot.ui._xdotparser import XDotParser
    assert xdot.dot.parser.XDotParser is XDotParser
    assert not hasattr(xdot.dot.parser, 'NoSuchThing')


#
# Colors
#

def test_lookup_color(capsys):
    from xdot.ui.colors import lookup_color
    assert lookup_color('white') == (1.0, 1.0, 1.0, 1.0)
    assert lookup_color('/blues9/9') == approx(
        (0x08 / 255, 0x30 / 255, 0x6b / 255, 1.0))
    # Out of range brewer index
    assert lookup_color('/blues3/4') is None
    assert lookup_color('/blues3/0') is None
    assert lookup_color('nosuchcolor') is None
    assert "unknown color 'nosuchcolor'" in capsys.readouterr().err


#
# Package
#

def test_deprecated_top_level_names():
    import xdot
    import xdot.ui
    with pytest.warns(UserWarning, match=r'^xdot.DotWidget is deprecated'):
        assert xdot.DotWidget is xdot.ui.DotWidget
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert xdot.ui is xdot.ui
    with pytest.raises(AttributeError):
        xdot.NoSuchThing

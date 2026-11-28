#!/usr/bin/env python3
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

"""Tests for the graph model in xdot.ui.elements: drawing order, highlight
and clipping decisions, and hit-testing, checked on graphs laid out by
Graphviz and drawn onto an off-screen Cairo surface."""


import cairo
import pytest

from xdot.ui import elements


@pytest.fixture
def graph(make_window):
    """Lay out dot code and return the resulting Graph."""
    def layout(dotcode):
        window = make_window(dotcode)
        assert not window.errors
        return window.dotwidget.graph
    return layout


@pytest.fixture
def cr():
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
    return cairo.Context(surface)


@pytest.fixture
def draws(monkeypatch, cr):
    """Record (element, highlight, bounding) for each node and edge drawn
    onto `cr`, ignoring the window's own on-screen draws."""
    calls = []

    def recorder(cls):
        original = cls._draw

        def _draw(self, context, highlight, bounding):
            if context is cr:
                calls.append((self, highlight, bounding))
            original(self, context, highlight, bounding)
        return _draw

    monkeypatch.setattr(elements.Node, '_draw', recorder(elements.Node))
    monkeypatch.setattr(elements.Edge, '_draw', recorder(elements.Edge))
    return calls


def node(graph, name):
    for n in graph.nodes:
        if n.id.decode() == name:
            return n
    raise KeyError(name)


EVERYWHERE = (-1e6, -1e6, 1e6, 1e6)


@pytest.mark.parametrize('outputorder, first', [
    ('breadthfirst', elements.Node),
    ('nodesfirst', elements.Node),
    ('edgesfirst', elements.Edge),
])
def test_outputorder(graph, cr, draws, outputorder, first):
    g = graph(b'digraph { outputorder=%s; a -> b }' % outputorder.encode())
    g.draw(cr)
    kinds = [type(element) for element, _, _ in draws]
    assert kinds[0] is first
    assert kinds.count(elements.Node) == 2
    assert kinds.count(elements.Edge) == 1


def test_highlight_edge_highlights_its_nodes(graph, cr, draws):
    g = graph(b'digraph { a -> b; c }')
    edge, = g.edges
    g.draw(cr, highlight_items={edge})
    highlighted = {element for element, highlight, _ in draws if highlight}
    assert highlighted == {edge, node(g, 'a'), node(g, 'b')}


def test_highlight_node_highlights_its_edges(graph, cr, draws):
    g = graph(b'digraph { a -> b; c }')
    edge, = g.edges
    g.draw(cr, highlight_items={node(g, 'a')})
    highlighted = {element for element, highlight, _ in draws if highlight}
    assert highlighted == {edge, node(g, 'a')}


def test_bounding_dropped_when_graph_fully_visible(graph, cr, draws):
    # Text has unbounded height, so only an unlabelled graph fits entirely
    g = graph(b'digraph { node [label=""]; a -> b }')
    g.draw(cr, bounding=EVERYWHERE)
    assert draws
    assert all(bounding is None for _, _, bounding in draws)


def test_bounding_kept_when_graph_partly_visible(graph, cr, draws):
    # Labels have unbounded height, so lay the nodes out side by side
    g = graph(b'digraph { rankdir=LR; a -> b }')
    a = node(g, 'a')
    bounding = (a.x - 1, a.y - 1, a.x + 1, a.y + 1)
    g.draw(cr, bounding=bounding)
    assert [element for element, _, _ in draws] == [a]
    assert draws[0][2] == bounding


def test_draw_outside_bounding(graph, cr, draws):
    g = graph(b'digraph { a -> b }')
    x0, y0, x1, y1 = g.bounding
    far = (x1 + 100, y1 + 100, x1 + 200, y1 + 200)
    g.draw(cr, bounding=far)
    a = node(g, 'a')
    a.draw(cr, bounding=far)
    assert draws == []
    a.draw(cr)
    assert draws == [(a, False, None)]


def test_get_text(graph):
    g = graph(b'digraph { a; b [label=""] }')
    assert node(g, 'a').get_text() == 'a'
    assert node(g, 'b').get_text() is None


def test_get_size(graph):
    g = graph(b'digraph { a }')
    assert g.get_size() == (g.width, g.height)


def test_repr(graph):
    g = graph(b'digraph { a -> b }')
    edge, = g.edges
    a, b = node(g, 'a'), node(g, 'b')
    assert repr(a) == '<Node %s>' % a.id
    assert repr(edge) == '<Edge %r -> %r>' % (a, b)


def test_edge_jump_off_curve(graph):
    # Inside the bounding box of a diagonal edge's spline, but away from the
    # curve itself, there is nothing to jump through.
    g = graph(b'digraph { a -> {b c d} }')
    radius = 1.0
    for edge in g.edges:
        for shape in edge.shapes:
            x0, y0, x1, y1 = shape.bounding
            for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
                distance = shape.get_smallest_distance(x, y)
                if distance is not None and distance > 10 * radius \
                        and not edge.is_inside_begin(x, y, radius) \
                        and not edge.is_inside_end(x, y, radius):
                    assert edge.get_jump(x, y, radius) is None
                    assert not edge.is_inside(x, y, radius)
                    return
    pytest.fail('no diagonal edge found')

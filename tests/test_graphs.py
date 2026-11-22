#
# Copyright 2015-2026 Jose Fonseca
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

"""Load and render every test graph.

Each graph is shown in a real DotWindow, drawn once on screen, rendered to
`<name>.png` next to the input, and the tooltip code path is exercised for
every node and edge.  Whether the pixels are right is checked by
tests/pixel_regression.py instead.

Run on other graphs with:

    pytest tests/test_graphs.py --graphs foo.dot bar.gv
"""


import glob
import os.path

import cairo
import pytest

from xdot.ui.actions import TooltipContext

from tests.gtkutil import pump


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

GRAPHS = sorted(
    glob.glob(os.path.join(TESTS_DIR, '*.dot')) +
    glob.glob(os.path.join(TESTS_DIR, 'graphs', '*.gv'))
)


def pytest_generate_tests(metafunc):
    if 'graph_path' not in metafunc.fixturenames:
        return
    paths = metafunc.config.getoption('graphs', default=None)
    if paths:
        ids = paths
    else:
        paths = GRAPHS
        ids = [os.path.relpath(path, TESTS_DIR) for path in paths]
    metafunc.parametrize('graph_path', paths, ids=ids)


def render_png(graph, highlight, filename):
    # Scale to give 96 dpi instead of 72 dpi
    dpi = 96.0
    scale = dpi/72.0
    w = int(graph.width*scale)
    h = int(graph.height*scale)

    CAIRO_XMAX = 32767
    CAIRO_YMAX = 32767
    if w >= CAIRO_XMAX:
        w = CAIRO_XMAX
        scale = w/graph.width
        h = int(graph.height*scale)
    if h >= CAIRO_YMAX:
        h = CAIRO_YMAX
        scale = h/graph.height
        w = int(graph.width*scale)

    assert w <= CAIRO_XMAX
    assert h <= CAIRO_YMAX

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)

    cr = cairo.Context(surface)

    cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    cr.paint()

    cr.scale(scale, scale)

    graph.draw(cr, highlight_items=highlight)

    surface.write_to_png(filename)


def test_graph(graph_path, make_window):
    with open(graph_path, 'rb') as f:
        dotcode = f.read()

    window = make_window(dotcode)
    widget = window.dotwidget
    assert window.errors == []

    # Wait for the widget to draw itself on screen
    widget.queue_draw()
    drawn = []
    handler = widget.connect_after('draw', lambda widget, cr: drawn.append(True))
    try:
        pump(lambda: drawn, timeout=60.0)
    finally:
        widget.disconnect(handler)

    name, ext = os.path.splitext(graph_path)
    render_png(widget.graph, widget.highlight, name + '.png')

    # Exercise the tooltip code path for every element with a tooltip
    TooltipContext.set_parent(widget)
    for element in widget.graph.nodes + widget.graph.edges:
        if element.tooltip is not None:
            TooltipContext.reset()
            widget.on_hover(element, None, TooltipContext)
    TooltipContext.reset()

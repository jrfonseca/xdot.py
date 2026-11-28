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

"""Interaction tests for DotWidget/DotWindow.

These run in-process against a real window (use tests/headless.sh when headless),
inject synthetic GDK events through Gtk.main_do_event, so that the regular
GTK signal dispatch takes place, and then check the widget state.

Run with:

    tests/headless.sh python3 -m pytest tests/test_ui.py
"""


import os
import subprocess

import cairo
import pytest
from pytest import approx

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gdk, Gtk

from xdot.ui import DotWidget
from xdot.ui import actions, animation
from xdot.ui.actions import TooltipContext

from tests.gtkutil import pump, button, motion, click, drag, scroll, key, \
    graph_to_window, window_center, wait_animation


#
# Test graphs
#

# A single straight vertical edge, so the edge midpoint is far from both
# nodes.
SIMPLE = b'digraph { a -> b }'

URLS = b'''digraph {
    a [URL="http://example.com/a"];
    b;
    a -> b;
}'''

TOOLTIPS = b'''digraph {
    a [tooltip="<b>bold</b> & <i>not markup</i>"];
    b;
    a -> b [tooltip="edge tip"];
}'''

EDGE_URLS = b'''digraph {
    a -> b [URL="body", headURL="head", tailURL="tail"];
}'''

THREE = b'digraph { a -> b -> c }'

FIND = b'''digraph {
    apple -> banana;
    apricot -> banana;
}'''


#
# Helpers
#

def set_view(widget, x, y, zoom_ratio=1.0):
    widget.zoom_image(zoom_ratio)
    widget.x, widget.y = x, y
    pump()


def node(widget, name):
    for n in widget.graph.nodes:
        if n.id.decode() == name:
            return n
    raise KeyError(name)


def edge_midpoint(widget, edge=None):
    edge = edge or widget.graph.edges[0]
    (x0, y0), (x1, y1) = edge.points[0], edge.points[-1]
    return 0.5 * (x0 + x1), 0.5 * (y0 + y1)


def tooltip_label():
    return TooltipContext.get_widget('tooltip_label')


def tooltip_visible():
    return TooltipContext._tooltip_window.get_visible()


#
# Fixtures
#

@pytest.fixture
def win(make_window):
    return make_window(SIMPLE)


@pytest.fixture
def url_win(make_window):
    return make_window(URLS)


@pytest.fixture
def tooltip_win(make_window):
    return make_window(TOOLTIPS)


@pytest.fixture
def find_win(make_window):
    return make_window(FIND)


class ClickRecorder(DotWidget):

    def __init__(self):
        DotWidget.__init__(self)
        self.clicks = []

    def on_click(self, element, event):
        self.clicks.append(element)
        return True


@pytest.fixture
def click_recorder_win(make_window):
    return make_window(SIMPLE, widget_class=ClickRecorder)


# (512, 480) is DotWindow's default width, narrower than the whole toolbar.
# The find entry used to land in the toolbar overflow, where it has no menu
# item, so find was unreachable and the "f" key focused an unrealized entry,
# logging a GTK critical on the next key press.
@pytest.fixture(params=[(512, 480), (300, 300)], ids=['default', 'narrow'])
def find_key_win(request, make_window):
    return make_window(SIMPLE, size=request.param)


#
# Load
#

def test_zoom_to_fit(win):
    w = win.dotwidget
    assert w.zoom_to_fit_on_resize
    assert w.x == approx(w.graph.width / 2)
    assert w.y == approx(w.graph.height / 2)
    assert len(w.graph.nodes) == 2
    assert len(w.graph.edges) == 1


#
# Mouse
#

def test_pan(win):
    w = win.dotwidget
    set_view(w, 100.0, 100.0, 2.0)
    drag(w, 100, 100, 150, 130)
    assert w.x == approx(100.0 - 50 / 2.0)
    assert w.y == approx(100.0 - 30 / 2.0)
    assert w.zoom_ratio == approx(2.0)
    assert isinstance(w.drag_action, actions.NullAction)
    assert w.history_back == []


def test_pan_middle_button(win):
    w = win.dotwidget
    set_view(w, 100.0, 100.0, 1.0)
    drag(w, 100, 100, 80, 90, button_=2)
    assert w.x == approx(120.0)
    assert w.y == approx(110.0)


def test_zoom_drag(win):
    w = win.dotwidget
    set_view(w, 100.0, 100.0, 1.0)
    # Dragging up/left zooms in
    drag(w, 200, 200, 180, 190, state=Gdk.ModifierType.CONTROL_MASK)
    assert w.zoom_ratio == approx(1.005 ** 30)
    assert not w.zoom_to_fit_on_resize
    # Dragging down/right zooms out
    drag(w, 200, 200, 220, 210, state=Gdk.ModifierType.CONTROL_MASK)
    assert w.zoom_ratio == approx(1.0)
    assert (w.x, w.y) == (100.0, 100.0)


def test_zoom_area(win):
    w = win.dotwidget
    set_view(w, 100.0, 100.0, 1.0)
    rect = w.get_allocation()
    gx0, gy0 = w.window2graph(100, 100)
    gx1, gy1 = w.window2graph(180, 140)
    drag(w, 100, 100, 180, 140, state=Gdk.ModifierType.SHIFT_MASK)
    assert w.zoom_ratio == approx(min(rect.width / (gx1 - gx0),
                                      rect.height / (gy1 - gy0)))
    assert w.x == approx((gx0 + gx1) / 2)
    assert w.y == approx((gy0 + gy1) / 2)


def test_escape_aborts_drag(win):
    w = win.dotwidget
    set_view(w, 100.0, 100.0, 1.0)
    button(w, Gdk.EventType.BUTTON_PRESS, 100, 100,
           state=Gdk.ModifierType.SHIFT_MASK)
    motion(w, 150, 150, Gdk.ModifierType.SHIFT_MASK |
           Gdk.ModifierType.BUTTON1_MASK)
    assert isinstance(w.drag_action, actions.ZoomAreaAction)
    key(win, Gdk.KEY_Escape)
    assert isinstance(w.drag_action, actions.NullAction)
    assert (w.x, w.y, w.zoom_ratio) == (100.0, 100.0, 1.0)


@pytest.mark.parametrize('direction, delta_y, factor', [
    (Gdk.ScrollDirection.UP, 0, DotWidget.ZOOM_INCREMENT),
    (Gdk.ScrollDirection.DOWN, 0, 1 / DotWidget.ZOOM_INCREMENT),
    (Gdk.ScrollDirection.SMOOTH, 2.0, 0.8),
], ids=['up', 'down', 'smooth'])
def test_scroll(win, direction, delta_y, factor):
    w = win.dotwidget
    set_view(w, 40.0, 50.0, 2.0)
    px, py = 150.0, 120.0
    before = w.window2graph(px, py)
    scroll(w, px, py, direction, delta_y)
    assert w.zoom_ratio == approx(2.0 * factor)
    # The point under the cursor stays put
    assert w.window2graph(px, py) == approx(before)


#
# Jumps
#

def test_click_edge_jumps_to_source(win):
    w = win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    history = []
    w.connect('history', lambda widget, b, f: history.append((b, f)))

    click(w, *window_center(w))
    assert w.history_back == [(mx, my)]
    assert history == [(True, False)]
    assert win.back_action.get_sensitive()
    assert not win.forward_action.get_sensitive()

    wait_animation(w)
    a = node(w, 'a')
    assert w.x == approx(a.x)
    assert w.y == approx(a.y)
    assert w.zoom_ratio == approx(1.0)


def test_ctrl_click_edge_jumps_to_destination(win):
    w = win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    # A Ctrl click (press and release without moving) is a zoom drag of zero
    # length, so the zoom doesn't change.
    click(w, *window_center(w), state=Gdk.ModifierType.CONTROL_MASK)
    wait_animation(w)
    b = node(w, 'b')
    assert w.x == approx(b.x)
    assert w.y == approx(b.y)


def test_click_empty_space(win):
    w = win.dotwidget
    set_view(w, -1000.0, -1000.0, 1.0)
    click(w, *window_center(w))
    assert w.history_back == []
    assert (w.x, w.y) == (-1000.0, -1000.0)


def test_back_forward(win):
    w = win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    a = node(w, 'a')

    click(w, *window_center(w))
    wait_animation(w)

    win.back_action.activate()
    wait_animation(w)
    assert w.x == approx(mx)
    assert w.y == approx(my)
    assert not win.back_action.get_sensitive()
    assert win.forward_action.get_sensitive()

    win.forward_action.activate()
    wait_animation(w)
    assert w.x == approx(a.x)
    assert w.y == approx(a.y)
    assert win.back_action.get_sensitive()
    assert not win.forward_action.get_sensitive()


@pytest.mark.parametrize('zoom', [1.0, 4.0])
@pytest.mark.parametrize('offset, hit', [(8, True), (14, False)])
def test_hit_radius_is_constant_in_screen_space(win, zoom, offset, hit):
    # Regression test for d2066a4: the hit radius is 10 pixels whatever the
    # zoom level.
    w = win.dotwidget
    mx, my = edge_midpoint(w)
    cx, cy = window_center(w)
    set_view(w, mx, my, zoom)
    click(w, cx + offset, cy)
    w.animation.stop()
    assert bool(w.history_back) == hit


def test_on_click_overrides_default(click_recorder_win):
    w = click_recorder_win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    click(w, *window_center(w))
    assert w.clicks == [w.graph.edges[0]]
    # The default jump didn't happen
    assert w.history_back == []
    assert isinstance(w.animation, animation.NoAnimation)


#
# URLs
#

def test_click_node_with_url(url_win):
    w = url_win.dotwidget
    a = node(w, 'a')
    set_view(w, a.x, a.y, 1.0)
    clicked = []
    w.connect('clicked', lambda widget, url, event: clicked.append(url))
    click(w, *window_center(w))
    assert clicked == ['http://example.com/a']
    assert w.history_back == []


def test_hover_url_highlights(url_win):
    w = url_win.dotwidget
    a = node(w, 'a')
    set_view(w, a.x, a.y, 1.0)
    motion(w, *window_center(w))
    assert w.highlight == {a}
    motion(w, 1, 1)
    assert w.highlight is None


#
# Hover
#

def test_node_tooltip_is_plain_text(tooltip_win):
    # Regression test for 233a70d
    w = tooltip_win.dotwidget
    a = node(w, 'a')
    set_view(w, a.x, a.y, 1.0)
    motion(w, *window_center(w))
    assert w.highlight == {a}
    assert tooltip_visible()
    label = tooltip_label()
    assert not label.get_use_markup()
    assert label.get_text() == '<b>bold</b> & <i>not markup</i>'


def test_edge_tooltip(tooltip_win):
    w = tooltip_win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    motion(w, *window_center(w))
    assert tooltip_visible()
    assert tooltip_label().get_text() == 'edge tip'


def test_tooltip_hides_when_leaving(tooltip_win):
    w = tooltip_win.dotwidget
    a = node(w, 'a')
    set_view(w, a.x, a.y, 1.0)
    motion(w, *window_center(w))
    assert tooltip_visible()
    motion(w, 1, 1)
    assert not tooltip_visible()
    assert w.highlight is None


#
# Keyboard
#

def test_arrows_pan(win):
    w = win.dotwidget
    set_view(w, 0.0, 0.0, 2.0)
    step = DotWidget.POS_INCREMENT / 2.0
    # Each key press starts from where the previous one left off
    for keyval, expected in (
        (Gdk.KEY_Left, (-step, 0.0)),
        (Gdk.KEY_Right, (0.0, 0.0)),
        (Gdk.KEY_Up, (0.0, -step)),
        (Gdk.KEY_Down, (0.0, 0.0)),
    ):
        key(win, keyval)
        assert (w.x, w.y) == approx(expected), Gdk.keyval_name(keyval)


_inc = DotWidget.ZOOM_INCREMENT


@pytest.mark.parametrize('keyval, factor', [
    pytest.param(keyval, factor, id=Gdk.keyval_name(keyval))
    for keyval, factor in (
        (Gdk.KEY_Page_Up, _inc),
        (Gdk.KEY_plus, _inc),
        (Gdk.KEY_equal, _inc),
        (Gdk.KEY_KP_Add, _inc),
        (Gdk.KEY_Page_Down, 1 / _inc),
        (Gdk.KEY_minus, 1 / _inc),
        (Gdk.KEY_KP_Subtract, 1 / _inc),
    )
])
def test_zoom_keys(win, keyval, factor):
    w = win.dotwidget
    set_view(w, 10.0, 20.0, 1.0)
    key(win, keyval)
    assert w.zoom_ratio == approx(factor)
    assert (w.x, w.y) == (10.0, 20.0)


def test_zoom_to_fit_key(win):
    w = win.dotwidget
    set_view(w, 0.0, 0.0, 10.0)
    key(win, Gdk.KEY_w)
    assert w.zoom_to_fit_on_resize
    assert w.x == approx(w.graph.width / 2)
    assert w.y == approx(w.graph.height / 2)


def test_toggle_toolbar(win):
    toolbar = win.uimanager.get_widget('/ToolBar')
    assert toolbar.get_visible()
    key(win, Gdk.KEY_t)
    assert not toolbar.get_visible()
    key(win, Gdk.KEY_t)
    assert toolbar.get_visible()


def test_quit(win):
    destroyed = []
    win.connect('destroy', lambda w: destroyed.append(True))
    key(win, Gdk.KEY_q)
    assert destroyed == [True]


def test_find_entry_visible(find_key_win):
    assert find_key_win.textentry.get_mapped()


def test_find_key_focuses_entry(find_key_win):
    key(find_key_win, Gdk.KEY_f)
    assert find_key_win.get_focus() is find_key_win.textentry
    # Typing now goes to the entry
    key(find_key_win, Gdk.KEY_a)
    assert find_key_win.textentry.get_text() == 'a'


#
# Toolbar
#

def test_zoom_actions(win):
    w = win.dotwidget

    def action(name):
        win.actiongroup.get_action(name).activate()

    inc = DotWidget.ZOOM_INCREMENT
    set_view(w, 0.0, 0.0, 1.0)
    action('ZoomIn')
    assert w.zoom_ratio == approx(inc)
    action('ZoomOut')
    action('ZoomOut')
    assert w.zoom_ratio == approx(1 / inc)
    action('Zoom100')
    assert w.zoom_ratio == approx(1.0)
    action('ZoomFit')
    assert w.zoom_to_fit_on_resize


def test_history_buttons_initially_disabled(win):
    assert not win.back_action.get_sensitive()
    assert not win.forward_action.get_sensitive()


#
# Find
#

def test_find(find_win):
    win = find_win
    w = win.dotwidget
    entry = win.textentry
    apple, apricot = node(w, 'apple'), node(w, 'apricot')

    entry.set_text('ap')
    pump()
    assert set(w.highlight) == {apple, apricot}
    assert win.find_count.get_label() == '2 nodes found'

    # Hovering doesn't change the search highlight
    banana = node(w, 'banana')
    set_view(w, banana.x, banana.y, 1.0)
    motion(w, *window_center(w))
    assert set(w.highlight) == {apple, apricot}

    entry.activate()
    wait_animation(w)
    assert w.x == approx(apple.x)
    assert w.y == approx(apple.y)
    assert win.find_next_toolitem.get_sensitive()

    win.actiongroup.get_action('FindNext').activate()
    wait_animation(w)
    assert w.x == approx(apricot.x)
    assert w.y == approx(apricot.y)
    assert not win.find_next_toolitem.get_sensitive()

    entry.set_text('')
    pump()
    assert w.highlight is None
    assert win.find_count.get_label() == ''


def test_find_no_match(find_win):
    win = find_win
    entry = win.textentry
    entry.set_text('cherry')
    pump()
    assert win.dotwidget.highlight == []
    assert win.find_count.get_label() == ''
    entry.activate()
    pump()
    assert win.dotwidget.history_back == []


def test_find_invalid_regex(find_win, capsys):
    # Happens routinely while typing, e.g. "a(" on the way to "a(b)"
    win = find_win
    win.textentry.set_text('a(')
    pump()
    assert win.dotwidget.highlight == []
    win.textentry.activate()
    pump()
    assert win.dotwidget.history_back == []
    assert 're.compile() failed' in capsys.readouterr().err


def test_find_activate_empty_returns_focus(find_win):
    win = find_win
    entry = win.textentry
    win.set_focus(entry)
    entry.set_text('ap')
    pump()
    entry.set_text('')
    entry.activate()
    pump()
    assert win.dotwidget.highlight is None
    assert win.get_focus() is win.dotwidget


#
# Files
#

def rewrite(path, dotcode):
    """Rewrite `path`, making sure the mtime changes even on file systems
    with a coarse timestamp resolution."""
    mtime_ns = path.stat().st_mtime_ns + 10**9
    path.write_bytes(dotcode)
    os.utime(path, ns=(mtime_ns, mtime_ns))


@pytest.fixture
def file_win(make_window, tmp_path):
    path = tmp_path / 'g.dot'
    path.write_bytes(SIMPLE)
    win = make_window(b'digraph {}')
    win.open_file(str(path))
    pump()
    win.path = path
    return win


def test_open_file(file_win):
    win = file_win
    w = win.dotwidget
    assert win.get_title() == 'g.dot - Dot Viewer'
    assert w.openfilename == str(win.path)
    assert len(w.graph.nodes) == 2
    assert w.zoom_to_fit_on_resize


def test_open_missing_file(file_win, tmp_path):
    win = file_win
    win.open_file(str(tmp_path / 'missing.dot'))
    assert len(win.errors) == 1
    assert 'missing.dot' in win.errors[0]
    # The previous graph stays
    assert win.dotwidget.openfilename == str(win.path)
    assert len(win.dotwidget.graph.nodes) == 2


def _reload_key(win):
    key(win, Gdk.KEY_r)


def _reload_action(win):
    win.actiongroup.get_action('Reload').activate()
    pump()


@pytest.mark.parametrize('trigger', [_reload_key, _reload_action],
                         ids=['key', 'action'])
def test_reload(file_win, trigger):
    win = file_win
    w = win.dotwidget
    set_view(w, 5.0, 6.0, 2.0)
    w.history_back.append((1.0, 2.0))
    rewrite(win.path, THREE)
    trigger(win)
    assert len(w.graph.nodes) == 3
    # The view isn't reset
    assert (w.x, w.y, w.zoom_ratio) == (5.0, 6.0, 2.0)
    assert w.history_back == []


def test_auto_reload(file_win):
    win = file_win
    w = win.dotwidget
    rewrite(win.path, THREE)
    # The first poll that sees a new mtime waits, in case the file is still
    # being written
    w.update()
    assert len(w.graph.nodes) == 2
    w.update()
    assert len(w.graph.nodes) == 3
    # Nothing changed since
    graph = w.graph
    w.update()
    assert w.graph is graph


def test_reload_syntax_error(file_win):
    win = file_win
    w = win.dotwidget
    rewrite(win.path, b'digraph { a -> }')
    w.reload()
    assert len(win.errors) == 1
    assert 'syntax error' in win.errors[0]
    assert len(w.graph.nodes) == 2


def test_missing_filter(file_win):
    win = file_win
    w = win.dotwidget
    win.set_filter('no-such-graphviz-filter')
    w.reload()
    assert win.errors == ['no-such-graphviz-filter: No such file or directory']
    assert len(w.graph.nodes) == 2


#
# Export
#

def test_export_file(file_win, tmp_path):
    win = file_win
    win.export_file(str(tmp_path / 'out'), 'svg')
    assert (tmp_path / 'out.svg').read_bytes().startswith(b'<?xml')
    win.export_file(str(tmp_path / 'out2.svg'), 'svg')
    assert (tmp_path / 'out2.svg').exists()
    assert not (tmp_path / 'out2.svg.svg').exists()


def test_export_dialog(file_win, tmp_path, monkeypatch):
    seen = []

    def run(chooser):
        seen.append((chooser.get_current_name(), chooser.get_filter().get_name()))
        return Gtk.ResponseType.OK

    monkeypatch.setattr(Gtk.FileChooserDialog, 'run', run)
    monkeypatch.setattr(Gtk.FileChooserDialog, 'get_filename',
                        lambda chooser: str(tmp_path / 'exported'))
    file_win.actiongroup.get_action('Export').activate()
    pump()
    assert seen == [('g', 'PNG image')]
    assert (tmp_path / 'exported.png').read_bytes().startswith(b'\x89PNG')


@pytest.fixture
def fake_export_dialog(monkeypatch, tmp_path):
    """Make the export dialog answer OK with tmp_path/exported, and record
    the name it suggested."""
    seen = []

    def run(chooser):
        seen.append(chooser.get_current_name())
        return Gtk.ResponseType.OK

    monkeypatch.setattr(Gtk.FileChooserDialog, 'run', run)
    monkeypatch.setattr(Gtk.FileChooserDialog, 'get_filename',
                        lambda chooser: str(tmp_path / 'exported'))
    return seen


def test_export_without_file(win, fake_export_dialog, tmp_path):
    # As with `xdot -`: there is no file to export from, nor a name to suggest
    win.actiongroup.get_action('Export').activate()
    pump()
    assert fake_export_dialog == ['']
    assert (tmp_path / 'exported.png').read_bytes().startswith(b'\x89PNG')


def test_export_xdot_without_file(make_window, fake_export_dialog, tmp_path):
    # As with `xdot -n -`
    win = make_window(b'digraph {}')
    win.set_filter(None)
    win.set_dotcode(subprocess.check_output(['dot', '-Txdot'], input=SIMPLE))
    pump()
    assert len(win.dotwidget.graph.nodes) == 2
    win.actiongroup.get_action('Export').activate()
    pump()
    assert (tmp_path / 'exported.png').read_bytes().startswith(b'\x89PNG')


def test_export_shown_graph(file_win, tmp_path):
    # What is exported is the graph shown, even if the file has changed since
    shown = len(file_win.dotwidget.graph.nodes)
    file_win.path.write_bytes(b'digraph { x -> y -> z }')
    file_win.export_file(str(tmp_path / 'out'), 'plain')
    nodes = [line for line in (tmp_path / 'out.plain').read_text().splitlines()
             if line.startswith('node ')]
    assert len(nodes) == shown


def test_export_nothing(make_window, monkeypatch):
    win = make_window(b'not a graph')
    assert win.errors
    assert win.dotwidget.dotcode is None

    def run(chooser):
        raise AssertionError('no dialog expected')
    monkeypatch.setattr(Gtk.FileChooserDialog, 'run', run)
    win.actiongroup.get_action('Export').activate()
    pump()


def test_export_without_filter(make_window, tmp_path):
    # As with `xdot -n file.xdot`
    path = tmp_path / 'g.xdot'
    path.write_bytes(subprocess.check_output(['dot', '-Txdot'], input=SIMPLE))
    win = make_window(b'digraph {}')
    win.set_filter(None)
    win.open_file(str(path))
    pump()
    assert len(win.dotwidget.graph.nodes) == 2
    win.export_file(str(tmp_path / 'out'), 'svg')
    assert (tmp_path / 'out.svg').exists()


#
# More view changes
#

def test_resize_refits(win):
    w = win.dotwidget

    def resize(width, height):
        old = w.get_allocated_width()
        win.resize(width, height)
        pump(lambda: w.get_allocated_width() != old)
        pump()

    zoom = w.zoom_ratio
    resize(320, 240)
    assert w.zoom_ratio < zoom
    assert w.zoom_to_fit_on_resize

    # After zooming by hand, resizing leaves the zoom alone
    key(win, Gdk.KEY_plus)
    zoom = w.zoom_ratio
    resize(640, 480)
    assert w.zoom_ratio == zoom


def test_zoom_area_click(win):
    # A Shift click is a zoom area of zero size, which zooms in a step
    w = win.dotwidget
    set_view(w, -1000.0, -1000.0, 1.0)
    click(w, *window_center(w), state=Gdk.ModifierType.SHIFT_MASK)
    assert w.zoom_ratio == approx(DotWidget.ZOOM_INCREMENT)
    assert (w.x, w.y) == approx((-1000.0, -1000.0))


class FakeZoomGesture:

    def __init__(self, point, x=0.0, y=0.0):
        self.point = (point, x, y)

    def get_point(self):
        return self.point


def test_pinch_zoom(win):
    w = win.dotwidget
    set_view(w, 40.0, 50.0, 1.0)
    px, py = 150.0, 120.0
    before = w.window2graph(px, py)
    # Scale changes are damped to the cube root
    w.on_scale_changed(FakeZoomGesture(True, px, py), 8.0)
    assert w.zoom_ratio == approx(2.0)
    assert w.window2graph(px, py) == approx(before)


def test_pinch_zoom_without_point(win):
    w = win.dotwidget
    set_view(w, 40.0, 50.0, 1.0)
    w.on_scale_changed(FakeZoomGesture(False), 8.0)
    assert w.zoom_ratio == approx(2.0)
    assert (w.x, w.y) == (40.0, 50.0)


def test_right_click_does_nothing(win):
    w = win.dotwidget
    mx, my = edge_midpoint(w)
    set_view(w, mx, my, 1.0)
    click(w, *window_center(w), button_=3)
    assert w.history_back == []
    assert (w.x, w.y) == (mx, my)


#
# Edge URLs
#

def _edge_tail(e):
    return e.points[0]


def _edge_head(e):
    return e.points[-1]


def _edge_middle(e):
    (x0, y0), (x1, y1) = e.points[0], e.points[-1]
    return 0.5 * (x0 + x1), 0.5 * (y0 + y1)


@pytest.mark.parametrize('where, url', [
    (_edge_tail, 'tail'),
    (_edge_head, 'head'),
    (_edge_middle, 'body'),
], ids=['tail', 'head', 'body'])
def test_click_edge_url(make_window, where, url):
    win = make_window(EDGE_URLS)
    w = win.dotwidget
    e = w.graph.edges[0]
    # pos lists the points from tail (a) to head (b)
    a, b = node(w, 'a'), node(w, 'b')
    assert abs(e.points[0][1] - a.y) < abs(e.points[0][1] - b.y)
    set_view(w, *edge_midpoint(w), 1.0)
    clicked = []
    w.connect('clicked', lambda widget, url, event: clicked.append(url))
    click(w, *graph_to_window(w, *where(e)))
    assert clicked == [url]
    assert w.history_back == []


#
# Window API
#

def test_window_set_xdotcode(win):
    w = win.dotwidget
    set_view(w, 0.0, 0.0, 10.0)
    xdotcode = subprocess.check_output(['dot', '-Txdot'], input=THREE)
    win.set_xdotcode(xdotcode, 'three.xdot')
    pump()
    assert len(w.graph.nodes) == 3
    assert win.get_title() == 'three.xdot - Dot Viewer'
    assert w.zoom_to_fit_on_resize
    assert w.x == approx(w.graph.width / 2)
    assert w.y == approx(w.graph.height / 2)


#
# Printing
#

def test_print(win, monkeypatch):
    w = win.dotwidget
    calls = []

    def run(op, action, parent):
        calls.append((action, parent, op.get_print_settings()))
        # What the print dialog would do
        op.set_print_settings(Gtk.PrintSettings())
        return Gtk.PrintOperationResult.APPLY

    monkeypatch.setattr(Gtk.PrintOperation, 'run', run)
    monkeypatch.setattr(DotWidget, 'print_settings', None)
    key(win, Gdk.KEY_p)
    assert calls == [(Gtk.PrintOperationAction.PRINT_DIALOG, win, None)]
    settings = w.print_settings
    assert settings is not None
    # The settings are reused next time
    key(win, Gdk.KEY_p)
    assert calls[1][2] is settings


def test_print_draws_page(win):
    w = win.dotwidget
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 480)

    class FakePrintContext:
        def get_cairo_context(self):
            return cairo.Context(surface)

    op = Gtk.PrintOperation()
    assert w.begin_print(op, FakePrintContext())
    w.draw_page(op, FakePrintContext(), 0)
    surface.flush()
    assert any(surface.get_data())

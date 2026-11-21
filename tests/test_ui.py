#!/usr/bin/env python3
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

These run in-process against a real window (use xvfb-run when headless),
inject synthetic GDK events through Gtk.main_do_event, so that the regular
GTK signal dispatch takes place, and then check the widget state.

Run with:

    xvfb-run -a python3 -m unittest -v tests.test_ui
"""


import math
import time
import unittest

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gtk

from xdot.ui import DotWidget, DotWindow
from xdot.ui import actions, animation
from xdot.ui.actions import TooltipContext


#
# GLib/GTK warnings are test failures
#

FATAL_LEVELS = GLib.LogLevelFlags.LEVEL_ERROR | \
               GLib.LogLevelFlags.LEVEL_CRITICAL | \
               GLib.LogLevelFlags.LEVEL_WARNING

# See test.py
IGNORED_MESSAGES = [
    'Error loading theme icon ',
]

log_errors = []


def log_writer(log_level, fields, n_fields, user_data):
    if log_level & FATAL_LEVELS:
        message = GLib.log_writer_format_fields(log_level, fields, False)
        if not any(ignored in message for ignored in IGNORED_MESSAGES):
            log_errors.append(message)
    return GLib.log_writer_default(log_level, fields, user_data)


def setUpModule():
    if Gdk.Display.get_default() is None:
        raise unittest.SkipTest('no display (run under xvfb-run)')
    # Can only be set once per process.
    GLib.log_set_writer_func(log_writer, None)


#
# Helpers
#

def pump(until=None, timeout=2.0):
    """Run the main loop until `until()` is true, or until no events are
    pending if `until` is None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if until is None:
            if not Gtk.events_pending():
                return True
            Gtk.main_iteration_do(False)
        else:
            if until():
                return True
            Gtk.main_iteration_do(False)
            time.sleep(0.001)
    if until is None:
        return True
    raise AssertionError('timed out waiting for condition')


# Synthetic events own a reference to their GdkWindow which PyGObject does
# not take when assigning the field, so never free them.
_events = []


def _new_event(type_, window, device):
    ev = Gdk.Event.new(type_)
    ev.window = window
    ev.send_event = 1
    ev.time = Gtk.get_current_event_time()
    ev.set_device(device)
    _events.append(ev)
    return ev


def _pointer():
    return Gdk.Display.get_default().get_default_seat().get_pointer()


def _keyboard():
    return Gdk.Display.get_default().get_default_seat().get_keyboard()


def button(widget, type_, x, y, button=1, state=0):
    ev = _new_event(type_, widget.get_window(), _pointer())
    ev.x, ev.y = float(x), float(y)
    ev.button = button
    ev.state = Gdk.ModifierType(state)
    Gtk.main_do_event(ev)
    pump()


def motion(widget, x, y, state=0):
    ev = _new_event(Gdk.EventType.MOTION_NOTIFY, widget.get_window(), _pointer())
    ev.x, ev.y = float(x), float(y)
    ev.is_hint = 0
    ev.state = Gdk.ModifierType(state)
    Gtk.main_do_event(ev)
    pump()


def click(widget, x, y, button_=1, state=0):
    button(widget, Gdk.EventType.BUTTON_PRESS, x, y, button_, state)
    button(widget, Gdk.EventType.BUTTON_RELEASE, x, y, button_, state)


def drag(widget, x0, y0, x1, y1, button_=1, state=0, steps=4):
    mask = {1: Gdk.ModifierType.BUTTON1_MASK,
            2: Gdk.ModifierType.BUTTON2_MASK}[button_]
    button(widget, Gdk.EventType.BUTTON_PRESS, x0, y0, button_, state)
    for i in range(1, steps + 1):
        t = i / steps
        motion(widget, x0 + (x1 - x0)*t, y0 + (y1 - y0)*t, state | mask)
    button(widget, Gdk.EventType.BUTTON_RELEASE, x1, y1, button_, state | mask)


def scroll(widget, x, y, direction, delta_y=0.0):
    ev = _new_event(Gdk.EventType.SCROLL, widget.get_window(), _pointer())
    ev.x, ev.y = float(x), float(y)
    ev.direction = direction
    ev.delta_x, ev.delta_y = 0.0, float(delta_y)
    Gtk.main_do_event(ev)
    pump()


def key(window, keyval, state=0):
    """Send a key press/release pair to the toplevel window, which forwards it
    to the focus widget like a real key press."""
    keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
    ok, entries = keymap.get_entries_for_keyval(keyval)
    keycode = entries[0].keycode if ok and entries else 0
    for type_ in (Gdk.EventType.KEY_PRESS, Gdk.EventType.KEY_RELEASE):
        ev = _new_event(type_, window.get_window(), _keyboard())
        ev.keyval = keyval
        ev.hardware_keycode = keycode
        ev.state = Gdk.ModifierType(state)
        Gtk.main_do_event(ev)
    pump()


def graph_to_window(widget, gx, gy):
    """Inverse of DotWidget.window2graph."""
    rect = widget.get_allocation()
    x = (gx - widget.x) * widget.zoom_ratio + 0.5 * rect.width
    y = (gy - widget.y) * widget.zoom_ratio + 0.5 * rect.height
    return x, y


def window_center(widget):
    rect = widget.get_allocation()
    return 0.5 * rect.width, 0.5 * rect.height


def wait_animation(widget):
    pump(lambda: isinstance(widget.animation, animation.NoAnimation))
    pump()


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

FIND = b'''digraph {
    apple -> banana;
    apricot -> banana;
}'''


class UITestCase(unittest.TestCase):

    widget_class = DotWidget
    dotcode = SIMPLE
    window_size = (640, 480)

    def setUp(self):
        del log_errors[:]
        self.widget = self.widget_class()
        width, height = self.window_size
        self.window = DotWindow(self.widget, width=width, height=height)
        self.window.set_dotcode(self.dotcode)
        self.window.show_all()
        pump(lambda: self.widget.get_allocated_width() > 1 and
             self.widget.get_window() is not None and
             self.widget.get_window().is_viewable())
        pump()

    def tearDown(self):
        TooltipContext.reset()
        self.window.destroy()
        pump()
        self.assertEqual(log_errors, [], 'GLib/GTK warnings were logged')

    def set_view(self, x, y, zoom_ratio=1.0):
        self.widget.zoom_image(zoom_ratio)
        self.widget.x, self.widget.y = x, y
        pump()

    def node(self, name):
        for node in self.widget.graph.nodes:
            if node.id.decode() == name:
                return node
        raise KeyError(name)

    def edge_midpoint(self, edge=None):
        edge = edge or self.widget.graph.edges[0]
        (x0, y0), (x1, y1) = edge.points[0], edge.points[-1]
        return 0.5 * (x0 + x1), 0.5 * (y0 + y1)


class TestLoad(UITestCase):

    def test_zoom_to_fit(self):
        w = self.widget
        self.assertTrue(w.zoom_to_fit_on_resize)
        self.assertAlmostEqual(w.x, w.graph.width / 2)
        self.assertAlmostEqual(w.y, w.graph.height / 2)
        self.assertEqual(len(w.graph.nodes), 2)
        self.assertEqual(len(w.graph.edges), 1)


class TestMouse(UITestCase):

    def test_pan(self):
        w = self.widget
        self.set_view(100.0, 100.0, 2.0)
        drag(w, 100, 100, 150, 130)
        self.assertAlmostEqual(w.x, 100.0 - 50 / 2.0)
        self.assertAlmostEqual(w.y, 100.0 - 30 / 2.0)
        self.assertAlmostEqual(w.zoom_ratio, 2.0)
        self.assertIsInstance(w.drag_action, actions.NullAction)
        self.assertEqual(w.history_back, [])

    def test_pan_middle_button(self):
        w = self.widget
        self.set_view(100.0, 100.0, 1.0)
        drag(w, 100, 100, 80, 90, button_=2)
        self.assertAlmostEqual(w.x, 120.0)
        self.assertAlmostEqual(w.y, 110.0)

    def test_zoom_drag(self):
        w = self.widget
        self.set_view(100.0, 100.0, 1.0)
        # Dragging up/left zooms in
        drag(w, 200, 200, 180, 190, state=Gdk.ModifierType.CONTROL_MASK)
        self.assertAlmostEqual(w.zoom_ratio, 1.005 ** 30)
        self.assertFalse(w.zoom_to_fit_on_resize)
        # Dragging down/right zooms out
        drag(w, 200, 200, 220, 210, state=Gdk.ModifierType.CONTROL_MASK)
        self.assertAlmostEqual(w.zoom_ratio, 1.0)
        self.assertEqual((w.x, w.y), (100.0, 100.0))

    def test_zoom_area(self):
        w = self.widget
        self.set_view(100.0, 100.0, 1.0)
        rect = w.get_allocation()
        gx0, gy0 = w.window2graph(100, 100)
        gx1, gy1 = w.window2graph(180, 140)
        drag(w, 100, 100, 180, 140, state=Gdk.ModifierType.SHIFT_MASK)
        self.assertAlmostEqual(w.zoom_ratio,
                               min(rect.width / (gx1 - gx0),
                                   rect.height / (gy1 - gy0)))
        self.assertAlmostEqual(w.x, (gx0 + gx1) / 2)
        self.assertAlmostEqual(w.y, (gy0 + gy1) / 2)

    def test_escape_aborts_drag(self):
        w = self.widget
        self.set_view(100.0, 100.0, 1.0)
        button(w, Gdk.EventType.BUTTON_PRESS, 100, 100,
               state=Gdk.ModifierType.SHIFT_MASK)
        motion(w, 150, 150, Gdk.ModifierType.SHIFT_MASK |
               Gdk.ModifierType.BUTTON1_MASK)
        self.assertIsInstance(w.drag_action, actions.ZoomAreaAction)
        key(self.window, Gdk.KEY_Escape)
        self.assertIsInstance(w.drag_action, actions.NullAction)
        self.assertEqual((w.x, w.y, w.zoom_ratio), (100.0, 100.0, 1.0))

    def _check_scroll(self, direction, delta_y, expected_factor):
        w = self.widget
        self.set_view(40.0, 50.0, 2.0)
        px, py = 150.0, 120.0
        before = w.window2graph(px, py)
        scroll(w, px, py, direction, delta_y)
        self.assertAlmostEqual(w.zoom_ratio, 2.0 * expected_factor)
        # The point under the cursor stays put
        after = w.window2graph(px, py)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])

    def test_scroll_up(self):
        self._check_scroll(Gdk.ScrollDirection.UP, 0,
                           DotWidget.ZOOM_INCREMENT)

    def test_scroll_down(self):
        self._check_scroll(Gdk.ScrollDirection.DOWN, 0,
                           1 / DotWidget.ZOOM_INCREMENT)

    def test_scroll_smooth(self):
        self._check_scroll(Gdk.ScrollDirection.SMOOTH, 2.0, 0.8)


class TestJump(UITestCase):

    def test_click_edge_jumps_to_source(self):
        w = self.widget
        mx, my = self.edge_midpoint()
        self.set_view(mx, my, 1.0)
        history = []
        w.connect('history', lambda widget, b, f: history.append((b, f)))

        click(w, *window_center(w))
        self.assertEqual(w.history_back, [(mx, my)])
        self.assertEqual(history, [(True, False)])
        self.assertTrue(self.window.back_action.get_sensitive())
        self.assertFalse(self.window.forward_action.get_sensitive())

        wait_animation(w)
        a = self.node('a')
        self.assertAlmostEqual(w.x, a.x)
        self.assertAlmostEqual(w.y, a.y)
        self.assertAlmostEqual(w.zoom_ratio, 1.0)

    def test_ctrl_click_edge_jumps_to_destination(self):
        w = self.widget
        mx, my = self.edge_midpoint()
        self.set_view(mx, my, 1.0)
        # A Ctrl click (press and release without moving) is a zoom drag of
        # zero length, so the zoom doesn't change.
        click(w, *window_center(w), state=Gdk.ModifierType.CONTROL_MASK)
        wait_animation(w)
        b = self.node('b')
        self.assertAlmostEqual(w.x, b.x)
        self.assertAlmostEqual(w.y, b.y)

    def test_click_empty_space(self):
        w = self.widget
        self.set_view(-1000.0, -1000.0, 1.0)
        click(w, *window_center(w))
        self.assertEqual(w.history_back, [])
        self.assertEqual((w.x, w.y), (-1000.0, -1000.0))

    def test_back_forward(self):
        w = self.widget
        mx, my = self.edge_midpoint()
        self.set_view(mx, my, 1.0)
        a = self.node('a')

        click(w, *window_center(w))
        wait_animation(w)

        self.window.back_action.activate()
        wait_animation(w)
        self.assertAlmostEqual(w.x, mx)
        self.assertAlmostEqual(w.y, my)
        self.assertFalse(self.window.back_action.get_sensitive())
        self.assertTrue(self.window.forward_action.get_sensitive())

        self.window.forward_action.activate()
        wait_animation(w)
        self.assertAlmostEqual(w.x, a.x)
        self.assertAlmostEqual(w.y, a.y)
        self.assertTrue(self.window.back_action.get_sensitive())
        self.assertFalse(self.window.forward_action.get_sensitive())

    def test_hit_radius_is_constant_in_screen_space(self):
        # Regression test for d2066a4: the hit radius is 10 pixels whatever
        # the zoom level.
        w = self.widget
        mx, my = self.edge_midpoint()
        cx, cy = window_center(w)
        for zoom in (1.0, 4.0):
            for offset, hit in ((8, True), (14, False)):
                with self.subTest(zoom=zoom, offset=offset):
                    del w.history_back[:]
                    self.set_view(mx, my, zoom)
                    click(w, cx + offset, cy)
                    w.animation.stop()
                    self.assertEqual(bool(w.history_back), hit)


class ClickRecorder(DotWidget):

    def __init__(self):
        DotWidget.__init__(self)
        self.clicks = []

    def on_click(self, element, event):
        self.clicks.append(element)
        return True


class TestOnClickOverride(UITestCase):

    widget_class = ClickRecorder

    def test_on_click_overrides_default(self):
        w = self.widget
        mx, my = self.edge_midpoint()
        self.set_view(mx, my, 1.0)
        click(w, *window_center(w))
        self.assertEqual(w.clicks, [w.graph.edges[0]])
        # The default jump didn't happen
        self.assertEqual(w.history_back, [])
        self.assertIsInstance(w.animation, animation.NoAnimation)


class TestUrl(UITestCase):

    dotcode = URLS

    def test_click_node_with_url(self):
        w = self.widget
        a = self.node('a')
        self.set_view(a.x, a.y, 1.0)
        clicked = []
        w.connect('clicked', lambda widget, url, event: clicked.append(url))
        click(w, *window_center(w))
        self.assertEqual(clicked, ['http://example.com/a'])
        self.assertEqual(w.history_back, [])

    def test_hover_url_highlights(self):
        w = self.widget
        a = self.node('a')
        self.set_view(a.x, a.y, 1.0)
        motion(w, *window_center(w))
        self.assertEqual(w.highlight, {a})
        motion(w, 1, 1)
        self.assertIsNone(w.highlight)


class TestHover(UITestCase):

    dotcode = TOOLTIPS

    def tooltip_label(self):
        return TooltipContext.get_widget('tooltip_label')

    def test_node_tooltip_is_plain_text(self):
        # Regression test for 233a70d
        w = self.widget
        a = self.node('a')
        self.set_view(a.x, a.y, 1.0)
        motion(w, *window_center(w))
        self.assertEqual(w.highlight, {a})
        self.assertTrue(TooltipContext._tooltip_window.get_visible())
        label = self.tooltip_label()
        self.assertFalse(label.get_use_markup())
        self.assertEqual(label.get_text(),
                         '<b>bold</b> & <i>not markup</i>')

    def test_edge_tooltip(self):
        w = self.widget
        mx, my = self.edge_midpoint()
        self.set_view(mx, my, 1.0)
        motion(w, *window_center(w))
        self.assertTrue(TooltipContext._tooltip_window.get_visible())
        self.assertEqual(self.tooltip_label().get_text(), 'edge tip')

    def test_tooltip_hides_when_leaving(self):
        w = self.widget
        a = self.node('a')
        self.set_view(a.x, a.y, 1.0)
        motion(w, *window_center(w))
        self.assertTrue(TooltipContext._tooltip_window.get_visible())
        motion(w, 1, 1)
        self.assertFalse(TooltipContext._tooltip_window.get_visible())
        self.assertIsNone(w.highlight)


class TestKeyboard(UITestCase):

    def test_arrows_pan(self):
        w = self.widget
        self.set_view(0.0, 0.0, 2.0)
        step = DotWidget.POS_INCREMENT / 2.0
        for keyval, expected in (
            (Gdk.KEY_Left, (-step, 0.0)),
            (Gdk.KEY_Right, (0.0, 0.0)),
            (Gdk.KEY_Up, (0.0, -step)),
            (Gdk.KEY_Down, (0.0, 0.0)),
        ):
            with self.subTest(keyval=Gdk.keyval_name(keyval)):
                key(self.window, keyval)
                self.assertAlmostEqual(w.x, expected[0])
                self.assertAlmostEqual(w.y, expected[1])

    def test_zoom_keys(self):
        w = self.widget
        inc = DotWidget.ZOOM_INCREMENT
        for keyval, factor in (
            (Gdk.KEY_Page_Up, inc),
            (Gdk.KEY_plus, inc),
            (Gdk.KEY_equal, inc),
            (Gdk.KEY_KP_Add, inc),
            (Gdk.KEY_Page_Down, 1 / inc),
            (Gdk.KEY_minus, 1 / inc),
            (Gdk.KEY_KP_Subtract, 1 / inc),
        ):
            with self.subTest(keyval=Gdk.keyval_name(keyval)):
                self.set_view(10.0, 20.0, 1.0)
                key(self.window, keyval)
                self.assertAlmostEqual(w.zoom_ratio, factor)
                self.assertEqual((w.x, w.y), (10.0, 20.0))

    def test_zoom_to_fit_key(self):
        w = self.widget
        self.set_view(0.0, 0.0, 10.0)
        key(self.window, Gdk.KEY_w)
        self.assertTrue(w.zoom_to_fit_on_resize)
        self.assertAlmostEqual(w.x, w.graph.width / 2)
        self.assertAlmostEqual(w.y, w.graph.height / 2)

    def test_toggle_toolbar(self):
        toolbar = self.window.uimanager.get_widget('/ToolBar')
        self.assertTrue(toolbar.get_visible())
        key(self.window, Gdk.KEY_t)
        self.assertFalse(toolbar.get_visible())
        key(self.window, Gdk.KEY_t)
        self.assertTrue(toolbar.get_visible())

    def test_quit(self):
        destroyed = []
        self.window.connect('destroy', lambda win: destroyed.append(True))
        key(self.window, Gdk.KEY_q)
        self.assertEqual(destroyed, [True])


class TestFindKey(UITestCase):

    # The find entry is only shown when the toolbar is wide enough.  In
    # narrower windows it is in the toolbar overflow menu, unrealized, and
    # sending key events to it after focusing it logs a GTK critical.
    window_size = (1000, 480)

    def test_find_key_focuses_entry(self):
        self.assertTrue(self.window.textentry.get_mapped())
        key(self.window, Gdk.KEY_f)
        self.assertIs(self.window.get_focus(), self.window.textentry)


class TestToolbar(UITestCase):

    def action(self, name):
        return self.window.actiongroup.get_action(name)

    def test_zoom_actions(self):
        w = self.widget
        inc = DotWidget.ZOOM_INCREMENT
        self.set_view(0.0, 0.0, 1.0)
        self.action('ZoomIn').activate()
        self.assertAlmostEqual(w.zoom_ratio, inc)
        self.action('ZoomOut').activate()
        self.action('ZoomOut').activate()
        self.assertAlmostEqual(w.zoom_ratio, 1 / inc)
        self.action('Zoom100').activate()
        self.assertAlmostEqual(w.zoom_ratio, 1.0)
        self.action('ZoomFit').activate()
        self.assertTrue(w.zoom_to_fit_on_resize)

    def test_history_buttons_initially_disabled(self):
        self.assertFalse(self.window.back_action.get_sensitive())
        self.assertFalse(self.window.forward_action.get_sensitive())


class TestFind(UITestCase):

    dotcode = FIND

    def test_find(self):
        w = self.widget
        win = self.window
        entry = win.textentry
        apple, apricot = self.node('apple'), self.node('apricot')

        entry.set_text('ap')
        pump()
        self.assertEqual(set(w.highlight), {apple, apricot})
        self.assertEqual(win.find_count.get_label(), '2 nodes found')

        # Hovering doesn't change the search highlight
        banana = self.node('banana')
        self.set_view(banana.x, banana.y, 1.0)
        motion(w, *window_center(w))
        self.assertEqual(set(w.highlight), {apple, apricot})

        entry.activate()
        wait_animation(w)
        self.assertAlmostEqual(w.x, apple.x)
        self.assertAlmostEqual(w.y, apple.y)
        self.assertTrue(win.find_next_toolitem.get_sensitive())

        win.actiongroup.get_action('FindNext').activate()
        wait_animation(w)
        self.assertAlmostEqual(w.x, apricot.x)
        self.assertAlmostEqual(w.y, apricot.y)
        self.assertFalse(win.find_next_toolitem.get_sensitive())

        entry.set_text('')
        pump()
        self.assertIsNone(w.highlight)
        self.assertEqual(win.find_count.get_label(), '')

    def test_find_no_match(self):
        entry = self.window.textentry
        entry.set_text('cherry')
        pump()
        self.assertEqual(self.widget.highlight, [])
        self.assertEqual(self.window.find_count.get_label(), '')
        entry.activate()
        pump()
        self.assertEqual(self.widget.history_back, [])


if __name__ == '__main__':
    unittest.main()

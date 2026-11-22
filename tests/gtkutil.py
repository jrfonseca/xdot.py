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

"""Helpers for driving GTK from tests: main loop pumping and synthetic GDK
events, injected through Gtk.main_do_event so that the regular GTK signal
dispatch takes place."""


import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gdk
from gi.repository import Gtk

from xdot.ui import animation


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

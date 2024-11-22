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
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import Gdk, Gtk
from xdot.ui.elements import Jump


class DragAction(object):

    def __init__(self, dot_widget):
        self.dot_widget = dot_widget

    def on_button_press(self, event):
        self.startmousex = self.prevmousex = event.x
        self.startmousey = self.prevmousey = event.y
        self.start()

    def on_motion_notify(self, event):
        if event.is_hint:
            window, x, y, state = event.window.get_device_position(event.device)
        else:
            x, y, state = event.x, event.y, event.state
        deltax = self.prevmousex - x
        deltay = self.prevmousey - y
        self.drag(deltax, deltay)
        self.prevmousex = x
        self.prevmousey = y

    def on_button_release(self, event):
        self.stopmousex = event.x
        self.stopmousey = event.y
        self.stop()

    def draw(self, cr):
        pass

    def start(self):
        pass

    def drag(self, deltax, deltay):
        pass

    def stop(self):
        pass

    def abort(self):
        pass


class NullAction(DragAction):

    # FIXME: The NullAction class is probably not the best place to hold this
    # sort mutable global state.
    _tooltip_window = Gtk.Window.new(type=Gtk.WindowType.POPUP)
    _tooltip_label = Gtk.Label(xalign=0, yalign=0)
    _tooltip_item = None

    _tooltip_window.add(_tooltip_label)
    _tooltip_label.show()

    def on_motion_notify(self, event):
        if event.is_hint:
            window, x, y, state = event.window.get_device_position(event.device)
        else:
            x, y, state = event.x, event.y, event.state
        dot_widget = self.dot_widget
        item = dot_widget.get_url(x, y)
        if item is None:
            item = dot_widget.get_jump(x, y)
        if item is not None:
            NullAction._tooltip_window.set_transient_for(dot_widget.get_toplevel())
            dot_widget.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))
            dot_widget.set_highlight(item.highlight)
            if item is not NullAction._tooltip_item:
                # TODO: Should fold this into a method.
                if isinstance(item, Jump) and item.item.tooltip is not None:
                    NullAction._tooltip_label.set_markup(item.item.tooltip)
                    NullAction._tooltip_window.resize(
                      NullAction._tooltip_label.get_preferred_width().natural_width,
                      NullAction._tooltip_label.get_preferred_height().natural_height
                    )
                    NullAction._tooltip_window.show()
                else:
                    NullAction._tooltip_window.hide()
                    NullAction._tooltip_label.set_markup("")
                NullAction._tooltip_item = item
            if NullAction._tooltip_window.is_visible:
                pointer = NullAction._tooltip_window.get_screen().get_root_window().get_pointer()
                NullAction._tooltip_window.move(pointer.x + 15, pointer.y + 10)
        else:
            dot_widget.get_window().set_cursor(None)
            dot_widget.set_highlight(None)
            NullAction._tooltip_window.hide()
            NullAction._tooltip_label.set_markup("")
            NullAction._tooltip_item = None


class PanAction(DragAction):

    def start(self):
        self.dot_widget.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.FLEUR))

    def drag(self, deltax, deltay):
        self.dot_widget.x += deltax / self.dot_widget.zoom_ratio
        self.dot_widget.y += deltay / self.dot_widget.zoom_ratio
        self.dot_widget.queue_draw()

    def stop(self):
        self.dot_widget.get_window().set_cursor(None)

    abort = stop


class ZoomAction(DragAction):

    def drag(self, deltax, deltay):
        self.dot_widget.zoom_ratio *= 1.005 ** (deltax + deltay)
        self.dot_widget.zoom_to_fit_on_resize = False
        self.dot_widget.queue_draw()

    def stop(self):
        self.dot_widget.queue_draw()


class ZoomAreaAction(DragAction):

    def drag(self, deltax, deltay):
        self.dot_widget.queue_draw()

    def draw(self, cr):
        cr.save()
        cr.set_source_rgba(.5, .5, 1.0, 0.25)
        cr.rectangle(self.startmousex, self.startmousey,
                     self.prevmousex - self.startmousex,
                     self.prevmousey - self.startmousey)
        cr.fill()
        cr.set_source_rgba(.5, .5, 1.0, 1.0)
        cr.set_line_width(1)
        cr.rectangle(self.startmousex - .5, self.startmousey - .5,
                     self.prevmousex - self.startmousex + 1,
                     self.prevmousey - self.startmousey + 1)
        cr.stroke()
        cr.restore()

    def stop(self):
        x1, y1 = self.dot_widget.window2graph(self.startmousex,
                                              self.startmousey)
        x2, y2 = self.dot_widget.window2graph(self.stopmousex,
                                              self.stopmousey)
        self.dot_widget.zoom_to_area(x1, y1, x2, y2)

    def abort(self):
        self.dot_widget.queue_draw()

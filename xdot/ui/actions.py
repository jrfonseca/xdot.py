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

from collections.abc import Iterable

class DragAction:

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

class TooltipContext():
    _tooltip_window: Gtk.Window = None
    _tooltip_box: Gtk.Box = None
    _widgets: dict[str, Gtk.Widget] = {}

    tooltip_text = None

    @staticmethod
    def initialize():
        if TooltipContext._tooltip_window is not None:
            return
        TooltipContext._tooltip_window = Gtk.Window.new(type=Gtk.WindowType.POPUP)
        TooltipContext._tooltip_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        TooltipContext._tooltip_window.add(TooltipContext._tooltip_box)
        TooltipContext._tooltip_window.hide()

        TooltipContext._widgets["tooltip_label"] = Gtk.Label()
        TooltipContext._tooltip_box.add(TooltipContext._widgets["tooltip_label"])

    @staticmethod
    def reset():
        """Reset the tooltip to it's native state"""
        TooltipContext.initialize()
        def _hide_widget(w):
            w.hide()
            if isinstance(w, Iterable):
                for c in w:
                    _hide_widget(c)

        # Gtk (and python bindings) don't have an explicit Gtk.Widget.hide_all()
        _hide_widget(TooltipContext._tooltip_window)

    @staticmethod
    def set_parent(parent):
        TooltipContext.initialize()
        TooltipContext._parent = parent

    @staticmethod
    def add_widget(name, widget):
        TooltipContext.initialize()
        TooltipContext._widgets[name] = widget
        TooltipContext._tooltip_box.add(TooltipContext._widgets[name])

    @staticmethod
    def remove_widget(name):
        TooltipContext.initialize()
        widget = TooltipContext._widgets.pop(name)
        TooltipContext._tooltip_box.remove(widget)

    @staticmethod
    def get_widget(name):
        TooltipContext.initialize()
        return TooltipContext._widgets[name]

    @staticmethod
    def activate():
        TooltipContext.initialize()
        TooltipContext._tooltip_window.resize(
            TooltipContext._tooltip_box.get_preferred_width().natural_width or 1,
            TooltipContext._tooltip_box.get_preferred_height().natural_height or 1
        )
        TooltipContext._tooltip_window.set_transient_for(TooltipContext._parent.get_toplevel())
        TooltipContext._tooltip_box.show()
        TooltipContext._tooltip_window.show()

        display = TooltipContext._tooltip_window.get_display()
        _, x, y = display.get_default_seat().get_pointer().get_position()
        TooltipContext._tooltip_window.move(x + 15, y + 10)

class NullAction(DragAction):
    def on_motion_notify(self, event):
        if event.is_hint:
            window, x, y, state = event.window.get_device_position(event.device)
        else:
            x, y, state = event.x, event.y, event.state
        dot_widget = self.dot_widget

        item = dot_widget.get_url(x, y) or dot_widget.get_jump(x, y)

        TooltipContext.reset()
        TooltipContext.set_parent(dot_widget)
        if item is not None:
            dot_widget.get_window().set_cursor(
                Gdk.Cursor.new_for_display(dot_widget.get_display(), Gdk.CursorType.HAND2))
            dot_widget.set_highlight(item.highlight)

            dot_widget.on_hover(dot_widget.get_element(x, y), event, TooltipContext)
        else:
            dot_widget.get_window().set_cursor(None)
            dot_widget.set_highlight(None)


class PanAction(DragAction):

    def start(self):
        self.dot_widget.get_window().set_cursor(
            Gdk.Cursor.new_for_display(self.dot_widget.get_display(), Gdk.CursorType.FLEUR))

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

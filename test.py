#!/usr/bin/env python3
#
# Copyright 2015 Jose Fonseca
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


import sys
import os.path
import traceback

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk
from gi.repository import Gdk

from xdot import DotWidget, DotWindow


class TestDotWidget(DotWidget):

    def __init__(self, name):
        DotWidget.__init__(self)
        self.name = name

    def on_draw(self, widget, cr):
        DotWidget.on_draw(self, widget, cr)

        if True:
            # Cairo screenshot

            import cairo

            # Scale to give 96 dpi instead of 72 dpi
            dpi = 96.0
            scale = dpi/72.0
            w = int(self.graph.width*scale)
            h = int(self.graph.height*scale)

            CAIRO_XMAX = 32767
            CAIRO_YMAX = 32767
            if w >= CAIRO_XMAX:
                w = CAIRO_XMAX
                scale = w/self.graph.width
                h = int(self.graph.height*scale)
            if h >= CAIRO_YMAX:
                h = CAIRO_YMAX
                scale = h/self.graph.height
                w = int(self.graph.width*scale)

            assert w <= CAIRO_XMAX
            assert h <= CAIRO_YMAX

            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)

            cr = cairo.Context(surface)

            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.paint()

            cr.scale(scale, scale)

            self.graph.draw(cr, highlight_items=self.highlight)

            surface.write_to_png(self.name + '.png')

        if False:
            # GTK 3 screenshot

            window = self.get_window()

            w = window.get_width()
            h = window.get_height()

            pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, w, h)

            pixbuf.savev(self.name + '.png', 'png', (), ())

        Gtk.main_quit()

    def error_dialog(self, message):
        sys.stderr.write(message)
        sys.stderr.write("\n")


def main():
    for arg in sys.argv[1:]:
        sys.stdout.write(arg + '\n')
        sys.stdout.flush()
        name, ext = os.path.splitext(os.path.basename(arg))
        dotcode = open(arg, 'rb').read()
        widget = TestDotWidget(name)
        window = DotWindow(widget)
        window.connect('delete-event', Gtk.main_quit)
        try:
            window.set_dotcode(dotcode)
        except:
            exc_info = sys.exc_info()
            traceback.print_exception(*exc_info)
            continue
        try:
            window.show()
            Gtk.main()
        finally:
            window.destroy()


if __name__ == '__main__':
    main()

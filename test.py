#!/usr/bin/env python3
#
# Copyright 2015-2016 Jose Fonseca
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
import multiprocessing


# GLib/GTK warnings and criticals logged during the current test.
log_errors = []


def init_worker():
    """Treat GLib/GTK warnings and criticals as test failures.

    GTK uses structured logging, so GLib.log_set_handler doesn't see its
    messages, but a log writer function does.  The writer can only be set
    once per process, hence it's done here and not in test()."""

    from gi.repository import GLib

    fatal_levels = GLib.LogLevelFlags.LEVEL_ERROR | \
                   GLib.LogLevelFlags.LEVEL_CRITICAL | \
                   GLib.LogLevelFlags.LEVEL_WARNING

    # Warnings caused by the environment rather than by xdot.  Namely, the
    # Ubuntu 22.04 GitHub runners lack some of the stock icons used in the
    # toolbar.
    ignored_messages = [
        'Error loading theme icon ',
    ]

    def log_writer(log_level, fields, n_fields, user_data):
        if log_level & fatal_levels:
            message = GLib.log_writer_format_fields(log_level, fields, False)
            if not any(ignored in message for ignored in ignored_messages):
                log_errors.append(log_level)
        return GLib.log_writer_default(log_level, fields, user_data)

    GLib.log_set_writer_func(log_writer, None)


def test(arg):
    sys.stdout.write(arg + '\n')
    sys.stdout.flush()


    import gi
    gi.require_version('Gtk', '3.0')

    from gi.repository import Gtk
    from gi.repository import Gdk

    from xdot.ui import DotWidget, DotWindow
    from xdot.ui.actions import TooltipContext

    del log_errors[:]


    class TestDotWidget(DotWidget):

        def __init__(self, filename):
            DotWidget.__init__(self)

            self.dirname, basename = os.path.split(filename)

            name, ext = os.path.splitext(basename)
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

                surface.write_to_png(os.path.join(self.dirname, self.name + '.png'))

            # Exercise the tooltip code path for every element with a tooltip
            TooltipContext.set_parent(self)
            for element in self.graph.nodes + self.graph.edges:
                if element.tooltip is not None:
                    TooltipContext.reset()
                    self.on_hover(element, None, TooltipContext)
            TooltipContext.reset()

            if False:
                # GTK 3 screenshot

                window = self.get_window()

                w = window.get_width()
                h = window.get_height()

                pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, w, h)

                pixbuf.savev(os.path.join(self.dirname, self.name + '.png'), 'png', (), ())

            Gtk.main_quit()

        def error_dialog(self, message):
            sys.stderr.write(message)
            sys.stderr.write("\n")


    result = True

    widget = TestDotWidget(arg)
    window = DotWindow(widget)
    window.connect('delete-event', Gtk.main_quit)
    try:
        try:
            dotcode = open(arg, 'rb').read()
            window.set_dotcode(dotcode)
        except:
            exc_info = sys.exc_info()
            traceback.print_exception(*exc_info)
            result = False
        else:
            window.show()
            Gtk.main()
    finally:
        window.destroy()

    if log_errors:
        sys.stderr.write('%s: %u GLib warning(s)/error(s)\n' % (arg, len(log_errors)))
        result = False

    return result


def main():
    args = sys.argv[1:]

    pool = multiprocessing.Pool(multiprocessing.cpu_count(), init_worker)
    results = pool.map(test, args)

    # Let workers exit cleanly, otherwise the pool finalizer terminates them
    # and coverage loses their data.
    pool.close()
    pool.join()

    # Exit with status 1 if any failed
    try:
        results.index(False)
    except ValueError:
        status = 0
    else:
        status = 1
    sys.exit(status)


if __name__ == '__main__':
    main()

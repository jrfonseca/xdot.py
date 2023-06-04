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

import math
import os
import re
import subprocess
import sys
import time
import operator

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

# See http://www.graphviz.org/pub/scm/graphviz-cairo/plugin/cairo/gvrender_cairo.c

# For pygtk inspiration and guidance see:
# - http://mirageiv.berlios.de/
# - http://comix.sourceforge.net/

from . import actions
from ..dot.lexer import ParseError
from ._xdotparser import XDotParser
from . import animation
from . import actions
from .elements import Graph


class DotWidget(Gtk.DrawingArea):
    """GTK widget that draws dot graphs."""

    # TODO GTK3: Second argument has to be of type Gdk.EventButton instead of object.
    __gsignals__ = {
        'clicked': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'error': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'history': (GObject.SignalFlags.RUN_LAST, None, (bool, bool))
    }

    filter = 'dot'
    graphviz_version = None

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self.graph = Graph()
        self.openfilename = None

        self.set_can_focus(True)

        self.connect("draw", self.on_draw)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-press-event", self.on_area_button_press)
        self.connect("button-release-event", self.on_area_button_release)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.SCROLL_MASK |
                        Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("motion-notify-event", self.on_area_motion_notify)
        self.connect("scroll-event", self.on_area_scroll_event)
        self.connect("size-allocate", self.on_area_size_allocate)

        self.connect('key-press-event', self.on_key_press_event)
        self.last_mtime = None

        GLib.timeout_add(1000, self.update)

        self.x, self.y = 0.0, 0.0
        self.zoom_ratio = 1.0
        self.zoom_to_fit_on_resize = False
        self.animation = animation.NoAnimation(self)
        self.drag_action = actions.NullAction(self)
        self.presstime = None
        self.highlight = None
        self.highlight_search = False
        self.history_back = []
        self.history_forward = []

    def error_dialog(self, message):
        self.emit('error', message)

    def set_filter(self, filter):
        self.filter = filter
        self.graphviz_version = None

    def run_filter(self, dotcode):
        if not self.filter:
            return dotcode
        try:
            p = subprocess.Popen(
                [self.filter, '-Txdot'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                universal_newlines=False
            )
        except OSError as exc:
            error = '%s: %s' % (self.filter, exc.strerror)
            p = subprocess.CalledProcessError(exc.errno, self.filter, exc.strerror)
        else:
            xdotcode, error = p.communicate(dotcode)
            error = error.decode()
        error = error.rstrip()
        if error:
            sys.stderr.write(error + '\n')
        if p.returncode != 0:
            self.error_dialog(error)
        return xdotcode

    def _set_dotcode(self, dotcode, filename=None, center=True):
        # By default DOT language is UTF-8, but it accepts other encodings
        assert isinstance(dotcode, bytes)
        xdotcode = self.run_filter(dotcode)
            
        if xdotcode is None:
            return False
        try:
            self.set_xdotcode(xdotcode, center=center)
        except ParseError as ex:
            self.error_dialog(str(ex))
            return False
        else:
            return True

    def set_dotcode(self, dotcode, filename=None, center=True):
        self.openfilename = None
        if self._set_dotcode(dotcode, filename, center=center):
            if filename is None:
                self.last_mtime = None
            else:
                self.last_mtime = os.stat(filename).st_mtime
            self.openfilename = filename
            return True

    def set_xdotcode(self, xdotcode, center=True):
        assert isinstance(xdotcode, bytes)

        if self.graphviz_version is None:
            stdout = subprocess.check_output([self.filter, '-V'], stderr=subprocess.STDOUT)
            stdout = stdout.rstrip()
            mo = re.match(br'^.* - .* version (?P<version>.*) \(.*\)$', stdout)
            assert mo
            self.graphviz_version = mo.group('version').decode('ascii')

        parser = XDotParser(xdotcode, graphviz_version=self.graphviz_version)
        self.graph = parser.parse()
        self.zoom_image(self.zoom_ratio, center=center)

    def reload(self):
        if self.openfilename is not None:
            try:
                fp = open(self.openfilename, 'rb')
                self._set_dotcode(fp.read(), self.openfilename, center=False)
                fp.close()
            except IOError:
                pass
            else:
                del self.history_back[:], self.history_forward[:]

    def update(self):
        if self.openfilename is not None:
            try:
                current_mtime = os.stat(self.openfilename).st_mtime
            except OSError:
                return True
            if current_mtime != self.last_mtime:
                self.last_mtime = current_mtime
                self.reload()
        return True

    def _draw_graph(self, cr, rect):
        w, h = float(rect.width), float(rect.height)
        cx, cy = 0.5 * w, 0.5 * h
        x, y, ratio = self.x, self.y, self.zoom_ratio
        x0, y0 = x - cx / ratio, y - cy / ratio
        x1, y1 = x0 + w / ratio, y0 + h / ratio
        bounding = (x0, y0, x1, y1)

        cr.translate(cx, cy)
        cr.scale(ratio, ratio)
        cr.translate(-x, -y)
        self.graph.draw(cr, highlight_items=self.highlight, bounding=bounding)

    def on_draw(self, widget, cr):
        rect = self.get_allocation()
        Gtk.render_background(self.get_style_context(), cr, 0, 0,
                              rect.width, rect.height)

        cr.save()
        self._draw_graph(cr, rect)
        cr.restore()

        self.drag_action.draw(cr)

        return False

    def get_current_pos(self):
        return self.x, self.y

    def set_current_pos(self, x, y):
        self.x = x
        self.y = y
        self.queue_draw()

    def set_highlight(self, items, search=False):
        # Enable or disable search highlight
        if search:
            self.highlight_search = items is not None
        # Ignore cursor highlight while searching
        if self.highlight_search and not search:
            return
        if self.highlight != items:
            self.highlight = items
            self.queue_draw()

    def zoom_image(self, zoom_ratio, center=False, pos=None):
        # Constrain zoom ratio to a sane range to prevent numeric instability.
        zoom_ratio = min(zoom_ratio, 1E4)
        zoom_ratio = max(zoom_ratio, 1E-6)

        if center:
            self.x = self.graph.width/2
            self.y = self.graph.height/2
        elif pos is not None:
            rect = self.get_allocation()
            x, y = pos
            x -= 0.5*rect.width
            y -= 0.5*rect.height
            self.x += x / self.zoom_ratio - x / zoom_ratio
            self.y += y / self.zoom_ratio - y / zoom_ratio
        self.zoom_ratio = zoom_ratio
        self.zoom_to_fit_on_resize = False
        self.queue_draw()

    def zoom_to_area(self, x1, y1, x2, y2):
        rect = self.get_allocation()
        width = abs(x1 - x2)
        height = abs(y1 - y2)
        if width == 0 and height == 0:
            self.zoom_ratio *= self.ZOOM_INCREMENT
        else:
            self.zoom_ratio = min(
                float(rect.width)/float(width),
                float(rect.height)/float(height)
            )
        self.zoom_to_fit_on_resize = False
        self.x = (x1 + x2) / 2
        self.y = (y1 + y2) / 2
        self.queue_draw()

    def zoom_to_fit(self):
        rect = self.get_allocation()
        rect.x += self.ZOOM_TO_FIT_MARGIN
        rect.y += self.ZOOM_TO_FIT_MARGIN
        rect.width -= 2 * self.ZOOM_TO_FIT_MARGIN
        rect.height -= 2 * self.ZOOM_TO_FIT_MARGIN
        zoom_ratio = min(
            float(rect.width)/float(self.graph.width),
            float(rect.height)/float(self.graph.height)
        )
        self.zoom_image(zoom_ratio, center=True)
        self.zoom_to_fit_on_resize = True

    ZOOM_INCREMENT = 1.25
    ZOOM_TO_FIT_MARGIN = 12

    def on_zoom_in(self, action):
        self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)

    def on_zoom_out(self, action):
        self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)

    def on_zoom_fit(self, action):
        self.zoom_to_fit()

    def on_zoom_100(self, action):
        self.zoom_image(1.0)

    POS_INCREMENT = 100

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Left:
            self.x -= self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Right:
            self.x += self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Up:
            self.y -= self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Down:
            self.y += self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval in (Gdk.KEY_Page_Up,
                            Gdk.KEY_plus,
                            Gdk.KEY_equal,
                            Gdk.KEY_KP_Add):
            self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)
            self.queue_draw()
            return True
        if event.keyval in (Gdk.KEY_Page_Down,
                            Gdk.KEY_minus,
                            Gdk.KEY_KP_Subtract):
            self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Escape:
            self.drag_action.abort()
            self.drag_action = actions.NullAction(self)
            return True
        if event.keyval == Gdk.KEY_r:
            self.reload()
            return True
        if event.keyval == Gdk.KEY_f:
            win = widget.get_toplevel()
            find_toolitem = win.uimanager.get_widget('/ToolBar/Find')
            textentry = find_toolitem.get_children()
            win.set_focus(textentry[0])
            return True
        if event.keyval == Gdk.KEY_q:
            Gtk.main_quit()
            return True
        if event.keyval == Gdk.KEY_p:
            self.on_print()
            return True
        if event.keyval == Gdk.KEY_t:
            # toggle toolbar visibility
            win = widget.get_toplevel()
            toolbar = win.uimanager.get_widget("/ToolBar")
            toolbar.set_visible(not toolbar.get_visible())
            return True
        if event.keyval == Gdk.KEY_w:
            self.zoom_to_fit()
            return True
        return False

    print_settings = None

    def on_print(self, action=None):
        print_op = Gtk.PrintOperation()

        if self.print_settings is not None:
            print_op.set_print_settings(self.print_settings)

        print_op.connect("begin_print", self.begin_print)
        print_op.connect("draw_page", self.draw_page)

        res = print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self.get_toplevel())
        if res == Gtk.PrintOperationResult.APPLY:
            self.print_settings = print_op.get_print_settings()

    def begin_print(self, operation, context):
        operation.set_n_pages(1)
        return True

    def draw_page(self, operation, context, page_nr):
        cr = context.get_cairo_context()
        rect = self.get_allocation()
        self._draw_graph(cr, rect)

    def get_drag_action(self, event):
        state = event.state
        if event.button in (1, 2):  # left or middle button
            modifiers = Gtk.accelerator_get_default_mod_mask()
            if state & modifiers == Gdk.ModifierType.CONTROL_MASK:
                return actions.ZoomAction
            elif state & modifiers == Gdk.ModifierType.SHIFT_MASK:
                return actions.ZoomAreaAction
            else:
                return actions.PanAction
        return actions.NullAction

    def on_area_button_press(self, area, event):
        self.animation.stop()
        self.drag_action.abort()
        action_type = self.get_drag_action(event)
        self.drag_action = action_type(self)
        self.drag_action.on_button_press(event)
        self.presstime = time.time()
        self.pressx = event.x
        self.pressy = event.y
        return False

    def is_click(self, event, click_fuzz=4, click_timeout=1.0):
        assert event.type == Gdk.EventType.BUTTON_RELEASE
        if self.presstime is None:
            # got a button release without seeing the press?
            return False
        # XXX instead of doing this complicated logic, shouldn't we listen
        # for gtk's clicked event instead?
        deltax = self.pressx - event.x
        deltay = self.pressy - event.y
        return (time.time() < self.presstime + click_timeout and
                math.hypot(deltax, deltay) < click_fuzz)

    def on_click(self, element, event):
        """Override this method in subclass to process
        click events. Note that element can be None
        (click on empty space)."""
        return False

    def on_area_button_release(self, area, event):
        self.drag_action.on_button_release(event)
        self.drag_action = actions.NullAction(self)
        x, y = int(event.x), int(event.y)
        if self.is_click(event):
            el = self.get_element(x, y)
            if self.on_click(el, event):
                return True

            if event.button == 1:
                url = self.get_url(x, y)
                if url is not None:
                    self.emit('clicked', url.url, event)
                else:
                    jump = self.get_jump(x, y)
                    if jump is not None:
                        self.animate_to(jump.x, jump.y)

                return True

        if event.button == 1 or event.button == 2:
            return True
        return False

    def on_area_scroll_event(self, area, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT,
                            pos=(event.x, event.y))
            return True
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT,
                            pos=(event.x, event.y))
        else:
            deltas = event.get_scroll_deltas()
            self.zoom_image(self.zoom_ratio * (1 - deltas.delta_y / 10),
                            pos=(event.x, event.y))
            return True
        return False

    def on_area_motion_notify(self, area, event):
        self.drag_action.on_motion_notify(event)
        return True

    def on_area_size_allocate(self, area, allocation):
        if self.zoom_to_fit_on_resize:
            self.zoom_to_fit()

    def animate_to(self, x, y):
        del self.history_forward[:]
        self.history_back.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(x, y)

    def _animate_to(self, x, y):
        self.animation = animation.ZoomToAnimation(self, x, y)
        self.animation.start()

    def history_changed(self):
        self.emit(
            'history',
            bool(self.history_back),
            bool(self.history_forward))

    def on_go_back(self, action=None):
        try:
            item = self.history_back.pop()
        except LookupError:
            return
        self.history_forward.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(*item)

    def on_go_forward(self, action=None):
        try:
            item = self.history_forward.pop()
        except LookupError:
            return
        self.history_back.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(*item)

    def window2graph(self, x, y):
        rect = self.get_allocation()
        x -= 0.5*rect.width
        y -= 0.5*rect.height
        x /= self.zoom_ratio
        y /= self.zoom_ratio
        x += self.x
        y += self.y
        return x, y

    def get_element(self, x, y):
        x, y = self.window2graph(x, y)
        return self.graph.get_element(x, y)

    def get_url(self, x, y):
        x, y = self.window2graph(x, y)
        return self.graph.get_url(x, y)

    def get_jump(self, x, y):
        x, y = self.window2graph(x, y)
        return self.graph.get_jump(x, y)


class FindMenuToolAction(Gtk.Action):
    __gtype_name__ = "FindMenuToolAction"

    def do_create_tool_item(self):
        return Gtk.ToolItem()


class DotWindow(Gtk.Window):

    ui = '''
    <ui>
        <toolbar name="ToolBar">
            <toolitem action="Open"/>
            <toolitem action="Export"/>
            <toolitem action="Reload"/>
            <toolitem action="Print"/>
            <separator/>
            <toolitem action="Back"/>
            <toolitem action="Forward"/>
            <separator/>
            <toolitem action="ZoomIn"/>
            <toolitem action="ZoomOut"/>
            <toolitem action="ZoomFit"/>
            <toolitem action="Zoom100"/>
            <separator/>
            <toolitem name="Find" action="Find"/>
            <separator name="FindNextSeparator"/>
            <toolitem action="FindNext"/>
            <separator name="FindStatusSeparator"/>
            <toolitem name="FindStatus" action="FindStatus"/>
        </toolbar>
    </ui>
    '''

    base_title = 'Dot Viewer'

    def __init__(self, widget=None, width=512, height=512):
        Gtk.Window.__init__(self)

        self.graph = Graph()

        window = self

        window.set_title(self.base_title)
        window.set_default_size(width, height)
        window.set_wmclass("xdot", "xdot")
        vbox = Gtk.VBox()
        window.add(vbox)

        self.dotwidget = widget or DotWidget()
        self.dotwidget.connect("error", lambda e, m: self.error_dialog(m))
        self.dotwidget.connect("history", self.on_history)

        # Create a UIManager instance
        uimanager = self.uimanager = Gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        window.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = Gtk.ActionGroup('Actions')
        self.actiongroup = actiongroup

        # Create actions
        actiongroup.add_actions((
            ('Open', Gtk.STOCK_OPEN, None, None, "Open dot-file", self.on_open),
            ('Export', Gtk.STOCK_SAVE_AS, None, None, "Export graph to other format", self.on_export),
            ('Reload', Gtk.STOCK_REFRESH, None, None, "Reload graph", self.on_reload),
            ('Print', Gtk.STOCK_PRINT, None, None,
             "Prints the currently visible part of the graph", self.dotwidget.on_print),
            ('ZoomIn', Gtk.STOCK_ZOOM_IN, None, None, "Zoom in", self.dotwidget.on_zoom_in),
            ('ZoomOut', Gtk.STOCK_ZOOM_OUT, None, None, "Zoom out", self.dotwidget.on_zoom_out),
            ('ZoomFit', Gtk.STOCK_ZOOM_FIT, None, None, "Fit zoom", self.dotwidget.on_zoom_fit),
            ('Zoom100', Gtk.STOCK_ZOOM_100, None, None, "Reset zoom level", self.dotwidget.on_zoom_100),
            ('FindNext', Gtk.STOCK_GO_FORWARD, 'Next Result', None, 'Move to the next search result', self.on_find_next),
        ))

        self.back_action = Gtk.Action('Back', None, None, Gtk.STOCK_GO_BACK)
        self.back_action.set_sensitive(False)
        self.back_action.connect("activate", self.dotwidget.on_go_back)
        actiongroup.add_action(self.back_action)

        self.forward_action = Gtk.Action('Forward', None, None, Gtk.STOCK_GO_FORWARD)
        self.forward_action.set_sensitive(False)
        self.forward_action.connect("activate", self.dotwidget.on_go_forward)
        actiongroup.add_action(self.forward_action)

        find_action = FindMenuToolAction("Find", None,
                                         "Find a node by name", None)
        actiongroup.add_action(find_action)

        findstatus_action = FindMenuToolAction("FindStatus", None,
                                               "Number of results found", None)
        actiongroup.add_action(findstatus_action)

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI descrption
        uimanager.add_ui_from_string(self.ui)

        # Create a Toolbar
        toolbar = uimanager.get_widget('/ToolBar')
        vbox.pack_start(toolbar, False, False, 0)

        vbox.pack_start(self.dotwidget, True, True, 0)

        self.last_open_dir = "."

        self.set_focus(self.dotwidget)

        # Add Find text search
        find_toolitem = uimanager.get_widget('/ToolBar/Find')
        self.textentry = Gtk.Entry()
        self.textentry.set_icon_from_stock(0, Gtk.STOCK_FIND)
        find_toolitem.add(self.textentry)

        self.textentry.set_activates_default(True)
        self.textentry.connect("activate", self.textentry_activate, self.textentry);
        self.textentry.connect("changed", self.textentry_changed, self.textentry);

        uimanager.get_widget('/ToolBar/FindNextSeparator').set_draw(False)
        uimanager.get_widget('/ToolBar/FindStatusSeparator').set_draw(False)
        self.find_next_toolitem = uimanager.get_widget('/ToolBar/FindNext')
        self.find_next_toolitem.set_sensitive(False)

        self.find_count = Gtk.Label()
        findstatus_toolitem = uimanager.get_widget('/ToolBar/FindStatus')
        findstatus_toolitem.add(self.find_count)

        self.show_all()

    def find_text(self, entry_text):
        found_items = []
        dot_widget = self.dotwidget
        try:
            regexp = re.compile(entry_text)
        except re.error as err:
            sys.stderr.write('warning: re.compile() failed with error "%s"\n' % err)
            return []
        for element in dot_widget.graph.nodes + dot_widget.graph.edges + dot_widget.graph.shapes:
            if element.search_text(regexp):
                found_items.append(element)
        return sorted(found_items, key=operator.methodcaller('get_text'))

    def textentry_changed(self, widget, entry):
        self.find_count.set_label('')
        self.find_index = 0
        self.find_next_toolitem.set_sensitive(False)
        entry_text = entry.get_text()
        dot_widget = self.dotwidget
        if not entry_text:
            dot_widget.set_highlight(None, search=True)
            return

        found_items = self.find_text(entry_text)
        dot_widget.set_highlight(found_items, search=True)
        if found_items:
            self.find_count.set_label('%d nodes found' % len(found_items))

    def textentry_activate(self, widget, entry):
        self.find_index = 0
        self.find_next_toolitem.set_sensitive(False)
        entry_text = entry.get_text()
        dot_widget = self.dotwidget
        if not entry_text:
            dot_widget.set_highlight(None, search=True)
            self.set_focus(self.dotwidget)
            return

        found_items = self.find_text(entry_text)
        dot_widget.set_highlight(found_items, search=True)
        if found_items:
            dot_widget.animate_to(found_items[0].x, found_items[0].y)
        self.find_next_toolitem.set_sensitive(len(found_items) > 1)

    def set_filter(self, filter):
        self.dotwidget.set_filter(filter)

    def set_dotcode(self, dotcode, filename=None):
        if self.dotwidget.set_dotcode(dotcode, filename):
            self.update_title(filename)
            self.dotwidget.zoom_to_fit()

    def set_xdotcode(self, xdotcode, filename=None):
        if self.dotwidget.set_xdotcode(xdotcode):
            self.update_title(filename)
            self.dotwidget.zoom_to_fit()

    def update_title(self, filename=None):
        if filename is None:
            self.set_title(self.base_title)
        else:
            self.set_title(os.path.basename(filename) + ' - ' + self.base_title)

    def open_file(self, filename):
        try:
            fp = open(filename, 'rb')
            self.set_dotcode(fp.read(), filename)
            fp.close()
        except IOError as ex:
            self.error_dialog(str(ex))

    def on_open(self, action):
        chooser = Gtk.FileChooserDialog(parent=self,
                                        title="Open Graphviz File",
                                        action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL,
                                                 Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OPEN,
                                                 Gtk.ResponseType.OK))
        chooser.set_default_response(Gtk.ResponseType.OK)
        chooser.set_current_folder(self.last_open_dir)
        filter = Gtk.FileFilter()
        filter.set_name("Graphviz files")
        filter.add_pattern("*.gv")
        filter.add_pattern("*.dot")
        chooser.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        chooser.add_filter(filter)
        if chooser.run() == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            self.last_open_dir = chooser.get_current_folder()
            chooser.destroy()
            self.open_file(filename)
        else:
            chooser.destroy()
   
    def export_file(self, filename, format_):
        if not filename.endswith("." + format_):
            filename += '.' + format_
        cmd = [
            self.dotwidget.filter, # program name, usually "dot"
            '-T' + format_,
            '-o', filename,
            self.dotwidget.openfilename,
        ]
        subprocess.check_call(cmd)

    def on_export(self, action):
        
        if self.dotwidget.openfilename is None:
            return
        
        default_filter = "PNG image"
    
        output_formats = {
            "dot file": "dot",
            "GIF image": "gif",
            "JPG image": "jpg",
            "JSON": "json",
            "PDF": "pdf",
            "PNG image": "png",
            "PostScript": "ps",
            "SVG image": "svg",
            "XFIG image": "fig",
            "xdot file": "xdot",
        }
        buttons = (
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        chooser = Gtk.FileChooserDialog(
            parent=self,
            title="Export to other file format.",
            action=Gtk.FileChooserAction.SAVE,
            buttons=buttons) 
        chooser.set_default_response(Gtk.ResponseType.OK)
        chooser.set_current_folder(self.last_open_dir)
        
        openfilename = os.path.basename(self.dotwidget.openfilename)
        openfileroot = os.path.splitext(openfilename)[0]
        chooser.set_current_name(openfileroot)

        for name, ext in output_formats.items():
            filter_ = Gtk.FileFilter()
            filter_.set_name(name)
            filter_.add_pattern('*.' + ext)
            chooser.add_filter(filter_)
            if name == default_filter:
                chooser.set_filter(filter_)

        if chooser.run() == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            format_ = output_formats[chooser.get_filter().get_name()]
            chooser.destroy()
            self.export_file(filename, format_)
        else:
            chooser.destroy()
	

    def on_reload(self, action):
        self.dotwidget.reload()

    def error_dialog(self, message):
        dlg = Gtk.MessageDialog(parent=self,
                                type=Gtk.MessageType.ERROR,
                                message_format=message,
                                buttons=Gtk.ButtonsType.OK)
        dlg.set_title(self.base_title)
        dlg.run()
        dlg.destroy()

    def on_find_next(self, action):
        self.find_index += 1
        entry_text = self.textentry.get_text()
        # Maybe storing the search result would be better
        found_items = self.find_text(entry_text)
        found_item = found_items[self.find_index]
        self.dotwidget.animate_to(found_item.x, found_item.y)
        self.find_next_toolitem.set_sensitive(len(found_items) > self.find_index + 1)

    def on_history(self, action, has_back, has_forward):
        self.back_action.set_sensitive(has_back)
        self.forward_action.set_sensitive(has_forward)

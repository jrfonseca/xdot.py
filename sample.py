#!/usr/bin/env python3
#
# Copyright 2008 Jose Fonseca
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

from gi.repository import Gtk

import xdot.ui


class MyDotWidget(xdot.ui.DotWidget):
    from xdot.ui.actions import TooltipContext as tooltip

    def __init__(self):
        xdot.ui.DotWidget.__init__(self)
        self.prev_element = None

        self.tooltip.add_widget("tooltip_image", Gtk.Image())

    def on_hover(self, element, _):
        if self.prev_element != element:
            self.prev_element = element
            self.tooltip.reset()

            if isinstance(element, xdot.ui.elements.Node):
                image = self.tooltip.get_widget("tooltip_image")
                image.set_from_file("./image.png")
                image.show()

        return isinstance(element, xdot.ui.elements.Node)


class MyDotWindow(xdot.ui.DotWindow):
    def __init__(self):
        xdot.ui.DotWindow.__init__(self, widget=MyDotWidget())
        self.dotwidget.connect('clicked', self.on_url_clicked)

    def on_url_clicked(self, widget, url, event):
        dialog = Gtk.MessageDialog(
            parent=self,
            buttons=Gtk.ButtonsType.OK,
            message_format="%s clicked" % url)
        dialog.connect('response', lambda dialog, response: dialog.destroy())
        dialog.run()
        return True

dotcode = b"""
digraph G {
  Hello [URL="http://en.wikipedia.org/wiki/Hello", tooltip="This tooltip is overriden by custom on_hover"]
  World [URL="http://en.wikipedia.org/wiki/World"]
    Hello -> World [URL="http://en.wikipedia.org/wiki/Edge", headhref="http://en.wikipedia.org/wiki/EdgeHead", tailURL="http://en.wikipedia.org/wiki/EdgeTail", tooltip="This tooltip is visible"]
}
"""


def main():
    window = MyDotWindow()
    window.set_dotcode(dotcode)
    window.connect('delete-event', Gtk.main_quit)
    Gtk.main()


if __name__ == '__main__':
    main()


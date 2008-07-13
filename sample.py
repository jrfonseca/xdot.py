#!/usr/bin/env python
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


import gtk
import gtk.gdk

import xdot


class MyDotWindow(xdot.DotWindow):

    def __init__(self):
        xdot.DotWindow.__init__(self)
        self.widget.connect('clicked', self.on_url_clicked)

    def on_url_clicked(self, widget, url, event):
        dialog = gtk.MessageDialog(
                parent = self, 
                buttons = gtk.BUTTONS_OK,
                message_format="%s clicked" % url)
        dialog.connect('response', lambda dialog, response: dialog.destroy())
        dialog.run()
        return True


dotcode = """
digraph G {
  Hello [URL="http://en.wikipedia.org/wiki/Hello"]
  World [URL="http://en.wikipedia.org/wiki/World"]
    Hello -> World
}
"""


def main():
    window = MyDotWindow()
    window.set_dotcode(dotcode)
    window.connect('destroy', gtk.main_quit)
    gtk.main()


if __name__ == '__main__':
    main()

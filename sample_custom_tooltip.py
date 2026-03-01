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
    def __init__(self):
        xdot.ui.DotWidget.__init__(self)
        self.prev_element = None

        # Create the image widget that will later be used to display the image
        xdot.ui.actions.TooltipContext.add_widget("tooltip_image", Gtk.Image())

    # We want to show some image instead of the tooltip text if it says "show_image" for nodes
    def on_hover(self, element, action, tooltip):
        # Check if it is a node and its tooltip is "show_image"
        if isinstance(element, xdot.ui.elements.Node) and element.tooltip == "show_image":
            
            # Retreive the image widget from the tooltip window
            image = tooltip.get_widget("tooltip_image")

            # This function is run on each input change (mouse movement).
            # We ideally want to load the image only once
            if self.prev_element != element:
                self.prev_element = element
                image.set_from_file("./image.jpeg")

            # Set the image visible and activate the tooltip
            # (that moves the window to the cursor location and resizes it to fit the content)
            image.show()
            tooltip.activate()

        # Otherwise if this element is not a node or the tooltip is not "show_image",
        # call the default hover handler 
        else:
            super().on_hover(element, action, tooltip)
                

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
  Hello [tooltip="show_image"]
  World [tooltip="Some regular tooltip"]

  Hello -> World [tooltip="This tooltip is also visible"]
}
"""


def main():
    window = MyDotWindow()
    window.set_dotcode(dotcode)
    window.connect('delete-event', Gtk.main_quit)
    Gtk.main()


if __name__ == '__main__':
    main()


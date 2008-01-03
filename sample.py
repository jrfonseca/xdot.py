#!/usr/bin/env python


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

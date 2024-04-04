#!/usr/bin/env python3
#
# Copyright 2008-2017 Jose Fonseca
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

import argparse
import sys

from .ui.window import DotWindow, Gtk


def main():

    parser = argparse.ArgumentParser(
        description="xdot.py is an interactive viewer for graphs written in Graphviz's dot language.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Shortcuts:
  Up, Down, Left, Right     scroll
  PageUp, +, =              zoom in
  PageDown, -               zoom out
  R                         reload dot file
  F                         find
  Q                         quit
  P                         print
  T                         toggle show/hide toolbar
  Escape                    halt animation
  Ctrl-drag                 zoom in/out
  Shift-drag                zooms an area
  Click (on edge)           focus edge's source node
  Ctrl-click (on edge)      focus edge's *destination* node
'''
    )
    parser.add_argument(
        'inputfile', metavar='file', nargs='?',
        help='input file to be viewed')
    parser.add_argument(
        '-f', '--filter', choices=['dot', 'neato', 'twopi', 'circo', 'fdp'],
        dest='filter', default='dot', metavar='FILTER',
        help='graphviz filter: dot, neato, twopi, circo, or fdp [default: %(default)s]')
    parser.add_argument(
        '-n', '--no-filter',
        action='store_const', const=None, dest='filter',
        help='assume input is already filtered into xdot format (use e.g. dot -Txdot)')
    parser.add_argument(
        '-g', '--geometry',
        action='store', dest='geometry',
        help='default window size in form WxH')
    parser.add_argument(
        '--hide-toolbar',
        action='store_true', dest='hide_toolbar',
        help='Hides the toolbar on start.')

    options = parser.parse_args()
    inputfile = options.inputfile

    width, height = 610, 610
    if options.geometry:
        try:
            width, height = (int(i) for i in options.geometry.split('x'))
        except ValueError:
            parser.error('invalid window geometry')

    win = DotWindow(width=width, height=height)
    win.connect('delete-event', Gtk.main_quit)
    win.set_filter(options.filter)
    if inputfile and len(inputfile) >= 1:
        if inputfile == '-':
            win.set_dotcode(sys.stdin.buffer.read())
        else:
            win.open_file(inputfile)

    if options.hide_toolbar:
        win.uimanager.get_widget('/ToolBar').set_visible(False)

    if sys.platform != 'win32':
        # Reset KeyboardInterrupt SIGINT handler, so that glib loop can be stopped by it
        import signal
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    Gtk.main()

if __name__ == '__main__':
    main()

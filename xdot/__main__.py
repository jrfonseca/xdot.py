#!/usr/bin/env python3
#
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
import optparse
import sys

from .ui.window import DotWindow, Gtk


class OptionParser(optparse.OptionParser):

    def format_epilog(self, formatter):
        # Prevent stripping the newlines in epilog message
        # http://stackoverflow.com/questions/1857346/python-optparse-how-to-include-additional-info-in-usage-output
        return self.epilog


def main():

    parser = OptionParser(
        usage='\n\t%prog [file]',
        epilog='''
Shortcuts:
  Up, Down, Left, Right     scroll
  PageUp, +, =              zoom in
  PageDown, -               zoom out
  R                         reload dot file
  F                         find
  Q                         quit
  P                         print
  Escape                    halt animation
  Ctrl-drag                 zoom in/out
  Shift-drag                zooms an area
'''
    )
    parser.add_option(
        '-f', '--filter',
        type='choice', choices=('dot', 'neato', 'twopi', 'circo', 'fdp'),
        dest='filter', default='dot',
        help='graphviz filter: dot, neato, twopi, circo, or fdp [default: %default]')
    parser.add_option(
        '-n', '--no-filter',
        action='store_const', const=None, dest='filter',
        help='assume input is already filtered into xdot format (use e.g. dot -Txdot)')
    parser.add_option(
        '-g', None,
        action='store', dest='geometry',
        help='default window size in form WxH')

    (options, args) = parser.parse_args(sys.argv[1:])
    if len(args) > 1:
        parser.error('incorrect number of arguments')

    width = height = 512
    if options.geometry:
        try:
            width, height = (int(i) for i in options.geometry.split('x'))
        except ValueError:
            parser.error('invalid window geometry')

    win = DotWindow(width=width, height=height)
    win.connect('delete-event', Gtk.main_quit)
    win.set_filter(options.filter)
    if len(args) >= 1:
        if args[0] == '-':
            win.set_dotcode(sys.stdin.read())
        else:
            win.open_file(args[0])
    Gtk.main()

if __name__ == '__main__':
    main()

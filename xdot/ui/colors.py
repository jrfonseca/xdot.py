# Copyright 2008-2026 Jose Fonseca
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


def lookup_color(c):
    """Return RGBA values of the X11 color named c, e.g. "navajowhite".

    Graphviz writes all colors in xdot output as #rrggbb[aa] since 2.22, so
    this is only needed for hand-written xdot input.
    """
    import sys
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('PangoCairo', '1.0')

    from gi.repository import Gdk

    try:
        color = Gdk.color_parse(c)
    except ValueError:
        # Older PyGObject versions raise instead of returning None
        color = None
    if color is not None:
        s = 1.0/65535.0
        r = color.red*s
        g = color.green*s
        b = color.blue*s
        a = 1.0
        return r, g, b, a

    sys.stderr.write("warning: unknown color '%s'\n" % c)
    return None

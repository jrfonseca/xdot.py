#
# Copyright 2008-2022 Jose Fonseca
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

'''Visualize dot graphs via the xdot format.'''

import sys
assert sys.version_info.major >= 3

import importlib
import warnings


__all__ = ['dot', 'ui']


__author__ = "Jose Fonseca et al"


# Leverage PEP 562 to maintain backwards compatibility while still
# allowing xdot.dot to be used headlessly.
if sys.version_info >= (3, 7):
    def __getattr__(name):
        if name in ('dot', 'ui'):
            return importlib.import_module("." + name, __name__)
        if name in ('DotWidget', 'DotWindow'):
            warnings.warn(f"w xdot.{name} is deprecated, use xdot.ui.{name} instead", UserWarning, stacklevel=2)
            from . import ui
            return getattr(ui, name)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
else:
    from . import dot
    from . import ui
    from .ui import DotWidget, DotWindow

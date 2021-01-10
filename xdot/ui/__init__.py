__all__ = ['actions', 'animation', 'colors', 'elements', 'pen', 'window']

import sys

try:
    import gi
except ImportError:
    sys.stderr.write('error: PyGObject bindings for GTK3 not found (https://git.io/JLjeE)\n')
    sys.exit(1)

from .window import DotWidget, DotWindow

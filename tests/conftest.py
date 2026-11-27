#
# Copyright 2026 Jose Fonseca
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

"""Shared pytest setup for the GTK tests.

Every test fails if it logs a GLib/GTK warning, critical or error, or if an
exception is raised inside a GTK callback (which PyGObject would otherwise
only print)."""


import sys
import traceback

import pytest

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gtk  # noqa: F401 (opens the default display)

# Nothing may import xdot.ui before pytest_configure has checked for a
# display: xdot.ui.actions creates a window at import time, which aborts the
# process without one.


#
# GLib/GTK warnings are test failures
#

FATAL_LEVELS = GLib.LogLevelFlags.LEVEL_ERROR | \
               GLib.LogLevelFlags.LEVEL_CRITICAL | \
               GLib.LogLevelFlags.LEVEL_WARNING

# Warnings caused by the environment rather than by xdot.  Namely, the Ubuntu
# 22.04 GitHub runners lack some of the stock icons used in the toolbar.
IGNORED_MESSAGES = [
    'Error loading theme icon ',
]

log_errors = []


def _log_writer(log_level, fields, n_fields, user_data):
    if log_level & FATAL_LEVELS:
        message = GLib.log_writer_format_fields(log_level, fields, False)
        if not any(ignored in message for ignored in IGNORED_MESSAGES):
            log_errors.append(message)
    return GLib.log_writer_default(log_level, fields, user_data)


# GTK uses structured logging, so GLib.log_set_handler doesn't see its
# messages, but a log writer function does.  The writer can only be set once
# per process, hence it's done here, at import time.
GLib.log_set_writer_func(_log_writer, None)


def pytest_configure(config):
    if Gdk.Display.get_default() is None:
        raise pytest.UsageError(
            'no display: run under tests/headless.sh, e.g. ./test.sh')


@pytest.fixture(autouse=True)
def gtk_checks(monkeypatch):
    # PyGObject reports exceptions raised in signal handlers and virtual
    # methods through sys.excepthook, and then carries on.
    exceptions = []

    def excepthook(type_, value, tb):
        exceptions.append(''.join(traceback.format_exception(type_, value, tb)))
        sys.__excepthook__(type_, value, tb)

    monkeypatch.setattr(sys, 'excepthook', excepthook)
    del log_errors[:]

    yield

    problems = []
    if log_errors:
        problems.append('GLib/GTK warnings were logged:\n' + '\n'.join(log_errors))
    if exceptions:
        problems.append('Exceptions were raised in GTK callbacks:\n' + '\n'.join(exceptions))
    if problems:
        pytest.fail('\n\n'.join(problems), pytrace=False)


@pytest.fixture
def make_window():
    """Factory that opens a DotWindow showing `dotcode`.

    Messages that would go to the error dialog are collected in
    `window.errors` instead."""

    from xdot.ui import DotWidget, DotWindow
    from xdot.ui.actions import TooltipContext
    from tests.gtkutil import pump

    windows = []

    def make(dotcode, widget_class=DotWidget, size=(640, 480)):
        widget = widget_class()
        width, height = size
        window = DotWindow(widget, width=width, height=height)
        windows.append(window)
        window.errors = []
        # DotWindow.error_dialog runs a modal dialog
        window.error_dialog = window.errors.append
        window.set_dotcode(dotcode)
        window.show_all()
        pump(lambda: widget.get_allocated_width() > 1 and
             widget.get_window() is not None and
             widget.get_window().is_viewable())
        pump()
        return window

    yield make

    TooltipContext.reset()
    for window in windows:
        window.destroy()
    pump()


#
# Graph inputs for test_graphs.py
#

def pytest_addoption(parser):
    parser.addoption('--graphs', nargs='+', metavar='PATH',
                     help='graphs for test_graphs.py to test, instead of the '
                          'ones in tests/')

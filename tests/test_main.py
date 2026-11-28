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

"""Tests for the command line (xdot/__main__.py).

main() runs in-process with Gtk.main stubbed out, so it returns as soon as
the window is set up."""


import io
import signal
import subprocess
import sys

import pytest

from tests.gtkutil import pump


GRAPH = b'digraph { a -> b }'


@pytest.fixture
def run_main(monkeypatch):
    import xdot.__main__
    from xdot.ui import DotWindow
    from xdot.ui.window import Gtk

    windows = []

    class RecordingWindow(DotWindow):

        def __init__(self, *args, **kwargs):
            self.errors = []
            DotWindow.__init__(self, *args, **kwargs)
            windows.append(self)

        def error_dialog(self, message):
            self.errors.append(message)

    monkeypatch.setattr(xdot.__main__, 'DotWindow', RecordingWindow)
    monkeypatch.setattr(Gtk, 'main', lambda: None)
    # Keep pytest's KeyboardInterrupt handler
    monkeypatch.setattr(signal, 'signal', lambda signum, handler: None)

    def run(*args):
        monkeypatch.setattr(sys, 'argv', ['xdot'] + list(args))
        xdot.__main__.main()
        pump()
        win, = windows
        assert win.errors == []
        return win

    yield run

    for win in windows:
        win.destroy()
    pump()


@pytest.fixture
def dot_file(tmp_path):
    path = tmp_path / 'g.dot'
    path.write_bytes(GRAPH)
    return path


def test_no_file(run_main):
    win = run_main()
    assert win.dotwidget.filter == 'dot'
    assert win.get_title() == 'Dot Viewer'
    assert win.get_default_size() == (610, 610)
    assert win.toolbar.get_visible()


def test_file(run_main, dot_file):
    win = run_main(str(dot_file))
    assert win.get_title() == 'g.dot - Dot Viewer'
    assert win.dotwidget.openfilename == str(dot_file)
    assert len(win.dotwidget.graph.nodes) == 2


def test_stdin(run_main, monkeypatch):
    stdin = io.TextIOWrapper(io.BytesIO(GRAPH))
    monkeypatch.setattr(sys, 'stdin', stdin)
    win = run_main('-')
    assert win.dotwidget.openfilename is None
    assert len(win.dotwidget.graph.nodes) == 2


def test_no_filter(run_main, tmp_path):
    path = tmp_path / 'g.xdot'
    path.write_bytes(subprocess.check_output(['dot', '-Txdot'], input=GRAPH))
    win = run_main('-n', str(path))
    assert win.dotwidget.filter is None
    assert len(win.dotwidget.graph.nodes) == 2


def test_filter(run_main, dot_file):
    win = run_main('-f', 'neato', str(dot_file))
    assert win.dotwidget.filter == 'neato'
    assert len(win.dotwidget.graph.nodes) == 2


def test_geometry(run_main):
    win = run_main('-g', '300x200')
    assert win.get_default_size() == (300, 200)


@pytest.mark.parametrize('args', [
    ['-g', 'bogus'],
    ['-f', 'nosuchfilter'],
])
def test_bad_arguments(run_main, args, capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_main(*args)
    assert excinfo.value.code == 2
    assert 'error:' in capsys.readouterr().err


def test_hide_toolbar(run_main):
    win = run_main('--hide-toolbar')
    assert not win.toolbar.get_visible()

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
import os
import re

from .scanner import DotScanner

EOF = -1
SKIP = -2

ID = 0
STR_ID = 1
HTML_ID = 2


class Token:

    def __init__(self, type, text, line, col):
        self.type = type
        self.text = text
        self.line = line
        self.col = col


class ParseError(Exception):

    def __init__(self, msg=None, filename=None, line=None, col=None):
        self.msg = msg
        self.filename = filename
        self.line = line
        self.col = col

    def __str__(self):
        return ':'.join([str(part) for part in
                         (self.filename, self.line, self.col, self.msg)
                         if part is not None])


class Lexer:

    # should be overriden by derived classes
    scanner = None
    tabsize = 8

    newline_re = re.compile(br'\r\n?|\n')

    def __init__(self, buf=None, pos=0, filename=None, fp=None):
        if fp is not None:
            try:
                fileno = fp.fileno()
                length = os.path.getsize(fp.name)
                import mmap
            except:
                # read whole file into memory
                buf = fp.read()
                pos = 0
            else:
                # map the whole file into memory
                if length:
                    # length must not be zero
                    buf = mmap.mmap(fileno, length, access=mmap.ACCESS_READ)
                    pos = os.lseek(fileno, 0, 1)
                else:
                    buf = b''
                    pos = 0

            if filename is None:
                try:
                    filename = fp.name
                except AttributeError:
                    filename = None

        self.buf = buf
        self.pos = pos
        self.line = 1
        self.col = 1
        self.filename = filename

    def __next__(self):
        while True:
            # save state
            pos = self.pos
            line = self.line
            col = self.col

            type, text, endpos = self.scanner.next(self.buf, pos)
            assert isinstance(text, bytes)
            assert pos + len(text) == endpos
            self.consume(text)
            type, text = self.filter(type, text)
            self.pos = endpos

            if type == SKIP:
                continue
            elif type is None:
                msg = 'unexpected char %r' % (text,)
                raise ParseError(msg, self.filename, line, col)
            else:
                break
        return Token(type=type, text=text, line=line, col=col)

    def consume(self, text):
        # update line number
        pos = 0
        for mo in self.newline_re.finditer(text, pos):
            self.line += 1
            self.col = 1
            pos = mo.end()

        # update column number
        while True:
            tabpos = text.find(b'\t', pos)
            if tabpos == -1:
                break
            self.col += tabpos - pos
            self.col = ((self.col - 1) // self.tabsize + 1) * self.tabsize + 1
            pos = tabpos + 1
        self.col += len(text) - pos


class DotLexer(Lexer):

    scanner = DotScanner()

    def filter(self, type, text):
        # TODO: handle charset
        if type == STR_ID:
            text = text[1:-1]

            # line continuations
            text = text.replace(b'\\\r\n', b'')
            text = text.replace(b'\\\r', b'')
            text = text.replace(b'\\\n', b'')

            # quotes
            text = text.replace(b'\\"', b'"')

            # layout engines recognize other escape codes (many non-standard)
            # but we don't translate them here

            type = ID

        elif type == HTML_ID:
            text = text[1:-1]
            type = ID

        return type, text

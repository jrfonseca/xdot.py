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
import re

EOF = -1
SKIP = -2

ID = 0
STR_ID = 1
HTML_ID = 2
EDGE_OP = 3

LSQUARE = 4
RSQUARE = 5
LCURLY = 6
RCURLY = 7
COMMA = 8
COLON = 9
SEMI = 10
EQUAL = 11
PLUS = 12

STRICT = 13
GRAPH = 14
DIGRAPH = 15
NODE = 16
EDGE = 17
SUBGRAPH = 18


class Scanner:
    """Stateless scanner."""

    # should be overriden by derived classes
    tokens = []
    symbols = {}
    literals = {}
    ignorecase = False

    def __init__(self):
        flags = re.DOTALL
        if self.ignorecase:
            flags |= re.IGNORECASE
        self.tokens_re = re.compile(
            b'|'.join([b'(' + regexp + b')'
                       for type, regexp, test_lit in self.tokens]),
            flags
        )

    def next(self, buf, pos):
        if pos >= len(buf):
            return EOF, b'', pos
        mo = self.tokens_re.match(buf, pos)
        if mo:
            text = mo.group()
            type, regexp, test_lit = self.tokens[mo.lastindex - 1]
            pos = mo.end()
            if test_lit:
                type = self.literals.get(text, type)
            return type, text, pos
        else:
            c = buf[pos:pos+1]
            return self.symbols.get(c, None), c, pos + 1


class DotScanner(Scanner):

    # token regular expression table
    tokens = [
        # whitespace and comments
        (SKIP,
         br'[ \t\f\r\n\v]+|'
         br'//[^\r\n]*|'
         br'/\*.*?\*/|'
         br'#[^\r\n]*',
         False),

        # Alphanumeric IDs
        (ID, br'[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*', True),

        # Numeric IDs
        (ID, br'-?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)', False),

        # String IDs
        (STR_ID, br'"[^"\\]*(?:\\.[^"\\]*)*"', False),

        # HTML IDs
        (HTML_ID, br'<[^<>]*(?:<[^<>]*>[^<>]*)*>', False),

        # Edge operators
        (EDGE_OP, br'-[>-]', False),
    ]

    # symbol table
    symbols = {
        b'[': LSQUARE,
        b']': RSQUARE,
        b'{': LCURLY,
        b'}': RCURLY,
        b',': COMMA,
        b':': COLON,
        b';': SEMI,
        b'=': EQUAL,
        b'+': PLUS,
    }

    # literal table
    literals = {
        b'strict': STRICT,
        b'graph': GRAPH,
        b'digraph': DIGRAPH,
        b'node': NODE,
        b'edge': EDGE,
        b'subgraph': SUBGRAPH,
    }

    ignorecase = True

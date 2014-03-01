#!/usr/bin/env python
#
# The purpose of this script is to enable uploading xdot.py to the Python
# Package Index, which can be easily done by doing:
#
#   python setup.py register
#   python setup.py sdist upload
#
# See also:
# - https://code.google.com/p/jrfonseca/issues/detail?id=19
# - http://docs.python.org/2/distutils/packageindex.html
#

from setuptools import setup

setup(
    name='xdot',
    version='0.6',
    author='Jose Fonseca',
    author_email='jose.r.fonseca@gmail.com',
    url='http://code.google.com/p/jrfonseca/wiki/XDot',
    description="Interactive viewer for Graphviz dot files",
    long_description="""
        xdot.py is an interactive viewer for graphs written in Graphviz's dot
        language.

        It uses internally the graphviz's xdot output format as an intermediate
        format, and PyGTK and Cairo for rendering.

        xdot.py can be used either as a standalone application from command
        line, or as a library embedded in your python application.
        """,
    license="LGPL",

    py_modules=['xdot'],
    entry_points=dict(gui_scripts=['xdot=xdot:main']),

    # This is true, but pointless, because easy_install PyGTK chokes and dies
    #install_requires=['PyGTK', 'pycairo'],
)

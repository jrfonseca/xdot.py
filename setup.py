#!/usr/bin/env python3
#
# The purpose of this script is to enable uploading xdot.py to the Python
# Package Index, which can be easily done by doing:
#
#   python3 setup.py sdist upload
#
# See also:
# - https://packaging.python.org/distributing/
# - https://docs.python.org/3/distutils/packageindex.html
#

from setuptools import setup

setup(
    name='xdot',
    version='1.3',
    author='Jose Fonseca',
    author_email='jose.r.fonseca@gmail.com',
    url='https://github.com/jrfonseca/xdot.py',
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

    packages=['xdot', 'xdot/dot', 'xdot/ui'],
    entry_points=dict(gui_scripts=['xdot=xdot.__main__:main']),

    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 6 - Mature',

        'Environment :: X11 Applications :: GTK',

        'Intended Audience :: Information Technology',

        'Operating System :: OS Independent',

        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: Multimedia :: Graphics :: Viewers',
    ],

    install_requires=[
        'PyGObject',
        'numpy'
    ],
)

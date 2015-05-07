About _xdot.py_
=================

_xdot.py_ is an interactive viewer for graphs written in [Graphviz](http://www.graphviz.org/)'s [dot language](http://www.graphviz.org/doc/info/lang.html).

It uses internally the graphviz's [xdot output format](http://www.graphviz.org/doc/info/output.html#d:xdot) as an intermediate format, and [PyGTK](http://www.pygtk.org/) and [Cairo](http://cairographics.org/) for rendering.

_xdot.py_ can be used either as a standalone application from command line, or as a library embedded in your python application.

Status
======

_xdot.py_ script became much more popular than I ever anticipated, and there are several interested in improving it further. However, for several years now, _xdot.py_ already meets my own needs, and unfortunately I don't have much time for maintain it myself.

So I'm looking into transition _xdot.py_ maitenance to [others](https://github.com/jrfonseca/xdot.py/wiki/Forks): either hand over the maintenance _xdot.py_ to a community or indicate an official fork of _xdot.py_.

I encourage people interested in development of _xdot.py_ to fork the [GitHub repository](https://github.com/jrfonseca/xdot.py), and join the new [mailing list](https://groups.google.com/d/forum/xdot-py).

Features
========

 * Since it doesn't use bitmaps it is fast and has a small memory footprint.
 * Arbitrary zoom.
 * Keyboard/mouse navigation.
 * Supports events on the nodes with URLs.
 * Animated jumping between nodes.
 * Highlights node/edge under mouse.

Known Issues
============

 * Not all xdot attributes are supported or correctly rendered yet. It works well for my applications but YMMV.

 * Text doesn't scale properly to large sizes if font hinting is enabled. I haven't find a reliable way to disable font hinting during rendering yet.

See also:

  * [github issue tracker](https://github.com/jrfonseca/xdot.py/issues)

  * [googlecode issue tracker](https://code.google.com/p/jrfonseca/issues/list?q=xdot).

Screenshots
===========

[![Profile 1 Screenshot](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-profile1_small.png)](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-profile1.png)
[![Profile 2 Screenshot](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-profile2_small.png)](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-profile2.png)
[![Control Flow Graph](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-cfg_small.png)](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-cfg.png)

Requirements
============

 * [Python](http://www.python.org/download/) (2.6 or 2.7)

 * [PyGTK](http://www.pygtk.org/downloads.html) (2.10 or greater)

 * [Graphviz](http://www.graphviz.org/Download.php)

Windows users
-------------

Download and install:

 * [Python for Windows](http://www.python.org/download/)

 * [GTK+ Runtime for Windows](http://www.gtk.org/download/win32.php)

 * [PyCairo, PyGobject, and PyGTK for Windows](http://www.pygtk.org/downloads.html)

 * [Graphviz for Windows](http://www.graphviz.org/Download_windows.php)

Debian/Ubuntu users
-------------------

Run:

    apt-get install python-gtk2 graphviz

Usage
=====

Command Line
------------

    Usage: 
    	xdot.py [file]
    
    Options:
      -h, --help            show this help message and exit
      -f FILTER, --filter=FILTER
                            graphviz filter: dot, neato, twopi, circo, or fdp
                            [default: dot]
      -n, --no-filter       assume input is already filtered into xdot format (use
                            e.g. dot -Txdot)
    
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
      F2                        prev highlighted item
      F3                        next highlighted item
      ,                         select prev focused node's edge
      .                         select next focused node's edge
      p,j                       prev file
      n,k                       next file
      o                         browse file
      Enter                     follow selected edge
      Ctrl-click                display shortest path (retargetable)
      Ctrl-shift-click          display reverse shortest path (retargetable)
      right click               dot url open ([URL="dots://file1;file2;..."]) (Linux only)

If no input file is given then it will read the dot graph from the standard input.

Embedding
---------

See included `sample.py` script for an example of how to embedded _xdot.py_ into another application.

[![Screenshot](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-sample_small.png)](https://raw.github.com/wiki/jrfonseca/xdot.py/xdot-sample.png)

Download
========

  * https://pypi.python.org/pypi/xdot

  * https://github.com/jrfonseca/xdot.py

Links
=====

 * [Graphviz homepage](http://www.graphviz.org/)

 * [ZGRViewer](http://zvtm.sourceforge.net/zgrviewer.html) -- another superb graphviz/dot viewer

 * [dot2tex](http://code.google.com/p/dot2tex/) -- python script to convert xdot output from Graphviz to a series of PSTricks or PGF/TikZ commands.

 * The [pypy project](http://codespeak.net/pypy/) also includes an [interactive dot viewer based on graphviz's plain format and the pygame library](http://morepypy.blogspot.com/2008/01/visualizing-python-tokenizer.html).

#!/bin/sh
set -ex
LANG=C exec xvfb-run -a -s '-screen 0 1024x768x24' sh -ec '
/usr/bin/python3 test.py tests/*.dot tests/graphs/*.gv
/usr/bin/python3 -W ignore::DeprecationWarning -m unittest -v tests.test_ui
'

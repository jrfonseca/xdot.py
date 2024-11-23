#!/bin/sh
set -ex
LANG=C exec xvfb-run -a -s '-screen 0 1024x768x24' /usr/bin/python3 test.py tests/*.dot tests/graphs/*.gv

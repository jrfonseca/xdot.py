#!/bin/sh
set -ex
cd tests
LANG=C exec xvfb-run -a -s '-screen 0 1024x768x24' /usr/bin/python3 ../test.py *.dot graphs/*.gv

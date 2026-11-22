#!/bin/sh
set -eux
rm -f .coverage .coverage.*
LANG=C xvfb-run -a -s '-screen 0 1024x768x24' python3 -m coverage run test.py tests/*.dot tests/graphs/*.gv
LANG=C xvfb-run -a -s '-screen 0 1024x768x24' python3 -W ignore::DeprecationWarning -m coverage run -m unittest -v tests.test_ui
python3 -m coverage combine
if [ -t 0 -a -t 1 -a -t 2 ]
then
	python3 -m coverage html
	xdg-open htmlcov/index.html
else
	python3 -m coverage report
fi

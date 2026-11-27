#!/bin/sh
# Coverage report for the test suite.  Needs pytest-cov:
#
#   apt install python3-pytest-cov
#
set -eux
rm -f .coverage .coverage.*
if [ -t 0 -a -t 1 -a -t 2 ]
then
	report=html
else
	report=term
fi
LANG=C tests/headless.sh python3 -m pytest -n auto --cov --cov-report=$report "$@"
if [ $report = html ]
then
	xdg-open htmlcov/index.html
fi

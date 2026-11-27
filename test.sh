#!/bin/sh
set -ex
LANG=C exec tests/headless.sh /usr/bin/python3 -m pytest -n auto "$@"

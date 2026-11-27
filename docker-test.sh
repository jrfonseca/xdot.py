#!/bin/sh
#
# Run the test suite inside an Ubuntu container, reproducing a CI job from
# .github/workflows/build.yml.
#
# Usage: ./docker-test.sh [-r RELEASE] [pytest args...]
#
# RELEASE defaults to 26.04 and selects the ubuntu-XX_YY job, whose apt package
# list is used to build the image (tagged xdot-test:ubuntu-RELEASE, and rebuilt
# only when the package list changes). The working tree is mounted into the
# container and the tests run as the calling user, so files written there (the
# tests/*.png renders) are not owned by root.
#

set -e

release=26.04
if [ "$1" = "-r" ]
then
    release=$2
    shift 2
fi

CDPATH= cd "$(dirname "$0")"

job="ubuntu-$(echo "$release" | tr . _)"

# Take the apt package list from the job's apt-install step
packages=$(awk -v job="  $job:" '
    $0 == job { injob = 1; next }
    injob && /^  [^ ]/ { exit }
    injob && /apt-get install/ { sub(/.*--no-install-recommends /, ""); print; exit }
' .github/workflows/build.yml)
if [ -z "$packages" ]
then
    echo "error: no apt-get install step for job $job in .github/workflows/build.yml" >&2
    exit 1
fi

image="xdot-test:ubuntu-$release"

# xauth is needed by xwfb-run and xvfb-run, and is preinstalled on GitHub runners
docker build -q -t "$image" - >/dev/null <<EOF
FROM ubuntu:$release
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && \
    apt-get install -qq -y --no-install-recommends $packages xauth && \
    rm -rf /var/lib/apt/lists/*
EOF

if [ -t 0 ] && [ -t 1 ]
then
    tty=-t
else
    tty=
fi

# --init: xvfb-run hangs waiting for Xvfb's ready signal when it is PID 1, and
# xwfb-run kills its process group on exit
exec docker run --rm -i $tty --init \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$PWD:/src" \
    -w /src \
    "$image" \
    ./test.sh -p no:cacheprovider "$@"

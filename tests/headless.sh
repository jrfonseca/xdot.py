#!/bin/sh
#
# Run a command on a headless X server.
#
# Usage: tests/headless.sh COMMAND [ARGS...]
#
# Uses xwfb-run (Xwayland on a headless Weston, from the xwayland-run package,
# https://gitlab.freedesktop.org/ofourdan/xwayland-run) when available, and
# falls back to xvfb-run otherwise (Ubuntu 22.04 has no xwayland-run).
#

set -e

if command -v xwfb-run >/dev/null
then
    # xwfb-run exports WAYLAND_DISPLAY too, so GTK would pick its Wayland
    # backend; the tests need X11.
    export GDK_BACKEND=${GDK_BACKEND:-x11}
    # xwfb-run sends the command's stderr to its error file (/dev/null by
    # default) together with the compositor's log, so fold it into stdout.
    # Xwayland picks a free display number by itself.
    exec xwfb-run -c weston -s \\-geometry -s 1024x768 -- \
        sh -c 'exec "$@" 2>&1' sh "$@"
else
    exec xvfb-run -a -s '-screen 0 1024x768x24' "$@"
fi

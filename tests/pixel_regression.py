#!/usr/bin/env python3
#
# Copyright 2026 Jose Fonseca
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Rendering regression check: base commit vs code under test.

Renders the same input graphs with two versions of xdot, in the same
environment, and compares the images pixel by pixel.  Nothing is stored in
git; see docs/rendering-tests.md for the rationale.

Typical use, from the repository root:

    tests/pixel_regression.py run                 # merge-base with origin/main vs working tree
    tests/pixel_regression.py run --base 1.5      # any commit-ish
    tests/pixel_regression.py run --base HEAD~3 --head HEAD tests/issue_94.dot

The base (and --head, if given) is checked out into a detached git worktree
under build/pixel/worktrees/.  Renders of commits are cached under
build/pixel/renders/.  The report goes to build/pixel/report/index.html.

The `render` and `compare` subcommands are the building blocks `run` uses.
"""


import argparse
import glob
import hashlib
import html
import json
import multiprocessing
import os
import shutil
import subprocess
import sys


SCRIPT = os.path.abspath(__file__)
REPO = os.path.dirname(os.path.dirname(SCRIPT))
BUILD = os.path.join(REPO, 'build', 'pixel')

DEFAULT_INPUTS = ['tests/*.dot', 'tests/*.gv', 'tests/graphs/*.gv']

# Bump when the rendering below changes, to invalidate cached renders.
RENDER_VERSION = 1


def output_name(path):
    """PNG file name for an input path, unique across directories."""
    return path.replace(os.sep, '__') + '.png'


def dot_version():
    try:
        out = subprocess.run(['dot', '-V'], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return 'unknown (%s)' % exc
    return out.stdout.decode(errors='replace').strip()


#
# render
#

def render_one(job):
    """Render one graph to PNG.  Runs in a worker process.

    Only uses DotWidget.set_dotcode and Graph.draw, which have been stable
    for years, so that it works with old commits too.  The drawing mirrors
    tests/test_graphs.py, but deliberately doesn't import it."""

    path, out_path = job

    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk  # noqa: F401
    import cairo
    from xdot.ui import DotWidget

    errors = []

    widget = DotWidget()
    widget.connect('error', lambda w, message: errors.append(message))
    try:
        with open(path, 'rb') as fp:
            dotcode = fp.read()
        if not widget.set_dotcode(dotcode):
            return path, False, '\n'.join(errors) or 'set_dotcode failed'

        graph = widget.graph

        # Scale to give 96 dpi instead of 72 dpi
        dpi = 96.0
        scale = dpi/72.0
        w = int(graph.width*scale)
        h = int(graph.height*scale)

        CAIRO_XMAX = 32767
        CAIRO_YMAX = 32767
        if w >= CAIRO_XMAX:
            w = CAIRO_XMAX
            scale = w/graph.width
            h = int(graph.height*scale)
        if h >= CAIRO_YMAX:
            h = CAIRO_YMAX
            scale = h/graph.height
            w = int(graph.width*scale)
        w = max(w, 1)
        h = max(h, 1)

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        cr.paint()
        cr.scale(scale, scale)
        graph.draw(cr, highlight_items=None)
        surface.write_to_png(out_path)
    except Exception as exc:
        return path, False, '%s: %s' % (type(exc).__name__, exc)
    finally:
        widget.destroy()

    return path, True, None


def cmd_render(args):
    import xdot

    os.makedirs(args.out, exist_ok=True)

    jobs = [(path, os.path.join(args.out, output_name(path)))
            for path in args.files]

    results = {}
    with multiprocessing.Pool(args.jobs or None) as pool:
        for path, ok, error in pool.imap_unordered(render_one, jobs):
            name = output_name(path)
            results[path] = {'png': name, 'ok': ok, 'error': error}
            if not ok:
                sys.stderr.write('%s: render failed: %s\n' % (path, error))

    manifest = {
        'render_version': RENDER_VERSION,
        'xdot': os.path.dirname(os.path.abspath(xdot.__file__)),
        'commit': args.commit,
        'dot': dot_version(),
        'inputs': inputs_digest(args.files),
        'results': results,
    }
    with open(os.path.join(args.out, 'manifest.json'), 'w') as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)

    failed = sum(not r['ok'] for r in results.values())
    sys.stdout.write('rendered %u graphs (%u failed) with %s\n' % (
        len(results), failed, manifest['xdot']))
    return 0


#
# compare
#

def load_png(path):
    """Return a (height, width, 4) uint8 array of the image's pixels."""
    import cairo
    import numpy

    surface = cairo.ImageSurface.create_from_png(path)
    w, h, stride = surface.get_width(), surface.get_height(), surface.get_stride()
    data = numpy.frombuffer(surface.get_data(), dtype=numpy.uint8)
    return data.reshape(h, stride)[:, :w*4].reshape(h, w, 4).copy()


def save_png(path, pixels):
    import cairo
    import numpy

    h, w, _ = pixels.shape
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    stride = surface.get_stride()
    buf = numpy.ndarray((h, stride), dtype=numpy.uint8,
                        buffer=surface.get_data())
    buf[:, :w*4] = pixels.reshape(h, w*4)
    surface.mark_dirty()
    surface.write_to_png(path)


def diff_image(base, mask):
    """Changed pixels in red over a faded copy of the base image."""
    import numpy

    out = (base.astype(numpy.uint16) // 4 + 191).astype(numpy.uint8)
    # Cairo's ARGB32 is BGRA in memory on little-endian machines
    red = numpy.array([0, 0, 255, 255], dtype=numpy.uint8)
    if sys.byteorder == 'big':
        red = red[::-1]
    out[mask] = red
    return out


def compare_images(base_path, head_path, threshold):
    """Return (number of differing pixels, mask or None, reason)."""
    import numpy

    base = load_png(base_path)
    head = load_png(head_path)
    if base.shape != head.shape:
        return -1, None, 'size %ux%u -> %ux%u' % (
            base.shape[1], base.shape[0], head.shape[1], head.shape[0])
    delta = numpy.abs(base.astype(numpy.int16) - head.astype(numpy.int16))
    mask = delta.max(axis=2) > threshold
    return int(mask.sum()), mask, None


def load_manifest(directory):
    with open(os.path.join(directory, 'manifest.json')) as fp:
        return json.load(fp)


def cmd_compare(args):
    base = load_manifest(args.base)
    head = load_manifest(args.head)

    report = args.report
    if os.path.isdir(report):
        shutil.rmtree(report)
    os.makedirs(os.path.join(report, 'images'))

    changed = []     # (path, description, base png, head png, diff png)
    notes = []       # (path, description)
    identical = 0

    paths = sorted(set(base['results']) | set(head['results']))
    for path in paths:
        b = base['results'].get(path)
        h = head['results'].get(path)
        if b is None or h is None:
            notes.append((path, 'only rendered by %s' % ('head' if b is None else 'base')))
            continue
        if not b['ok'] or not h['ok']:
            if b['ok'] != h['ok']:
                side, result = ('base', b) if not b['ok'] else ('head', h)
                notes.append((path, 'failed in %s: %s' % (side, result['error'])))
            else:
                notes.append((path, 'failed in both: %s' % h['error']))
            continue

        base_png = os.path.join(args.base, b['png'])
        head_png = os.path.join(args.head, h['png'])
        count, mask, reason = compare_images(base_png, head_png, args.threshold)
        if count == -1 or count > args.max_pixels:
            name = b['png'][:-len('.png')]
            rb = os.path.join('images', name + '.base.png')
            rh = os.path.join('images', name + '.head.png')
            shutil.copyfile(base_png, os.path.join(report, rb))
            shutil.copyfile(head_png, os.path.join(report, rh))
            rd = None
            if mask is not None:
                rd = os.path.join('images', name + '.diff.png')
                save_png(os.path.join(report, rd),
                         diff_image(load_png(base_png), mask))
                total = mask.size
                reason = '%u pixels differ (%.3f%%)' % (count, 100.0 * count / total)
            changed.append((path, reason, rb, rh, rd))
        else:
            identical += 1

    write_html(report, base, head, changed, notes, identical, args)

    for path, reason, _, _, _ in changed:
        sys.stdout.write('CHANGED  %s: %s\n' % (path, reason))
    for path, note in notes:
        sys.stdout.write('NOTE     %s: %s\n' % (path, note))
    sys.stdout.write('%u identical, %u changed, %u notes\n' % (
        identical, len(changed), len(notes)))
    sys.stdout.write('report: %s\n' % os.path.join(os.path.abspath(report), 'index.html'))

    return 1 if changed else 0


def write_html(report, base, head, changed, notes, identical, args):
    e = html.escape

    def side(manifest):
        return '%s<br><small>%s<br>%s</small>' % (
            e(manifest['commit'] or '?'), e(manifest['xdot']), e(manifest['dot']))

    rows = []
    for path, reason, rb, rh, rd in changed:
        diff = '<a href="%s"><img src="%s"></a>' % (e(rd), e(rd)) if rd else '(no diff)'
        rows.append(
            '<tr><th colspan="3">%s &mdash; %s</th></tr>\n'
            '<tr><td><a href="%s"><img src="%s"></a></td>'
            '<td><a href="%s"><img src="%s"></a></td><td>%s</td></tr>\n' % (
                e(path), e(reason), e(rb), e(rb), e(rh), e(rh), diff))

    note_items = ''.join('<li><code>%s</code>: %s</li>\n' % (e(p), e(n))
                         for p, n in notes)

    with open(os.path.join(report, 'index.html'), 'w') as fp:
        fp.write('''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>xdot rendering comparison</title>
<style>
body { font-family: sans-serif; margin: 1em; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 4px; vertical-align: top; text-align: left; }
td img { max-width: 30vw; max-height: 60vh; }
</style></head><body>
<h1>xdot rendering comparison</h1>
<table>
<tr><th>Base</th><td>%s</td></tr>
<tr><th>Head</th><td>%s</td></tr>
<tr><th>Tolerance</th><td>channel delta &gt; %u, more than %u pixels</td></tr>
<tr><th>Result</th><td>%u identical, %u changed, %u notes</td></tr>
</table>
<h2>Changed</h2>
%s
<h2>Notes</h2>
<ul>%s</ul>
</body></html>
''' % (side(base), side(head), args.threshold, args.max_pixels,
       identical, len(changed), len(notes),
       ('<table>\n<tr><th>Base</th><th>Head</th><th>Diff</th></tr>\n%s</table>' % ''.join(rows))
       if rows else '<p>None.</p>',
       note_items or '<li>None.</li>'))


#
# run
#

def git(*args, cwd=REPO):
    out = subprocess.run(['git'] + list(args), cwd=cwd, check=True,
                         stdout=subprocess.PIPE)
    return out.stdout.decode().strip()


def inputs_digest(files):
    """Digest of the input file names and contents."""
    md5 = hashlib.md5()
    for path in sorted(files):
        md5.update(path.encode() + b'\0')
        with open(path, 'rb') as fp:
            md5.update(hashlib.md5(fp.read()).digest())
    return md5.hexdigest()


def worktree(sha):
    path = os.path.join(BUILD, 'worktrees', sha)
    if not os.path.isdir(os.path.join(path, 'xdot')):
        if os.path.exists(path):
            shutil.rmtree(path)
        subprocess.run(['git', 'worktree', 'prune'], cwd=REPO, check=True)
        sys.stdout.write('creating worktree %s\n' % path)
        subprocess.run(['git', 'worktree', 'add', '--quiet', '--detach', path, sha],
                       cwd=REPO, check=True)
    return path


def render_tree(tree, out, files, commit, jobs, cache):
    """Render `files` with the xdot in `tree` into `out`, reusing a previous
    render when possible."""

    if cache and os.path.exists(os.path.join(out, 'manifest.json')):
        manifest = load_manifest(out)
        if manifest.get('render_version') == RENDER_VERSION and \
           manifest.get('inputs') == inputs_digest(files) and \
           manifest.get('dot') == dot_version() and \
           manifest.get('commit') == commit:
            sys.stdout.write('reusing render of %s in %s\n' % (commit, out))
            return
    if os.path.isdir(out):
        shutil.rmtree(out)

    env = dict(os.environ)
    env['PYTHONPATH'] = tree
    cmd = [sys.executable, SCRIPT, 'render', '--out', out, '--commit', commit]
    if jobs:
        cmd += ['--jobs', str(jobs)]
    cmd += files
    # Input paths, like shapefile= inside the graphs, are relative to the
    # repository root.
    subprocess.run(cmd, cwd=REPO, env=env, check=True)

    expected = os.path.realpath(os.path.join(tree, 'xdot'))
    actual = os.path.realpath(load_manifest(out)['xdot'])
    if actual != expected:
        raise SystemExit('error: rendered with %s instead of %s' % (actual, expected))


def default_base():
    for ref in ('origin/main', 'main'):
        try:
            return git('merge-base', 'HEAD', ref)
        except subprocess.CalledProcessError:
            pass
    raise SystemExit('error: no origin/main or main; pass --base')


def cmd_run(args):
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY') and \
       not os.environ.get('PIXEL_REGRESSION_HEADLESS'):
        if shutil.which('xwfb-run') is None and shutil.which('xvfb-run') is None:
            raise SystemExit('error: no display and no xwfb-run or xvfb-run')
        env = dict(os.environ, PIXEL_REGRESSION_HEADLESS='1')
        cmd = [os.path.join(REPO, 'tests', 'headless.sh'),
               sys.executable, SCRIPT] + sys.argv[1:]
        return subprocess.run(cmd, env=env).returncode

    os.chdir(REPO)

    files = args.files
    if not files:
        files = sorted(set(f for pattern in DEFAULT_INPUTS for f in glob.glob(pattern)))
    files = [os.path.relpath(os.path.abspath(f), REPO) for f in files]
    if not files:
        raise SystemExit('error: no input graphs')

    # Cached renders are keyed by commit and input set
    key = inputs_digest(files)[:12]

    base_sha = git('rev-parse', '--verify', (args.base or default_base()) + '^{commit}')
    base_dir = os.path.join(BUILD, 'renders', '%s-%s' % (base_sha, key))
    render_tree(worktree(base_sha), base_dir, files, base_sha, args.jobs,
                cache=not args.no_cache)

    if args.head:
        head_sha = git('rev-parse', '--verify', args.head + '^{commit}')
        head_dir = os.path.join(BUILD, 'renders', '%s-%s' % (head_sha, key))
        render_tree(worktree(head_sha), head_dir, files, head_sha, args.jobs,
                    cache=not args.no_cache)
    else:
        head_sha = git('rev-parse', 'HEAD')
        dirty = git('status', '--porcelain', '--untracked-files=no', '--', 'xdot')
        label = 'working tree (%s%s)' % (head_sha[:12], ', modified' if dirty else '')
        head_dir = os.path.join(BUILD, 'renders', 'worktree')
        render_tree(REPO, head_dir, files, label, args.jobs, cache=False)

    compare_args = argparse.Namespace(
        base=base_dir, head=head_dir, report=args.report,
        threshold=args.threshold, max_pixels=args.max_pixels)
    return cmd_compare(compare_args)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    def tolerance(p):
        p.add_argument('--threshold', type=int, default=0,
                       help='per-channel difference (0-255) below which a pixel '
                            'counts as equal (default: %(default)s)')
        p.add_argument('--max-pixels', type=int, default=0,
                       help='number of differing pixels allowed per image '
                            '(default: %(default)s)')

    p = sub.add_parser('run', help='render base and head, then compare')
    p.add_argument('--base', help='reference commit-ish '
                                  '(default: merge-base of HEAD and origin/main)')
    p.add_argument('--head', help='commit-ish to test (default: the working tree)')
    p.add_argument('--report', default=os.path.join(BUILD, 'report'),
                   help='report directory (default: %(default)s)')
    p.add_argument('--jobs', '-j', type=int, help='parallel render processes')
    p.add_argument('--no-cache', action='store_true',
                   help='re-render commits even if a cached render exists')
    tolerance(p)
    p.add_argument('files', nargs='*',
                   help='input graphs (default: %s)' % ' '.join(DEFAULT_INPUTS))
    p.set_defaults(func=cmd_run)

    p = sub.add_parser('render', help='render graphs with the xdot on PYTHONPATH')
    p.add_argument('--out', required=True)
    p.add_argument('--commit', default=None, help='label stored in the manifest')
    p.add_argument('--jobs', '-j', type=int)
    p.add_argument('files', nargs='+')
    p.set_defaults(func=cmd_render)

    p = sub.add_parser('compare', help='compare two render directories')
    p.add_argument('base')
    p.add_argument('head')
    p.add_argument('--report', default=os.path.join(BUILD, 'report'))
    tolerance(p)
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    # Keep our messages in order with those of child processes.
    sys.stdout.reconfigure(line_buffering=True)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())

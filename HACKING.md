# Testing

Tests use pytest (`apt install python3-pytest python3-pytest-xdist`) and need a
display.  Headless, as CI runs them:

    ./test.sh

which runs `python3 -m pytest -n auto` under `xvfb-run`, and passes any extra
arguments to pytest.  Inside a Docker container that reproduces a CI job (the
Ubuntu 26.04 one by default; the apt packages are read from
`.github/workflows/build.yml`):

    ./docker-test.sh
    ./docker-test.sh -r 22.04 tests/test_ui.py::test_pan

With a display:

    python3 -m pytest -n auto
    python3 -m pytest tests/test_graphs.py -k issue_94
    python3 -m pytest tests/test_ui.py::test_pan
    python3 -m pytest tests/test_graphs.py --graphs path/to/foo.dot

Coverage report (in `htmlcov/`; needs `apt install python3-pytest-cov`):

    ./test-cov.sh

# Rendering regressions

Compare the rendering of the test graphs between a reference commit and your
working tree:

    tests/pixel_regression.py run                  # against the merge-base with origin/main
    tests/pixel_regression.py run --base 1.6       # against any commit-ish
    tests/pixel_regression.py run --base HEAD~1 --head HEAD tests/issue_94.dot

It exits with status 1 if any image changed, and writes a side-by-side report
to `build/pixel/report/index.html`.  It runs under `xvfb-run` automatically
when there is no display.  Pull requests run the same check in CI; label the PR
`rendering-change` when a change is intended.

Reference commits are checked out as git worktrees under `build/pixel/`.  To
clean up:

    rm -rf build/pixel && git worktree prune

See `docs/rendering-tests.md` for the design.

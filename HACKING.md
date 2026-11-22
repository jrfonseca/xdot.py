# Testing

    ./test.py tests/*.dot
    ./test.py tests/graphs/*.gv

or simply

    .github/scripts/test.sh

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

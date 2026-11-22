# Rendering regression tests

Design notes. They record which approaches were considered and why the current one was chosen, so later work doesn't have to start over.

## Problem

`test.py` renders every test graph to a PNG, but only checks that loading and rendering don't raise exceptions or log GLib/GTK warnings. The PNGs are ignored by git (`tests/.gitignore`), so nothing catches a change in what is drawn.

Committing the PNGs as references isn't attractive as is:

- The 213 test graphs (`tests/*.dot`, `tests/graphs/*.gv`) produce about 28.6 MB of PNGs at 96 dpi. 24 images over 2000px make up 18 MB; `tests/graphs/xx.png` is 30669×896.
- Each regeneration adds the changed files to git history. A Graphviz upgrade changes the layout, and therefore the image, of nearly every graph.
- The pixels depend on Graphviz (layout), Cairo, pixman and FreeType (rasterization), Pango and the installed fonts (text). These differ between distributions and change with updates, so the CI runners (Ubuntu 22.04, 24.04 and 26.04) would each need their own references.

## Chosen approach: base vs head, same job

`tests/pixel_regression.py run` renders the same input graphs with two versions of xdot, in the same environment, and compares them pixel by pixel:

- **Base:** any commit-ish. Defaults to the merge-base of `HEAD` and `origin/main`. It is checked out into a detached git worktree under `build/pixel/worktrees/`.
- **Head:** the working tree, uncommitted changes included, or any commit-ish given with `--head`.
- **Rendering:** both renders use the same input files (from the current tree), the same Graphviz and the same libraries and fonts. Any difference therefore comes from xdot. Rendering goes through `DotWidget.set_dotcode()` and `Graph.draw()` only. Those have been stable for years, so the script can render old releases as well.
- **Tolerance:** `--threshold` sets the per-channel difference that is still treated as equal, and `--max-pixels` how many pixels may differ per image. Both default to 0, since the two renders share one environment.
- **Report:** `build/pixel/report/index.html` shows base, head and a diff image for every changed graph. The diff image shows changed pixels in red over a faded base image.
- **Failures:** graphs that fail to render on one or both sides are listed as notes and don't fail the run. A PR that adds a new test graph therefore doesn't break the base render.
- **Caching:** renders of commits are cached in `build/pixel/renders/<sha>-<inputs digest>/` and reused while the inputs and `dot -V` stay the same.

In CI, `.github/workflows/pixels.yml` runs this for every PR against `github.event.pull_request.base.sha` and uploads the report as an artifact. A PR that changes rendering on purpose gets the `rendering-change` label. The check then passes, and reviewers can look at the report.

Why this approach:

- Nothing is stored, so there's no repository growth and no references to regenerate.
- No Docker image or package pinning is needed. Both renders run on the same machine at the same moment, so they always use the same environment.
- It is easy to run locally against any commit, which helps when bisecting.

Trade-offs:

- It detects changes but doesn't judge them. A person has to look at the report and decide whether a change was intended.
- It can't detect slow drift across many PRs that were each accepted. It also can't detect breakage caused by the environment, such as a Cairo or Graphviz update, because both sides change together. Pinned, committed references (below) would cover that.
- Rendering takes twice as long. That is about 15 seconds for all 213 graphs on a workstation, or less when the base render is cached.

## Ideas considered

### 1. Generate references in a separate scheduled workflow and download them in the test workflow

- **Feasible?** Yes. The test job can fetch the latest successful artifact with `gh run download` or `actions/download-artifact` given a run id and a token.
- **Precedents:** visual-testing services such as Percy, Chromatic and reg-suit keep baselines outside git. Each baseline is tied to a specific commit, and a person approves every change to it.
- **What could go wrong:**
  - **Regressions become the baseline silently.** A rendering bug merged on Monday is in Sunday's references, and nobody ever looked at it.
  - **Intended changes break every open PR** until the next regeneration.
  - **Artifacts expire.** Retention is at most 90 days for public repos, and gaps in the schedule leave nothing to download.
  - **Old commits can't be tested** against the references they were written for.
- **Verdict:** rejected as written. Rendering the base in the same job (the chosen approach) keeps the advantage of not committing references, without the staleness.

### 2. Have xdot draw onto an SVG surface and store SVG references

- **Feasible?** Easily. `Graph.draw(cr)` accepts any Cairo context, so `cairo.SVGSurface` works without changing xdot. Images embedded through GdkPixbuf come out as base64 PNG.
- **Advantages:** small text files that are readable in `git diff`. They check the layer xdot owns, its Cairo drawing calls, rather than Cairo's rasterizer. The SVG backend writes no timestamps.
- **Precedents:**
  - Graphviz's own regression tests compare text output.
  - Matplotlib's test suite produces SVGs, but it converts them to PNG with Inkscape and compares pixels instead of comparing text.
- **What could go wrong:**
  - **Brittle across Cairo versions.** Cairo's SVG backend was largely rewritten in 1.17/1.18. Number formatting, ids and glyph handling change between versions.
  - **Text is still font-dependent.** Glyphs are written as outline symbols at positions computed by Pango.
  - **No tolerance.** Text either matches or it doesn't, so a harmless floating-point change fails the test.
- **Verdict:** not pursued. See the Cairo call trace variant below.

### 3. Keep a single reference image of one comprehensive graph

- **Feasible?** Yes, and it's cheap to store.
- **Precedents:** Knuth's `trip.tex` torture test; browser "kitchen sink" pages such as the Acid tests and Storybook kitchen sinks.
- **What could go wrong:**
  - **Failures don't say where.** One changed pixel fails the whole test.
  - **Changes ripple.** With Graphviz in the loop, any layout change moves everything around it.
  - **Regression history is lost.** Each `issue_NN.dot` records a bug someone actually hit; merging them into one graph loses that link.
  - **Graphviz attribute interactions** such as `splines`, `rankdir`, clusters and `concentrate` can't all be combined in one graph.
- **Verdict:** not pursued. A few feature-focused graphs (shapes, fonts and Unicode, arrows, colours, images) next to the existing issue regressions would give the same coverage while still showing which feature broke.

### 4. Store a fuzzy hash: a numeric fingerprint (FFT-based or similar) where similar images score close

- **Feasible?** Technically yes, with no new dependencies, using NumPy's FFT or a DCT-based pHash.
- **Precedents:** pHash, dHash and the `imagehash` library, used for near-duplicate detection (TinEye, PhotoDNA). They are not used for regression testing.
- **What could go wrong:**
  - **Wrong design goal.** These hashes are built to ignore small local changes. A missing arrowhead, a wrong colour on one edge or a typo in a label is exactly that kind of change, so it would pass.
  - **Global transforms spread small local edits** thinly across all coefficients.
  - **Huge images collapse.** pHash shrinks the image to 32×32 first; `xx.png` is 30669×896.
  - **No image on failure.** You only learn that something changed, with nothing to compare against.
  - **Thresholds are guesswork** and have to be tuned per image.
- **What testing tools actually do:** they compare pixels directly with explicit tolerances. Firefox reftests annotate tests with `fuzzy(maxDiff, pixelCount)`; Skia Gold and Cairo's own test suite use fuzzy per-pixel matching; Matplotlib uses an RMS threshold.
- **Verdict:** rejected. If small storage is ever needed, a grid of block averages (e.g. mean colour per 8×8 tile) stays small but still shows where a change happened.

### Cross-cutting points

- **Graphviz version.** Storing pre-laid-out `.xdot` inputs, loaded with `set_xdotcode` like `tests/graphs/Times.gv.xdot`, would take Graphviz out of the test entirely. That matters for any approach that compares against stored references. It doesn't matter for base vs head, where both sides use the same `dot`.
- **What the inputs test.** Most of the 195 graphs in `tests/graphs/` are Graphviz demo graphs. They are valuable for crash and warning checks, but they say little about xdot's own drawing code. The `issue_*`/`pull_*` regressions are the most valuable inputs for pixel checks.

## Future work

- **Cairo call trace.** Commit text references made by logging xdot's Cairo calls (`move_to`, `curve_to`, `set_source_rgba`, `show_layout` text, …) through a small fake context, with numbers rounded to a fixed precision. That wouldn't depend on any Cairo version, would give tolerance through the rounding, and its diffs would be easy to read. Its limit: it can't tell whether the rendering is actually correct for anything the trace doesn't show, such as Pango shaping and font fallback, clipping, antialiasing and operator state, or how embedded images and SVGs look. It would complement pixel comparison, not replace it.
- **Pinned environment plus committed references.** This would detect drift over time and breakage caused by the environment. It needs a Docker image with pinned packages, for example Ubuntu 24.04 using the `snapshot.ubuntu.com` archive (`apt-get --snapshot <timestamp>`) and a fixed font set. It also needs a storage decision for the references: commit size-capped renders, commit full-size ones, or keep them on a separate branch. It should be combined with `.xdot` inputs.
- **Curated feature graphs**, as described in idea 3.

# PX-RE browser patcher

Static HTML, CSS and JavaScript; no package manager or build step is needed to
serve this directory. All firmware processing runs locally using browser byte
arrays and Web Crypto SHA-256. No firmware, extracted application, or complete
patched image is distributed. Source and browser additions follow the root
[LICENSE](../LICENSE) and [NOTICE](../NOTICE).

## Implementation

This is a data-driven JavaScript port of the fixed-release direct patcher, not a
Python interpreter in the browser. The Python linker, MIPS encoder and source
generators are evaluated at recipe-generation time. Their 411 guarded final
writes, source provenance and ownership receipts are preserved in `recipe.js`.
The JavaScript runtime executes that recipe against the exact verified stock
input. It does not reproduce the compiler-object linker in JavaScript.

`tools/build_browser_recipe.py` invokes the unmodified direct builder, including
its cache/source pins and full final validation, and captures its `Component`
writes. Each generated write is encoded with three operations:

- `copy`: copy matching bytes from the user's whole verified factory update.
- `zero`: fill a generated padding span with zeros.
- `literal`: project-generated patch bytes encoded as base64.

Every matching sequence of eight or more bytes found by the greedy encoder is
copied from user input, rather than included as a literal. This removes matching
factory-derived tables and code even when relocated. This bounded overlap check
does not establish independent authorship for shorter/common sequences.

The recipe pins direct-builder code, data and cache inputs. Markdown guides are excluded because documentation edits do not change generated firmware.
`recipe-pin.js` pins its serialized SHA-256; `patcher.js` also independently pins
the accepted stock and final identities and sizes. The pin detects accidental
recipe damage; it is not a signature or protection against replacement of the
site's trusted scripts. The independent documented final hash remains important.

`patcher.js` ports these runtime checks from `core.py`, `px_container.py` and
`build.validate`:

- Exact factory size/SHA-256 and parse/serialize round trip.
- Record framing, lengths, QNX/FPGA checksums and PIC legacy trailer.
- Exact component identity, per-write factory and generated hashes, ownership,
  non-overlapping writes and complete extension coverage.
- Unchanged FPGA, final revision headers, ELF section/program boundaries,
  added-section overlap/readability and load/memory sizes.
- All 910 sorted unwind-index entries, their FDE targets/extents and executable
  mappings, plus DSP/updater revision gates.
- Exact final size and SHA-256 before any download link is created.

Malformed ELF names and missing added sections also fail explicitly. Source,
object-restoration and relocation checks run during recipe generation; the
browser verifies the resulting pinned recipe and every generated write.

On HTTPS or localhost, `worker.js` runs the patcher off the page's main thread.
Opening `index.html` directly uses the same engine without a worker, supporting
offline use in browsers that expose Web Crypto on local files. The site uses
relative asset paths for GitHub Pages project URLs. `connect-src 'none'` blocks
fetch/XHR/WebSocket connections. All scripts and styles are local; no analytics,
CDNs, persistence, accounts, upload endpoint or backend is involved. The host
receives normal requests for static assets, never selected firmware contents.

The UI checks the size before reading a selected file. It clears download URLs
on a new selection, handles read/validation/worker errors, and creates explicit
download links only after all output checks pass. The input file is never
modified. The browser controls download destinations and duplicate filenames;
Python's exclusive filesystem publication semantics do not apply to downloads.

## Run locally

From the repository root:

```sh
python3 -m http.server 8000 --directory website
```

Open `http://localhost:8000`. For offline use, extract a repository download and
open `website/index.html` directly. The expected filenames and independent USB
copy verification are documented in the [main guide](../README.md).

## Regenerate and verify privately

Use Python 3.11+ and keep the factory file outside the repository. These commands
never publish firmware:

```sh
python3 tools/build_browser_recipe.py /private/path/PxUpdate_V2.2.2.0.0.bin
python3 tools/build_browser_recipe.py /private/path/PxUpdate_V2.2.2.0.0.bin --check
python3 tools/check_browser_recipe.py
```

Browser QA requires Playwright; install it in a virtual environment:

```sh
python3 -m venv /tmp/px-re-browser-qa
/tmp/px-re-browser-qa/bin/pip install playwright==1.64.1
/tmp/px-re-browser-qa/bin/python -m playwright install chromium
/tmp/px-re-browser-qa/bin/python tools/test_browser.py
/tmp/px-re-browser-qa/bin/python tools/test_browser.py --factory /private/path/PxUpdate_V2.2.2.0.0.bin --receipt website/VERIFICATION.json
```

On macOS, the test uses installed Google Chrome when available. Private parity
testing builds Python output in memory, drives the real browser file picker and
patch worker, downloads the result into a temporary directory, and compares
every byte. It repeats via offline `file://`, compares validation reports, tests
corruption rejection and verifies the stock file is unchanged. Temporary output
is removed automatically. The public [verification receipt](VERIFICATION.json)
contains hashes and check results, not private firmware or paths.

Public CI runs synthetic parser/ownership/corruption/recipe/UI tests without
firmware. It checks the recipe pin and direct-source inventory so a Python
builder change requires recipe regeneration. It cannot re-run private parity
without a stock image. A byte-identical result adds no new hardware/audio/QNX
runtime validation.

## Editing the page on GitHub

Edit `website/index.html` using GitHub’s pencil button and commit to `main`.
After committing, run the Pages workflow manually from Actions to check and deploy the change. Commits and pull requests do not launch it automatically. The HTML page
is excluded from `SHA256SUMS`, so text edits do not need a checksum update.
JavaScript, patch recipe, source pins and firmware input/output integrity checks
remain verified.

## GitHub Pages deployment

The [Pages workflow](../.github/workflows/pages.yml) runs browser checks and Python
tests, uploads only this directory, then deploys it when explicitly run from Actions. No stock firmware or generated updates belong in this folder.

1. Merge these changes into `main`.
2. In the repository's **Settings → Pages → Build and deployment**, select
   **GitHub Actions** as the source.
3. Run **Browser patcher and GitHub Pages** using **Run workflow** on `main`.
4. Check the deployment job and open its returned URL. The expected project URL
   is `https://water-feature.github.io/PX-RE/`.

Deployment is prepared, not enabled or published by this change. See GitHub's
[custom-workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

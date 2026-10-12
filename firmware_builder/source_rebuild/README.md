# Compiler-based source rebuild

This workflow rebuilds the retained feature chain using the compiler toolchain documented below. It stages implementations from [PX patch history](../../PX%20patch%20history/README.md) and keeps intermediate packages and reports for inspection. Supply your own exact factory update.

For the default cross-platform patcher, see the [direct builder](../direct/README.md) and [main guide](../../README.md).

## Directory map

`PX patch history/` contains live build inputs alongside research and historical evidence. Its name does not mean the whole directory is archival. The table below describes the compiler-based audit path; standalone recovery and SSD tools have separate inputs.

| Location | Role in the final firmware build |
|---|---|
| `firmware_builder/direct/` | Default cross-platform patcher: pure generators, source inputs, redacted object cache, direct linker and final validators. |
| `firmware_builder/source_rebuild/` | Separate compiler audit orchestrator, container parser, early-stage builders and restored follow-up sources under `sources/`. Historical verification receipt retained. |
| `PX patch history/B1 - voice steal fix/` | Mixed. Staging takes only `prophet_x_combined_application_patch/analysis/combined_patch/patch_spec.json`; other files provide implementation history and evidence. |
| `PX patch history/B3 - sysex channel fix/` | Research, original implementation and packaging evidence. The final builder uses `firmware_builder/source_rebuild/build_b3_merge.py` instead of staging this directory. |
| `PX patch history/B4 - expand user slots (abandoned)/` | Research and rejected implementation only; not staged. The active ELF parser is `qnx_elf.py` in B5. |
| `PX patch history/B5 - sample end fade/` | Mixed. Staging uses `b5_candidate_work/`, supplements B15 from `b15_candidate_work/`, and copies `b5_elf_placement_check.py` and `qnx_elf.py`. Other material is retained for review. |
| `PX patch history/B6 - center moves window/` | Mixed. Staging copies `b6_investigation/` and `b6_candidate_work/`, including their retained fixtures and evidence. |
| `PX patch history/B7 - center can be pushed/` | Mixed. Staging copies `b7_candidate_work/`, `b7_lfo_center_investigation/` and `b7_combined_instruction_model.py`. Other inherited copies are not selected. |
| `PX patch history/B8 - end escape/` | Mixed. Staging copies `b8_candidate_work/` and the selected revision of `b5_fade_prototype.py`. Other inherited copies are not selected. |
| `PX patch history/B9 - slow preset browsing/` | Mixed. Staging uses `b9_250_candidate_work/`; other variants and reports provide historical evidence. |
| `PX patch history/B10 - window scroll clicks/` | Mixed. Staging copies `implementation/b10_ordinary_entry_design_1_12/`, including retained validation data. Other experiments are not selected. |
| `PX patch history/B11 - type name tweak/` | Mixed. Staging copies `b11b_implementation_2_2_2_2_0/`, `b11b_investigation/` and `b11_pic_tools/`, plus the B5 packaging contract and `b14_ui_packaging_work/package_display.py`. |
| `PX patch history/B13 - fast boot (failed, abandoned)/` | Research and failed diagnostic implementations only; not staged. |
| `PX patch history/B14 - disable encoder accel/` | Mixed. Staging selects the candidate, packaging, metadata, stable-frame, sample-acceleration and UI source directories listed in `DIRS`. Rejected alternatives remain as evidence. |
| `PX patch history/B15 - stretch layer/` | Mixed. Staging copies `implementation/b15_candidate_work/`, supplemented by the B5 follow-up and restored builder sources. |
| `PX patch history/B16 - new sync divisions/` | Mixed. Staging copies `implementation/b16_finer_loop_sync_resolution/`, resets the in-place and geometry output directories, then restores the geometry builder and validator. Rejected offline sources remain for preservation checks, not as firmware candidates to install. |
| `SSD expansion/` (including `extract_qnx.py`), `RECOVERY.md` | Separate maintenance-image builder, application extractor and recovery guidance; not stages in the final firmware build. |
| `tests/`, `tools/`, `.github/` | Repository checks and synthetic tests; not firmware build inputs. |

`DIRS`, `HELPERS` and `stage()` in [source_pipeline.py](source_pipeline.py) are the exact staging specification. `build()` lists the commands that run. Copying a directory does not mean every script in it executes: some files are fixtures, retained results or provenance dependencies. Generated firmware and intermediate packages are local build outputs. Checksumming the public bundle also covers research files; that does not make them build inputs.

## Review and rebuild without the patcher

To rebuild compiler objects and review the historical feature stages, inspect the sources and invoke this separate orchestrator. It shares feature logic and the final hash with the direct builder, so agreement does not independently prove behavior. Review the stage code and independently verify the saved file's size and SHA-256.

Copy the factory `PxUpdate_V2.2.2.0.0.bin` into `firmware_builder/`. In your terminal, use `cd` to enter `firmware_builder/`, then run:

```sh
python3 source_rebuild/source_pipeline.py PxUpdate_V2.2.2.0.0.bin --work-dir source-build
```

The final `PxUpdate_V2.2.2.2.2.bin` is saved in `firmware_builder/`, alongside the factory input. The output file and `source-build/` directory must not already exist; move an earlier run elsewhere before rebuilding. Use `-o` to choose a different output location if needed. `--work-dir` retains firmware intermediates, staged source inventory, compiler output, validation reports and `build.log`, including after a failure. Omit it to use a temporary working directory that is removed afterward.

For a manual build, read `stage()` and the ordered invocations in `build()` in [source_pipeline.py](source_pipeline.py). `stage()` assembles the retained sources into the historical directory layout; `build()` is the complete command sequence and shows the inputs to each stage. Run those scripts in order in a private copy of that layout. Do not use experimental packages or rejected alternatives from the history as inputs.

## Compiler toolchain

Verified on Apple silicon macOS with Python 3.14.3, Apple clang 16.0.0 (`clang-1600.0.26.6`), Rust 1.83.0 and `objdump`; x86_64 host fixtures need Rosetta. Python needs no third-party packages. The builder checks that the required tools are available and records their installed versions in `toolchain_verification.json`. Versions are not restricted and Rust is not pinned; your installed toolchain and any explicit environment overrides are used. The scripts set `RUSTC_BOOTSTRAP=1` for Rust's experimental MIPS assembly support. Compiler versions can affect generated bytes; the final hash is mandatory. Windows/Linux compiler commands are not currently supported or verified. The build runs locally and invokes no downloads or Ghidra processes.

## Build and verification

1. Verify the published files against the root `SHA256SUMS` before staging. Pin the factory input size and SHA-256; prove an identical null repack with [container.py](container.py).
2. Apply B1's guarded source recipe; compile the B5/B8 helpers and emit B3 PIC instructions.
3. Rebuild the retained B7, B6, B9, B14, B15, B5/B7 follow-ups, B10, B11 and B16 stages. Run their saved-image, instruction, ownership, bounds, ABI, version-gate and host validations. Abandoned B4/B13 and rejected alternatives are excluded.
4. Check the final package hash, length, parser/serializer round trip and unchanged FPGA record before creating the output exclusively.

Expected final: **3,187,784 bytes**, SHA-256 **`488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c`**. See the [main README](../../README.md) for independent hashing and hardware installation guidance.

The [rebuild receipt](VERIFICATION.json) records the 2026-10-11 compiler-based source-only and former public-entry-point runs, exact byte comparison and CLI guard checks. That receipt predates the default direct builder; current direct results are in [direct/VERIFICATION.json](../direct/VERIFICATION.json). The root [SHA256SUMS](../../SHA256SUMS) lists the public bundle files.

## Archive compatibility adjustments

The public archive deliberately excludes firmware and some private analysis artifacts. The public sources include explicit compatibility adjustments. B8 reruns its host validation on the emitted objects before checking the candidate, so its test-source receipt reflects the current sources. Staging copies the adjusted Python files unchanged and prepares the supporting receipts:

- Refresh B7 design-source receipts for the public source headers while retaining the historical emitted payload, frame and measurement hashes.
- Select the B8 revision of the shared B5 helper and combine the separately archived B15/B5 follow-up sources. [sources/lfo_endpoint_investigation/build_fix.py](sources/lfo_endpoint_investigation/build_fix.py) and [reproduce.c](sources/lfo_endpoint_investigation/reproduce.c) restore two authored follow-up sources missing from the archive.
- Supply SHA-256 guards for the two B14 pre-edit spans rather than original instruction words or the full private disassembly.
- Restore B7's historical checksum filename. The published B7 validator omits the old branch-target trace review that requires an unpublished full disassembly; it reports `NOT RERUN; historical evidence retained` and leaves that result unset. The emitted-byte host and CFI checks still run.
- The published B10 validator excludes absent `phase.csv` from the report artifact list; its validation assertions still run.
- The published B11 PIC decoder supports importing against the generated parent image. Refresh B11's source-file receipts for the portable archive; preserve its historical firmware-input hashes. Independently assemble and compare the emitted fragments before building the image.
- Recreate B16's preservation receipt for the source-only staged files. The published integration script excludes generated Python caches from the preservation comparison.

The pinned final firmware SHA-256 is the decisive output integrity gate: the builder refuses to create the requested output unless the generated package matches the accepted bytes. The other guards and validation assertions check inputs and intermediate results.

Before staging, the builder checks every file listed in the root `SHA256SUMS` and records the result in `published_source_verification.json`. This detects missing or changed published files, but does not authenticate a checkout if both files and their checksums have been changed.

B7's and B11's refreshed source hashes and B16's recreated preservation receipt establish baselines from the current staged files. They detect subsequent changes to the files they cover during the run; they do not independently establish that those files match a historical or trusted release. `staged_source_inventory.json` records the staged files before compilation, including generated receipts. It is a traceability record, not a comparison against an independently pinned expected inventory. Historical reports remain evidence of their original run, including hardware-pending wording; subsequent hardware observations are recorded in the feature guides. A matching final hash establishes byte identity with the accepted package, not exhaustive proof of behavior on every instrument.

Original-byte fields in retained patch recipes and receipts have been replaced with SHA-256 hashes and lengths. This changes their representation, not the recorded test outcomes. Replacement instructions and authored helper sources remain available for review. Generated build artifacts stay in the private working directory.

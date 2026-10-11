# B11 - Type browsing and real instrument selection

Technical handover covering the closed B11 category-skipping investigation and successful B11b follow-up. B11 deployed no patch; B11b is implemented and hardware-confirmed. This identifies the B11b milestone, not the latest combined project firmware.

**Firmware:** `2.2.2.2.0` (B11b), built from exact `2.2.2.1.15`; no original B11 package.

**Hardware: PASS (B11b):** The Type-name/instrument-selection follow-up was confirmed working. Original B11 category skipping was not deployed; historical hardware-pending reports predate B11b acceptance.

B11 originally aimed to skip empty Type categories. It closed with mixed-layer navigation and cache-lifecycle questions unresolved. The owner clarified that the immediate problem was entering a populated category and seeing `1.-----` until turning Instrument. B11b addresses that: a manual Type transition promotes a remembered placeholder to the first real instrument when available, while keeping empty Types and the manually selectable placeholder.

This handover explains both the intentionally closed investigation and the shipped follow-up. B11’s research and sketches are evidence, not an installed category-skipping feature.

## B11 - closed category-skipping investigation

**Patch location:** PIC controller (MIPS), proposed only.

**Patch size:** 276-byte proposed in-place layout (268 active + 8 padding); no deployed patch. The successful B11b implementation has separate size accounting below.

### Original request and intended behavior

Skip empty Type categories while browsing User/Purchased groups, preserving Factory navigation.

Proposed search:
- Cover both Instrument 1 and Instrument 2, forward and reverse.
- Search only in the encoder direction; preserve stock clamping rather than wrap.
- Inspect at most 17 candidates (at most 16 alternative categories are actually in range).
- If no populated category exists in that direction, leave category and instrument selection unchanged.
- If every category is empty, Type therefore does nothing beyond the existing UI refresh.
- Preserve Group navigation, preset recall and existing patches.
- Reuse cached counts; avoid blocking communication or loading for each candidate.

PIC space was effectively exhausted. The user required an efficient, narrow investigation, with no broad cave hunt or compaction detour.

### Baseline and evidence limits

Investigated baseline: user-designated **2.2.2.1.15**.

Authorized PIC image:
`b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_pic.bin`

Length: `0x81960` (530,784 bytes), mapped at `9D000000–9D08195F`.

SHA-256 reported in closure:
`be8eb8ac823a639f3024b97e01b017ef0cef5f33d086eaa71dfe55d4b0e34622`

Decoded Type instructions matched the active Ghidra listing at checked anchors. This was not a complete Ghidra export/hash comparison. Package revision was user-established, not independently verified from package metadata.

The original PIC import was rebased after import at zero, leaving inconsistent `AA...` references and incomplete function coverage. Later local checks used raw instructions, raw branch/jump scans and defined data. Missing functions/xrefs were never accepted as free-space evidence.

### Established count contract

Existing count getter: `9D0792E0`. It is a pure, unchecked load with no communication or cache fill.

Expanded count table:
`80037E90 + 8 * (17 * group + category)`

65 groups, 17 categories, eight bytes per record:
- First word: real instrument count plus one placeholder.
- Second word: cumulative name index for populated categories, otherwise `FFFFFFFF`.

**Empty count = 1; populated count >= 2.** A zero/nonzero test would be wrong.

Builder `9D040ED8` reads persistent raw counts and adds one. Legacy unavailable groups are filled with the same representation as empty categories; there is no established distinct unavailable/stale marker. The first raw byte FF selects the extended format; FF elsewhere must not be globally treated as unavailable.

`9D079978` is a blocking communicating count request and unsuitable for per-category browsing. `9D079340` changes communication/name state and is also unsuitable. The flash staging buffer is shared and must not be treated as a permanent live count table.

Normal descriptor limits are group 64 and category 16. Ordinary setters and bulk preset validation enforce these limits. This supports ordinary validated states, not arbitrary corrupt RAM.

### Navigation and setter findings

The Type handler is dispatch case 16:
`9D029348 -> 9D02A74C`.

Four original category setter calls:
- Instrument 1 forward: `9D02A78C`.
- Instrument 1 reverse: `9D02DF0C`.
- Instrument 2 forward: `9D02D45C`.
- Instrument 2 reverse: `9D02DD1C`.

They call existing relative setter thunk `9D04FA6C`, with category parameter `0x24` or `0x65`, fixed direction +1/-1, layer/edit selection and maximum 16. Existing patched thunk/interceptor chains must be preserved.

`9D0816E0` clamps current plus delta to 0..maximum. A larger signed delta can reach the discovered category through the original setter without directly writing category RAM.

The real setter retains a remembered valid instrument selection and clamps excessive selections to count minus one. Empty categories therefore resolve to placeholder index zero. Loading and notifications continue through existing paths.

### Space investigation and corrected candidate

Initial standalone search: **112 bytes**, emitted with a handwritten MIPS subset encoder. Initial added-wrapper estimate: 296–368 bytes; this was not a measured integrated requirement.

The placement pass instead shared duplicated Type setup within existing occupied code:

| Half-open replacement range | Bytes |
|---|---:|
| 9D02A74C–9D02A7BC | 112 |
| 9D02D428–9D02D484 | 92 |
| 9D02DD08–9D02DD2C | 36 |
| 9D02DEF8–9D02DF1C | 36 |
| Total | 276 |

No extra allocation, persistent RAM, table, preset field or message was required for the demonstrated primary-bank algorithm.

**Important correction:** the first 276-byte sketch broke six incoming Group return paths that Ghidra's reference inventory missed:
- `9D02EB14/EB54/EB60 -> 9D02D464`.
- `9D02EC18/EC58/EC64 -> 9D02A794`.

The closure candidate retains those refresh entries and the original dispatch/Group routes. Missing predecessor instructions were decoded and shown to branch away from all four replacement ranges.

Corrected budget: **268 active instruction bytes + 8 trailing padding bytes = 276 bytes**. The eight bytes were not proof that the unresolved behavior corrections would fit.

Independent LLVM MIPS assembly via Rust 1.83.0 (`mipsel-unknown-none`, `mips32r2`, noreorder/noat) matched all 69 emitted words, with no unresolved relocations.

Modeled checks:
- First layout: 1,088 cases.
- Corrected layout: 1,632 cases, covering both instruments, edit values 0/1/2, categories, directions, population patterns, Factory and Group routes.
- Setter calls were mocked; these were not hardware or cache-freshness validation.

Five scattered four-byte compaction proposals totaled 20 bytes, but were not installed or certified as contiguous storage. They were unnecessary for the in-place candidate and should not be pursued as part of this closed branch.

### Unresolved correctness issues at closure

#### Both Layers policy

Stock reads bank A for edit values 0 and 2, bank B otherwise. In Both Layers, it computes one absolute category from A and assigns it to both banks. It does not independently increment different starting categories.

With different groups:
- A's populated category may be empty in B.
- Skipping in nonfactory A can move Factory B by multiple categories.
- Factory A's ordinary step can land on an empty category in nonfactory B.

Independent empty filtering, Factory single-step preservation and stock common-target coupling can conflict. No mixed-bank policy was settled.

A proposed fallback—stock browsing in Both Layers, skipping in individual-layer modes—was rejected because the user disliked inconsistent navigation. Do not treat that acceptance as final authorization.

#### Cache freshness

Initialization explicitly reconstructs the expanded cache. Two recovered rebuild routes call raw count/name rebuilds and then `9D040ED8`.

But the route at `9D02277C` calls `9D042A8C` and `9D042B80`, then returns through `9D021BB0` without an explicit expanded-cache reconstruction in the recovered path.

This was an unresolved lifecycle question, not proof that every such operation leaves stale counts. Stale zero-population data could cause B11 to hide newly populated categories. No synchronization mechanism or rebuild correction was implemented.

### Why the branch was closed

The user's actual frustration was that entering Type categories displays `-----` at position 1, including populated Factory categories. They must turn Instrument to position 2 to learn whether content exists.

The investigation established that this is the internal index-zero placeholder shared by categories. Its precise original design purpose was not proven.

The user wanted the placeholder to remain accessible by turning Instrument left. Removing categories or removing position 1 was unnecessary. B11b therefore targets the default instrument selection on manual Type changes instead.

**Do not resume B11 automatically.** Its research is useful to B11b, but its category-skipping code was never approved for installation.

## B11b - completed follow-up

## Final implementation logic

**Patch location:** PIC controller (MIPS) for shipped B11b; QNX edits are version metadata only. Original B11 category skipping shipped no patch.

**Patch size:** B11b: 204 bytes across four fragment allocations (200 active + 4 padding) + four 4-byte clamp-call replacements = 220 functional write-span bytes. Actual differences: 187 functional PIC bytes + four PIC version bytes, three QNX version bytes, and 200 whole-package bytes. No payload growth. Closed B11 had a 276-byte proposed in-place layout, not a deployed patch.

The four stock instrument restoration paths read the remembered selection using `9D01E334`, clamp it through stock `9D04D4FC`, store it, and continue through stock load/notification code. B11b redirects only the four clamp-call instructions to a small **guarded helper**.

1. The Type encoder's shared routing derives the actual target category from the existing category and normalised direction. Category range is `0..16`.
2. At a Type boundary, routing returns via existing refresh logic **without invoking the setter** or changing any instrument selection.
3. For a valid manual transition, routing snapshots the old categories for the affected banks and calls existing absolute setter `9D04DACC` with the already bounded common target.
4. The helper recognizes this exact manual invocation by comparing the **full saved return address `9D02DF10`**. Other callers take the original clamp path, preserving preset recall.
5. For each bank, it promotes remembered selection `0` to `1` **only if the bank's old category differs from the target**; it then tail-calls the existing stock clamp. Existing count validation brings `1` back to `0` when a Type is empty. Nonzero selections retain stock clamping behaviour.

Conceptual rule (illustrative, **not original assembly/source**):

```text
if manual_type_change and bank_type_actually_changed and remembered == 0:
    clamp_input = 1
else:
    clamp_input = remembered
result = stock_clamp(clamp_input, placeholder_inclusive_count)
```

In Both Layers, the stock common target is determined from primary bank A. Counts, old-category comparisons and remembered selections remain independent per bank. A secondary bank already at the common target is not promoted, even if its remembered index is zero. Group IDs `0..64` use stock validation and group mapping; no new category-population search exists.

## Exact changed PIC addresses and allocation

All address ranges below are PIC virtual addresses; range end is exclusive.

| Owned location | Allocation | Final purpose |
|---|---:|---|
| `9D02A74C–9D02A794` | 72 bytes | Shared Type dispatch, direction/target handling and primary snapshot |
| `9D02D428–9D02D464` | 60 bytes | Instrument-2 entry, helper tail, secondary snapshot, refresh selector |
| `9D02DD08–9D02DD2C` | 36 bytes | Guarded clamp helper head |
| `9D02DEF8–9D02DF1C` | 36 bytes | Boundary bypass and absolute setter invocation |
| **Four fragment allocations** | **204 bytes** | **200 active bytes + 4 padding bytes** |

Four existing clamp `jal` words (4 bytes each) are replaced in place to call helper `9D02DD08`: `9D04DEBC` (Instrument 1/A), `9D04E010` (1/B), `9D04E54C` (2/A), `9D04E624` (2/B). The corresponding stock selection stores are at `9D04DEC8`, `9D04E01C`, `9D04E558`, `9D04E630`.

No additional PIC storage, persistent RAM or stack frame. The 72 bytes of shared refresh/UI logic outside the allocated Type ranges were explicitly preserved; no unrelated fix was compacted and no unknown `FF`/free region was appropriated. This **supersedes** the interim 16-byte shortfall in `followup_findings.md`; the final 200-byte compact design resolved it. Earlier proposed return identities `9D02DF0C` and `9D02DF14` were superseded by **`9D02DF10`**.

## Cache-consistency investigation and why no cache patch shipped

Early static research found the expanded PIC instrument cache at `80037E90 + 8*(17*group+category)` with records containing placeholder-inclusive count and cumulative name-record offset; empty entries have count `1` and offset `FFFFFFFF`. The getter `9D0792E0` is an unchecked table read. If counts/offsets were stale after removal, a promoted selection could cause the PIC metadata loader to read a record for another category; the QNX normal selection lookup avoids a null folder dereference in its checked branch but does not restore selection zero, and overall audio/display consequences were not proved safe.

The important corrective evidence was the **real User-bank deletion workflow**:

- PIC's User-bank deletion handler invokes QNX command **4036** (`LibraryCopy_DeleteGroup`) and waits for completion.
- PIC then refreshes bank availability and invokes count-page refresh `9D042A8C` at `9D01B904`, name-page refresh `9D042B80` at `9D01B90C`, and expanded-RAM cache builder **`9D040ED8` at `9D01B914`**.
- The count refresh presents the observed text **`Refreshing category files...`**; deleted bank availability is refreshed so encoder navigation skips the bank.
- An instruction harness ran this sequence with controlled I/O and checked all **1,105** expanded-cache rows. The user independently observed the front-panel refresh/skip behaviour on .1.15.

The other suspect path at **`9D022760`** was identified as Debug Menu **`Reload Sample Names`** (item 3). It rebuilds persistent names/counts without an explicit expanded-RAM rebuild, but the operation was not shown to change library population; a reachable stale-count failure from a normal front-panel workflow was **not demonstrated**. The QNX individual-instrument delete backend `4034` was traced but **not established as front-panel-accessible**, and the user confirmed only whole-bank deletion is provided on the front panel.

**Final decision:** omit the proposed two-word cache patch to `9D022794/9D0227A0` from B11b. It was an uninstalled investigation option, not part of the shipped firmware. This conclusion is scoped to the established normal-user workflows; it does not prove arbitrary external filesystem edits, developer/debug operations or all concurrent mutations safe.

## Release construction and versioning

**Exact baseline:** firmware package `2.2.2.1.15`; its SHA-256 is `ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450` as reported in original HANDOVER. No experimental B10 `.1.16` changes are included.

**Candidate:** `PxUpdate_V2.2.2.2.0_B11b_real_instrument_on_Type_candidate.bin`, **3,187,784 bytes**, SHA-256:

`89d794880697c18da66356a2fd8cb90b7302d2250574ea4664bdbc496945bc6f`

Revision `2.2.2.2.0` was chosen because `.1.16` was already occupied and the five-component DSP startup display's last revision component is 4-bit, making `.1.17` unsuitable for faithful reporting. Original build documentation reports synchronised PIC/app record headers, updater gate, DSP display, PIC revision responses, and application checksum. The three-field `M` display remains unchanged.

The documented version-only locations are PIC `9D001394`, `9D0013A0` (final report component), PIC `9D0258B4`, `9D051BC4` (report prefix), and QNX ELF offsets `0x1F4E3`, `0x250E2`, `0x250EF`. The candidate comparison reports **191 PIC changed bytes** (187 functional + 4 version bytes), **3 QNX changed version bytes**, **200 package changed bytes** overall. All other QNX audio code, FPGA, stock refresh/UI paths, existing patches and Group routing were reported unchanged. Application checksum trailer bytes are `fc 2a` (word checksum `0x2AFC`); FPGA trailer is `59 77`, and the inherited PIC trailer is `30 30`.

Original build scripts, approved assembly, harnesses and machine-readable results have now been recovered from the local workspace. The privately held package hash was checked during cleanup; the feature tests were not rerun. Firmware images and generated binary fragments remain private.

## Original build-time validation results

The final HANDOVER reports the following PASSES for the **emitted PIC file** (not merely a speculative overlay):

| Check | Reported result |
|---|---|
| Encoding | LLVM match for all **51** allocated layout words; zero relocations |
| Routing / setter | **18,366** instruction-execution cases |
| All-group routing | **42,120** more cases covering all **65** groups |
| Four clamp paths | **2,016** setter cases |
| Nonmanual return identity | **16** cross-region rejection cases |
| Preset zero | Bulk recall preserves all four placeholder zeros at count 1/2/256 |
| Bank delete cache refresh | All **1,105** rows correct with controlled flash/I/O callbacks |
| Control flow | **18** branches/delay slots verified; owned-entry/branch audit |
| Updater | **22** gate cases; baseline `.1.15` accepts new version |
| PIC packaging | **130** transfer-block checksums and **260** valid/corrupt comparisons |
| Package extraction | Exact re-extraction match, unchanged FPGA record, consistent hashes |

Limitations: the instrument-routing tests stub real sample/metadata/UI effects; bank-refresh tests simulate actual flash and communications. Real device timing, interrupt effects and full audio behaviour were **not proven by these tests**. The original validation JSON and harness source are included below. These are saved results, rather than tests rerun during documentation cleanup.

## Hardware test and acceptance

The focused hardware plan (in `original_reports/HANDOVER.md`) covers: real versus empty Types, remembered nonzero selections, manual placeholder choice, Instrument 1/2 and layer A/B, Factory/User/Purchased groups, Both Layers with mixed empty/populated banks and unchanged secondary Type, boundaries, Group navigation, and preset recall of intentionally stored placeholder zeros. Complete User-bank deletion was an optional regression check.

**Actual outcome:** `2.2.2.2.0` was tested working on hardware. No instrument-by-instrument test log, recorded audio, hardware trace, or repeat of the optional deletion test on `2.2.2.2.0` was provided. Preserve this distinction when publishing.

## Excluded work and future cautions

- **B11 category skipping** was abandoned; B11b does not skip categories.
- **No expanded cache-refresh correction** and no per-turn QNX count communication were included.
- **No change to preset file format**, persistent selector representation, underlying instrument or sample data, bootloader, or unrelated features.
- **No B10 `.1.16` changes** inherited. Do not merge/rebase B11b onto another firmware version without new diff ownership and regression tests.
- Original scripts retain pinned private inputs, generated-fragment and toolchain requirements; see the packaging path below.

## Recovered source and packaging path

The main implementation is in `b11b_implementation_2_2_2_2_0/`. `approved/candidate.s` and its listing preserve the frozen compact layout. `build.py` checks `input_manifest.json`, installs four approved fragments and four clamp-call replacements, synchronizes revision metadata, and creates private candidate components/container. `validate.py` checks emitted bytes and executes the retained harnesses. `package.py` validates the container, independently re-extracts it and exclusively creates the updater-facing package after PASS.

```sh
python3 b11b_implementation_2_2_2_2_0/build.py
python3 b11b_implementation_2_2_2_2_0/validate.py
python3 b11b_implementation_2_2_2_2_0/package.py
```

These are the original incremental commands, requiring preparation in a private working copy:

- Supply the exact baseline package `PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin` and its extracted PIC/QNX at the paths pinned in `input_manifest.json`. The three hashes are recorded there.
- Regenerate the four `approved/fragment_*.bin` files from the approved layout before building; generated binary fragments are excluded from this public folder. `measure_compact.py` emits the matching layout into `compact/`, with independent LLVM comparison using Rust's `mipsel-unknown-none` target and `RUSTC_BOOTSTRAP=1`. Match all 51 words against `approved/listing.txt` before using them as the frozen approved fragments.
- Preserve the sibling paths listed in the input manifest. Some listed files are hash-pinned procedure/provenance references rather than executed build dependencies; they are included to preserve the original checks. Do not run unrelated B10/B14/B7 packagers as B11b build steps.
- The published `b11_pic_tools/decode_pic.py` loads the generated `.1.15` PIC from the staged layout and can be imported by the B11 validators. Use the root source builder to prepare that layout.
- Use Python 3 and the matching Rust/LLVM MIPS toolchain (recorded independent assembly used Rust 1.83.0). Work in a fresh private directory: output creation is exclusive and existing generated checkpoints may need moving aside. Generated firmware must stay outside the public repository.

The final package is `PxUpdate_V2.2.2.2.0_B11b_real_instrument_on_Type_candidate.bin`. Container framing, payload lengths and record order remain inherited. Application and PIC headers use `2.2.2.2.0`; the application word checksum is recalculated, complete FPGA record retained, and PIC trailer `30 30` preserved under the established contract. No new PIC or QNX payload space is required by B11b.

The supplied tools document the incremental `.1.15` → `.2.0` path. The [root patcher](../../patch_prophet_x.py) now generates the retained parent inputs from the exact factory update, emits and independently checks B11b instructions, and continues to the final package. See the [source build guide](../../firmware_builder/README.md) for source review and retained build reports.

## Complete supporting-file inventory

Every retained supporting file is linked below. Original B11 closure records are intentional historical evidence; B11b implementation files and test evidence describe the successful follow-up. Superseded proposal handovers, stale missing-artifact notices and duplicate archive documentation are retained privately. No firmware packages, extracted ELFs/PICs, object files or generated binary fragments are included. The [checksum inventory](SHA256SUMS) covers this handover and supporting files.

| File | Purpose |
|---|---|
| [b10_ordinary_entry_design_1_12/candidate_1_15/package.py](b10_ordinary_entry_design_1_12/candidate_1_15/package.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11_pic_tools/decode_pic.py](b11_pic_tools/decode_pic.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11_pic_tools/measure_corrected.py](b11_pic_tools/measure_corrected.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11b_implementation_2_2_2_2_0/approved/candidate.rs](b11b_implementation_2_2_2_2_0/approved/candidate.rs) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/approved/candidate.s](b11b_implementation_2_2_2_2_0/approved/candidate.s) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/approved/listing.txt](b11b_implementation_2_2_2_2_0/approved/listing.txt) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/bank_refresh_results.json](b11b_implementation_2_2_2_2_0/bank_refresh_results.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/branch_targets.json](b11b_implementation_2_2_2_2_0/branch_targets.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/build.py](b11b_implementation_2_2_2_2_0/build.py) | B11b build, emitted-byte validation or package creation entry point. |
| [b11b_implementation_2_2_2_2_0/check_bank_refresh.py](b11b_implementation_2_2_2_2_0/check_bank_refresh.py) | Instruction harness, compact-layout emitter or regression checker. |
| [b11b_implementation_2_2_2_2_0/check_compact.py](b11b_implementation_2_2_2_2_0/check_compact.py) | Instruction harness, compact-layout emitter or regression checker. |
| [b11b_implementation_2_2_2_2_0/compact/candidate.rs](b11b_implementation_2_2_2_2_0/compact/candidate.rs) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/compact/candidate.s](b11b_implementation_2_2_2_2_0/compact/candidate.s) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/compact/extended_results.json](b11b_implementation_2_2_2_2_0/compact/extended_results.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/compact/listing.txt](b11b_implementation_2_2_2_2_0/compact/listing.txt) | New compact helper layout or independent assembly input/listing. |
| [b11b_implementation_2_2_2_2_0/compact/results.json](b11b_implementation_2_2_2_2_0/compact/results.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/emission.json](b11b_implementation_2_2_2_2_0/emission.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/input_manifest.json](b11b_implementation_2_2_2_2_0/input_manifest.json) | Pinned private input and original source/provenance hashes. |
| [b11b_implementation_2_2_2_2_0/measure_compact.py](b11b_implementation_2_2_2_2_0/measure_compact.py) | Instruction harness, compact-layout emitter or regression checker. |
| [b11b_implementation_2_2_2_2_0/package.py](b11b_implementation_2_2_2_2_0/package.py) | B11b build, emitted-byte validation or package creation entry point. |
| [b11b_implementation_2_2_2_2_0/package_results.json](b11b_implementation_2_2_2_2_0/package_results.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_implementation_2_2_2_2_0/setter_harness.py](b11b_implementation_2_2_2_2_0/setter_harness.py) | Instruction harness, compact-layout emitter or regression checker. |
| [b11b_implementation_2_2_2_2_0/validate.py](b11b_implementation_2_2_2_2_0/validate.py) | B11b build, emitted-byte validation or package creation entry point. |
| [b11b_implementation_2_2_2_2_0/validation.json](b11b_implementation_2_2_2_2_0/validation.json) | Saved emission, validation, identity or packaging evidence. |
| [b11b_investigation/check_bank_refresh.py](b11b_investigation/check_bank_refresh.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11b_investigation/check_compact.py](b11b_investigation/check_compact.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11b_investigation/measure_compact.py](b11b_investigation/measure_compact.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b11b_investigation/redirected_findings.md](b11b_investigation/redirected_findings.md) | Original design decision or hash-pinned packaging-contract reference. |
| [b11b_investigation/setter_harness.py](b11b_investigation/setter_harness.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b14_ui_packaging_work/package_display.py](b14_ui_packaging_work/package_display.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b5_packaging_work/established_packaging_contract.md](b5_packaging_work/established_packaging_contract.md) | Original design decision or hash-pinned packaging-contract reference. |
| [b7_candidate_work/validate_version_gates.py](b7_candidate_work/validate_version_gates.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b7_lfo_center_investigation/implementation_1_12/package.py](b7_lfo_center_investigation/implementation_1_12/package.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [b9_250_candidate_work/mips_check.py](b9_250_candidate_work/mips_check.py) | Imported decoder/encoder/gate utility or hash-pinned provenance dependency. |
| [closed_B11/b11_276_closure.md](closed_B11/b11_276_closure.md) | Closed B11 investigation/placement/decision evidence; no deployed patch. |
| [closed_B11/b11_findings.md](closed_B11/b11_findings.md) | Closed B11 investigation/placement/decision evidence; no deployed patch. |
| [closed_B11/b11_placement_feasibility.md](closed_B11/b11_placement_feasibility.md) | Closed B11 investigation/placement/decision evidence; no deployed patch. |

For this cleanup, Python/JSON syntax, document links, source-copy identities and the saved private package SHA-256 were checked. Compilation, full feature tests and hardware testing were not rerun.

The PIC decoder uses the generated parent image in the staged layout and accepts hexadecimal address ranges: `python3 b11_pic_tools/decode_pic.py START:END [START:END ...]`.

# Direct builder implementation

The [direct firmware patcher](../patch_prophet_x.py) is launched by `firmware_builder/patch_prophet_x.py` and uses this implementation on Windows,
macOS and Linux. Requires Python 3.11+. Follow the
[main guide](../../README.md#patching-the-firmware-using-the-supplied-tool) for commands.
The same code and factory input must produce the same final bytes on every host.

## Build and checks

1. Verify the factory SHA-256 and parse/re-serialize its container without changes.
2. Verify generated compiler-source/include hashes and the pinned object manifest;
   restore redacted spans from the verified factory and check complete object hashes.
3. Link the QNX helpers in memory, generate final hooks and ELF tables, and emit
   authored PIC instructions/data. Every write guards the original factory and
   has one final owner. Conflicts, unowned extensions and relocation errors fail.
4. Serialize the final update and verify record checksums, unchanged FPGA record,
   all changed-byte ownership, added ELF sections/load mappings, 910 indexed FDE
   targets, revision headers/gates, final length and SHA-256 before publication.

Retained B5/B8 ELF metadata artifacts are generated as final-layout content.
Historical behavioral checks are documented in the
[feature history](../../PX%20patch%20history/README.md) and
[compiler audit guide](../source_rebuild/README.md).

The final firmware is published from a fully written temporary file using an
exclusive hard link, so existing destinations are never replaced. Use a local
filesystem supporting hard links. Successful builds leave the final file and
`<output>.report.json` only. If report publication fails after firmware publication,
the validated firmware remains and the command reports failure. The commands in the main guide save the firmware and report in
`firmware_builder/`, alongside the factory input. The input is never modified.

## Implementation map

| Files | Purpose |
|---|---|
| `build.py`, `px_container.py` | Command, final checks, parser/serializer, publication |
| `core.py` | Immutable factory guards, one-owner write registry |
| `objects.py`, `cache/manifest.json`, `cache/blobs/` | Pinned source/include checks and redacted-object restoration |
| `elf_objects.py`, `helpers.py`, `final_helpers.py`, `remaining_helpers.py` | Bounded x86-64 relocation and final helper sections |
| `qnx.py`, `b1_recipe.json` | Final QNX layout, hooks, metadata and factory-derived unwind index |
| `mips.py`, `pic.py`, `pic_stretch.py`, `pic_recipes.json` | Bounded MIPS encoder and final PIC composition |
| `sources/`, `object_recipes.json` | Authored source inputs and original source mapping |
| `PROVENANCE.json`, `VERIFICATION.json` | Extraction provenance and verification scope |

## Object provenance and maintenance

The cache contains 15 redacted compiler objects. Factory-matching spans are stored as zero placeholders with
source offsets, sizes and SHA-256 values. Restoration is in memory only and must
match each complete original object hash. Unchanged firmware comes from the user.

The published manifest is an explicitly derived object-only manifest. It retains
original object entry IDs, compiler arguments/environment, source/include hashes,
redaction recipes and original/restored blob hashes. Its provenance identifies the
original compiler recording manifest and toolchain.
`objects.py` pins the derived manifest's exact SHA-256. [PROVENANCE.json](PROVENANCE.json) maps extracted
generators to their reviewed source hashes; feature sources remain in the repository.

For maintenance, compile changed helper sources using the reviewed compiler flags,
redact factory-matching spans, audit the resulting blobs, and record new source,
blob and complete restored-object hashes. Review relocation/layout changes and
update the manifest pin and applicable recipes. Verify the result against the
intended firmware identity before changing its final pin. Do not suppress guards
or reuse a cached object after its source/include hashes change. The separate
[compiler rebuild](../source_rebuild/README.md#review-and-rebuild-without-the-patcher) remains
available for auditing the retained feature implementation.

The publication audit checks for private paths, forbidden firmware artifacts and
sampled factory/final byte overlaps in cache blobs (24-byte windows, reference
stride 8, at least 6 distinct bytes). Factory-overlap hits must be absent. Final
image hits are separately attributed to the source-generated helper sections,
where authored code/CFI naturally matches its installed copy. This is a bounded
content check; shorter or common matching sequences fall outside its scope.

## Verification scope

The private direct trial reproduced the accepted final image on macOS in about
0.82 seconds. Windows and Linux builds passed per user reports; their machine
receipts and exact timings were not supplied. Local public-integration checks
are recorded separately in [VERIFICATION.json](VERIFICATION.json).

Public CI uses synthetic fixtures for parser, ownership, cache rejection,
relocation rejection and output protection, without firmware or compiler tools.
Exact factory-to-final testing requires a privately supplied factory image. A
matching final hash proves byte identity with the documented firmware; no new
hardware/audio/QNX runtime validation is claimed by this builder integration.

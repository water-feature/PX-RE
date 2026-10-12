# Prophet X firmware patches and SSD tools

This project documents a set of user-created bugfixes and improvements for the Sequential Prophet X. It includes a local firmware patcher, implementation sources and test evidence for each feature, and a guide detailing how to install a larger SSD. 
  No affiliation with Sequential. 
  No firmware images or extracted payloads are distributed here. 
  Install at your own risk and keep generated firmware images private. 
  LLMs used throughout. 
  Thanks to [rvense](https://rven.se/prophet-x/) for taking the first steps. 

**Before installing:** read [RECOVERY.md](RECOVERY.md), open up your synth by following [this video](https://www.youtube.com/watch?v=tF9Ji9iL00g) and create an image of your SSD.

## What is included

- [Direct firmware patcher](firmware_builder/patch_prophet_x.py): to generate a flashable firmware file with the changes described in the changelog below.
- [SSD expansion guide](SSD%20expansion/README.md): details on how to prepare and fit a larger SSD.
- [Feature and version history](PX%20patch%20history/BUILD_VERSION_HISTORY.md): follows the build chain and links to each feature's implementation, test status and packaging evidence.
- [Firmware architecture and map](FIRMWARE_MAP.md): container format, QNX/PIC/FPGA components and version-specific offsets.
- [Source and research directory map](firmware_builder/README.md#directory-map): identifies active build inputs, retained research and mixed directories.
- [Contributing](CONTRIBUTING.md): evidence, reproduction and copyright requirements for proposed changes. PRs and bug reports welcome.

## Changelog for 2.2.2.2.2.bin

| Feature | Description |
|---|---|
| [Voice steal](PX%20patch%20history/B1%20-%20voice%20steal%20fix/README.md) | Fixed bug where amp envelope attack was ignored on voice steal, causing a harsh click when sample start was set on a non-zero crossing. |
| [SysEx reception](PX%20patch%20history/B3%20-%20sysex%20channel%20fix/README.md) | Fixed bug where the synth ignored sysex when set to receive midi on any channel but 2 or omni. |
| [Window scrolling](PX%20patch%20history/B10%20-%20window%20scroll%20clicks/README.md) | Reduced clicking when scrolling Start or End across loop boundaries, particularly with short windows. |
| [Sample-end fade](PX%20patch%20history/B5%20-%20sample%20end%20fade/README.md) | Added a 5 ms fade on sample end, including reverse playback. Eliminates clicks caused by stopping at non-zero crossings when looping is disabled. |
| [Center moves window](PX%20patch%20history/B6%20-%20center%20moves%20window/README.md) | Center can now move the Start/End window through the sample instead of being constrained inside it. |
| [Start/End push Center](PX%20patch%20history/B7%20-%20center%20can%20be%20pushed/README.md) | Allows sample Start and End values to push past the Center position instead of being blocked by it. |
| [Window bug](PX%20patch%20history/B7%20-%20center%20can%20be%20pushed/README.md) | Fixed bug where editing both sample layers together could allow Start to move past End and leave the sample window in an invalid state. |
| [Tail retrigger bug](PX%20patch%20history/B8%20-%20end%20escape/README.md) | Fixed bug where increasing End after a held sample had already finished could unexpectedly retrigger the newly exposed tail. |
| [Loop sync divisions](PX%20patch%20history/B16%20-%20new%20sync%20divisions/README.md) | Previously minimum loop sync was 1/16. This has been reduced to allow 1/32 and 1/64. |
| [Preset browsing](PX%20patch%20history/B9%20-%20slow%20preset%20browsing/README.md) | Reduced screen lag when scrolling presets. |
| [Encoder acceleration](PX%20patch%20history/B14%20-%20disable%20encoder%20accel/README.md) | Removed acceleration from all encoders except for sample controls. |
| [Stretch velocity layer](PX%20patch%20history/B15%20-%20stretch%20layer/README.md) | Enabling stretch while a note is held now selects the held velocity layer in addition to its note, and the layer can be changed using the menu as expected. Previously stretch would always choose the highest layer with no way of changing it. |
| [Type encoder](PX%20patch%20history/B11%20-%20type%20name%20tweak/README.md) | Moving the 'type' encoder now starts instruments at entry number 2 if it exists instead of the always-blank entry 1, making it easier to see which types are populated with instrument samples when scrolling. |


## Patching the firmware using the supplied tool:

The [firmware_builder/patch_prophet_x.py](firmware_builder/patch_prophet_x.py) converts your exact factory 2.2.2.0.0 update into the combined 2.2.2.2.2 update. All listed features are included.
The patcher is cross-platform, you just need Python 3.11 or newer.

1. Download and extract the whole repository.
2. Obtain your own exact factory `PxUpdate_V2.2.2.0.0.bin` from Sequential.
3. Copy that firmware file into `firmware_builder/`, alongside `patch_prophet_x.py`.

cd into `PX-RE/firmware_builder`. On macOS or Linux, run:

```sh
python3 patch_prophet_x.py PxUpdate_V2.2.2.0.0.bin -o PxUpdate_V2.2.2.2.2.bin
```

On Windows:

```cmd
py -3 patch_prophet_x.py PxUpdate_V2.2.2.0.0.bin -o PxUpdate_V2.2.2.2.2.bin
```

These commands save `PxUpdate_V2.2.2.2.2.bin` and its verification report inside `firmware_builder/`, alongside the factory file. The synth expects the same filename formatting as the factory firmware bin and will ignore firmware files that are formatted differently. If your Windows installation uses `python` instead of the `py` launcher, substitute `python`.

The command prints four completed stages with timings, then the final filename, size and SHA-256. The [direct builder guide](firmware_builder/direct/README.md) describes the implementation and verification scope.

### Build from source if you do not trust the patcher

You can review and rebuild the update from the feature sources without using the direct firmware patcher. From the repository root, start with the [source build guide](firmware_builder/source_rebuild/README.md), inspect the [orchestrator](firmware_builder/source_rebuild/source_pipeline.py) and the feature implementations it invokes, then run it directly with a new private working directory:

```sh
python3 firmware_builder/source_rebuild/source_pipeline.py firmware_builder/PxUpdate_V2.2.2.0.0.bin -o /path/to/private-workspace/PxUpdate_reviewed.bin --work-dir /path/to/private-workspace/source-build
```

This retains the staged source files, compiler outputs, intermediate packages, validation reports and `build.log` for inspection. This compiler-based audit path is separate from the default direct builder and requires the macOS compiler environment described in its guide. For a manual build, follow the ordered script invocations in `build()` in the orchestrator and review each stage's guards and reports. Independently hash the resulting file using the command below.

The compiler rebuild saves the final update at the path given after `-o`. With `--work-dir`, it also retains the intermediate firmware files, staged sources, compiler outputs, validation reports and `build.log` in that working directory. Before copying the final update to your USB drive, name it exactly `PxUpdate_V2.2.2.2.2.bin` so the synth can recognize it. Verify the final update below, retain your backups, and follow [Sequential's Prophet X update procedure](https://sequential.com/updating-prophet-x-os/) to install it. The factory version requirement applies to the input file used by the patcher; there is no need to install each intermediate project build.

## Why the output is checkable

Unchanged firmware comes from your verified factory input. New helpers come from authored source recipes and 15 pinned compiler objects. Firmware-matching spans are zeroed in the distributed object blobs and restored only from your factory input; source/include hashes, blob hashes and complete restored-object hashes are checked before linking. See the [object provenance and validation details](firmware_builder/direct/README.md).

The direct builder verifies the factory container round trip, relocation bounds, guarded final ownership of every changed byte, ELF/helper layout, all 910 indexed FDE targets, revision gates, record checksums and the unchanged FPGA record. It generates the final payloads once and requires the exact final size and SHA-256 below before saving.

The direct build and the separately retained compiler-based source build reproduce the accepted final package byte for byte. The [documented build history and hardware observations](PX%20patch%20history/BUILD_VERSION_HISTORY.md) describe that firmware. Historical offline reports retain their original test status; feature guides record subsequent observations. The [source build guide](firmware_builder/source_rebuild/README.md) documents the compiler audit path and its historical validation limits.

[Direct verification](firmware_builder/direct/VERIFICATION.json) and the earlier [compiler rebuild receipt](firmware_builder/source_rebuild/VERIFICATION.json) distinguish these runs. [SHA256SUMS](SHA256SUMS) covers published code, object blobs and research evidence; routine guides are excluded from checksum gating so documentation edits do not break CI.

The command publishes a fully written final file without overwriting an existing destination. Temporary output is cleaned up on a reported write failure. If report publication fails after final publication, the validated firmware remains and the command reports failure.

**Matching hashes establish byte identity, not freedom from bugs or authenticity of an untrusted download.** Read the code and obtain the script and expected hashes from a project copy you trust. The documented hardware results describe one user's experience, not exhaustive testing on every instrument. Keep preset/sample backups and a known-good SSD image before installing modified firmware.


## Independently verify the saved file

Compare both the size and SHA-256 with these values. Renaming a file does not change its identity.

| File | Bytes | SHA-256 |
|---|---:|---|
| Factory 2.2.2.0.0 | 3,099,064 | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| Patched 2.2.2.2.2 | 3,187,784 | `488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c` |

This command reads the saved file independently of the patcher. Replace the path with your output path; use `py -3` on Windows:

```sh
python3 -c "import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); b=p.read_bytes(); print('Bytes:',len(b)); print('SHA-256:',hashlib.sha256(b).hexdigest())" /path/to/private-workspace/PxUpdate_V2.2.2.2.2.bin
```

Require **both** final values to match before installation. Repeat the check on the copy placed on the update media. A mismatch means that copy is not the documented final package. A displayed firmware version alone is insufficient: historical experimental builds sometimes reused version numbers.

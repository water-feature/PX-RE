# Prophet X firmware patches and SSD tools

This project documents a set of user-created bugfixes and improvements for the Sequential Prophet X. It includes a local firmware patcher, implementation sources and test evidence for each feature, and a guide detailing how to install a larger SSD. 
  No affiliation with Sequential. 
  No firmware images or extracted payloads are distributed here. 
  Install at your own risk and keep generated firmware images private. 
  LLMs used throughout. 
  Thanks to [rvense](https://rven.se/prophet-x/) for taking the first steps. 

## What is included

- [Direct patcher](firmware_builder/patch_prophet_x.py): python script that generates a flashable firmware file with the changes described in the changelog below.
- [SSD expansion guide](SSD%20expansion/README.md): details on how to prepare and fit a larger SSD.
- [Feature and version history](PX%20patch%20history/README.md): follows the build chain and links to each feature's implementation, test status and packaging evidence.
- [Firmware architecture and map](FIRMWARE_MAP.md): container format, QNX/PIC/FPGA components and version-specific offsets.
- [Contributing](CONTRIBUTING.md): evidence, reproduction and copyright requirements for proposed changes. PRs and bug reports welcome.

### Changelog for PxUpdate_V2.2.2.2.2.bin

| Feature | Description |
|---|---|
| [Voice&nbsp;steal&nbsp;bug](PX%20patch%20history/B1%20-%20voice%20steal%20fix/README.md) | Fixed bug where amp envelope attack was ignored on voice steal, causing a harsh click when sample start was set on a non-zero crossing. |
| [SysEx&nbsp;bug](PX%20patch%20history/B3%20-%20sysex%20channel%20fix/README.md) | Fixed bug where the synth ignored sysex when set to receive midi on any channel but 2 or omni. |
| [Window&nbsp;scroll&nbsp;clicks](PX%20patch%20history/B10%20-%20window%20scroll%20clicks/README.md) | Reduced clicking when scrolling Start or End across loop boundaries, particularly with short windows. |
| [Sample-end&nbsp;fade](PX%20patch%20history/B5%20-%20sample%20end%20fade/README.md) | Added a 5 ms fade on sample end, including reverse playback. Eliminates clicks caused by stopping at non-zero crossings when looping is disabled. |
| [Center&nbsp;moves&nbsp;window](PX%20patch%20history/B6%20-%20center%20moves%20window/README.md) | Center can now move the Start/End window through the sample instead of being constrained inside it. |
| [Start/End&nbsp;push&nbsp;Center](PX%20patch%20history/B7%20-%20center%20can%20be%20pushed/README.md) | Allows sample Start and End values to push the Center position instead of being blocked by it. |
| [Window&nbsp;bug](PX%20patch%20history/B7%20-%20center%20can%20be%20pushed/README.md) | Fixed bug where editing both sample layers together could allow Start to move past End and leave the sample window in an invalid state. |
| [Tail&nbsp;retrigger&nbsp;bug](PX%20patch%20history/B8%20-%20end%20escape/README.md) | Fixed bug where increasing End after a held sample had already finished could unexpectedly retrigger the newly exposed tail. |
| [Loop&nbsp;sync&nbsp;divisions](PX%20patch%20history/B16%20-%20new%20sync%20divisions/README.md) | Previously minimum loop sync was 1/16. This has been reduced to allow 1/32 and 1/64. |
| [Preset&nbsp;browsing&nbsp;lag](PX%20patch%20history/B9%20-%20slow%20preset%20browsing/README.md) | Reduced screen lag when scrolling presets. |
| [Encoder&nbsp;acceleration&nbsp;fix](PX%20patch%20history/B14%20-%20disable%20encoder%20accel/README.md) | Removed acceleration from all encoders except for sample controls. |
| [Stretch&nbsp;velocity&nbsp;layer](PX%20patch%20history/B15%20-%20stretch%20layer/README.md) | Enabling stretch while a note is held now selects the held velocity layer in addition to its note, and the layer can be changed using the menu as expected. Previously stretch would always choose the highest layer with no way of changing it. |
| [Type&nbsp;encoder&nbsp;tweak](PX%20patch%20history/B11%20-%20type%20name%20tweak/README.md) | Moving the 'type' encoder now starts instruments at entry number 2 if it exists instead of the always-blank entry 1, making it easier to see which types are populated with instrument samples when scrolling. |


## Patching the firmware using the supplied tool:

The [firmware_builder/patch_prophet_x.py](firmware_builder/patch_prophet_x.py) converts your exact factory 2.2.2.0.0 update into the combined 2.2.2.2.2 update. All listed features are included.
The patcher is cross-platform, you just need Python 3.11 or newer.

1. Read [RECOVERY.md](RECOVERY.md), open up your synth by following [this video](https://www.youtube.com/watch?v=tF9Ji9iL00g) and create a backup image of your SSD.
2. Download and extract the whole repository.
3. Download the latest factory firmware `PxUpdate_V2.2.2.0.0.bin` from [Sequential](https://sequential.com/support/download/prophet-x-operating-system/).
4. Copy that firmware file into `firmware_builder/`, alongside `patch_prophet_x.py`.
5. In your terminal or Command Prompt, use `cd` to enter the `firmware_builder/` folder.
6. Run the patcher. On macOS or Linux:

   ```sh
   python3 patch_prophet_x.py PxUpdate_V2.2.2.0.0.bin -o PxUpdate_V2.2.2.2.2.bin
   ```

   On Windows:

   ```cmd
   py -3 patch_prophet_x.py PxUpdate_V2.2.2.0.0.bin -o PxUpdate_V2.2.2.2.2.bin
   ```

7. Check that the command completes successfully. It prints four completed stages with timings, then the final filename, size and SHA-256. The update `PxUpdate_V2.2.2.2.2.bin` and its verification report are saved inside `firmware_builder/`, alongside the factory file.
8. Copy the new firmware file to your update USB drive and verify that copy too. Keep the filename exactly `PxUpdate_V2.2.2.2.2.bin`; the synth will ignore firmware files that diverge from this naming scheme.
9. Follow [Sequential's Prophet X update procedure](https://sequential.com/updating-prophet-x-os/) to install it.

## Alternatively: build from source

You can review and rebuild the update from the [feature sources](PX%20patch%20history/README.md) without using the direct firmware patcher. See the [detailed source-build guide](firmware_builder/source_rebuild/README.md) for prerequisites, build stages and validation details. The [source build script](firmware_builder/source_rebuild/source_pipeline.py) runs those stages in order. Copy the factory `PxUpdate_V2.2.2.0.0.bin` into `firmware_builder/`, as in the direct patcher instructions above. In your terminal, use `cd` to enter that folder, then run:

```sh
python3 source_rebuild/source_pipeline.py PxUpdate_V2.2.2.0.0.bin --work-dir source-build
```

The output `PxUpdate_V2.2.2.2.2.bin` is saved in `firmware_builder/`. The new `source-build/` folder retains staged sources, compiler output, intermediate packages, validation reports and `build.log`. Neither the output file nor `source-build/` may already exist; move an earlier run elsewhere before rebuilding.

This build requires the macOS compiler environment described in the source build guide. For a manual build, follow the ordered script invocations in `build()` in `source_pipeline.py` and review each stage's guards and reports. Verify the saved output below, then follow the USB copy and installation steps above.

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

Require **both** final values to match before installation. Repeat the check on the copy placed on the update media. A mismatch means that copy is not the documented final package.

# Contributing

This repository documents a specific Prophet X firmware build and the investigations behind it. Read the [main guide](README.md), [build history](PX%20patch%20history/BUILD_VERSION_HISTORY.md) and relevant feature `README.md` before proposing a change. The [recovery guide](recovery.md) explains the PIC and SSD recovery materials to prepare before hardware testing.

Use a GitHub issue to describe a bug or a proposed improvement. Include the pxupdate version and the steps needed to reproduce. For an implementation change, identify the QNX or PIC payload, the factory or incremental input it expects, patch offsets and byte guards, changed-byte size, and the validation performed. Keep results from rejected experiments distinguishable from the released build. Note that I have not been able to establish whether or not the firmware PIC payload actually has the capability to modify the bootloader, so any further patches should be assessed very carefully before flashing to hardware.

Do not attach or commit Sequential firmware, extracted firmware payloads, recovery images, Ghidra databases containing copyrighted code, or private instrument data. Supply hashes and instructions so a reader can work with a firmware copy obtained independently. Keep generated binaries and personal disk images outside the repository. 

For pull requests, update the affected feature guide and the [build history](PX%20patch%20history/BUILD_VERSION_HISTORY.md) when the feature or version relationship changes. Regenerate the applicable `SHA256SUMS` inventory after editing published files and confirm local Markdown links resolve. State the test environment and outcome precisely; distinguish owner-reported hardware testing from static checks and from tests you ran yourself. A matching checksum proves byte identity, not functional safety.

GitHub Actions verifies the root and feature `SHA256SUMS`, inline local Markdown links and heading anchors, and container parser tests using synthetic data. No firmware or compiler toolchain is needed. CI verifies inventories; it does not regenerate them. External websites are not checked.

Run the link and parser checks locally from the repository root:

```sh
python3 tools/check_links.py
python3 -m unittest discover -s tests -v
```

On Linux, run `sha256sum --check SHA256SUMS` and repeat from each feature directory containing `SHA256SUMS`. On macOS, use `shasum -a 256 --check SHA256SUMS`. The root inventory also checks the feature inventory files themselves.

Contributions must be submitted under [GPL-2.0-or-later](LICENSE). Credit [water-feature](https://github.com/water-feature/) for project material and individual contributors for their own work. By contributing, you confirm that you have the rights needed to submit the material under that license. The project license does not grant rights to manufacturer firmware or other third-party material.

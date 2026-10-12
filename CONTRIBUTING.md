# Contributing

Bug reports, improvements and pull requests are welcome. Start with the [main guide](README.md) and the relevant feature guide in [the build history](PX%20patch%20history/BUILD_VERSION_HISTORY.md).

## Reporting a bug

Open a GitHub issue with your firmware version, file SHA-256, steps to reproduce, and what you expected to happen.

## Proposing a change

Open a GitHub issue to discuss an improvement. Explain the problem you want to solve, your proposed approach and which component it affects.

## Pull requests and firmware modifications

Explain what your changes do. For firmware patches, document the expected input, patch locations, byte guards and validation results. Say which checks you ran, on what system, and whether you tested on hardware.

Update the affected documentation. Update the build history if the feature or firmware version changes. Code, build-input and research changes also need updated `SHA256SUMS` entries; routine guide edits do not. Keep manufacturer firmware, extracted payloads, recovery images, firmware-containing Ghidra databases and personal instrument data out of issues and pull requests. Share hashes and reproduction instructions instead.

Hardware testing has revealed no bootloader-related issues, but the PIC firmware is not fully mapped. Review new patches carefully before installation and prepare the backups described in the [recovery guide](RECOVERY.md). Passing software checks does not establish hardware safety.

For builder changes, see [object provenance and cache maintenance](firmware_builder/direct/README.md#object-provenance-and-maintenance), including how to update cached objects when their sources change.

## Checks

Run these from the repository root before submitting:

```sh
python3 tools/check_checksums.py
python3 tools/check_links.py
python3 -m unittest discover -s tests -v
```

GitHub Actions runs the same checks for checksums, documentation links and synthetic tests.


## License

Contributions are accepted under [GPL-2.0-or-later](LICENSE). Credit the project and contributors whose work you use, and submit only material you have the rights to share. Manufacturer firmware remains subject to its own rights.

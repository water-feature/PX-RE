# B1 PxUpdate packaging

Offline reconstruction PASS: the public application patch specification plus private stock firmware reproduces the hardware-tested voice-only update byte-for-byte. See [verification_report.json](verification_report.json). No new hardware trial was performed.

## Container format

The file starts with `F0`, contains application (type 1), FPGA (type 2), and PIC (type 3) records, and ends with `F7`. Each record has a 12-byte header:

| Relative byte | Meaning |
|---|---|
| 0 | Record type |
| 1 | `7B` |
| 2–6 | Five numeric revision bytes |
| 7 | `7A` |
| 8–11 | Payload length, unsigned big-endian |

The payload follows, then a two-byte checksum trailer. Offsets below are absolute container file offsets; ranges exclude their end.

| Record | Header start | Payload range | Trailer start |
|---|---|---|---|
| Application | `0x1` | `[0xD, 0xF0DA5)` | `0xF0DA5` |
| FPGA | `0xF0DA7` | `[0xF0DB3, 0x273047)` | `0x273047` |
| PIC | `0x273049` | `[0x273055, 0x2F49B5)` | `0x2F49B5` |

## Exact transformation

1. Require the stock package and application candidate hashes pinned in [package_b1.py](package_b1.py).
2. Change candidate ELF file offsets `0x1F4E3` and `0x250EF` from `00` to `02`. These synchronize the compiled updater revision comparison and DSP revision response to 2.2.2.0.2. They are payload-relative offsets, not container offsets. Their individual function attribution is inherited from the B1 analysis; this reconstruction verifies their exact bytes and resulting application identity.
3. Replace the application payload with the versioned candidate. Its length stays 986,520 bytes (`0xF0D98`). Set application header revision bytes at container offsets `0x3..0x7` to `02 02 02 00 02`.
4. Sum all application payload words as unsigned little-endian 16-bit integers, modulo 65,536. Exclude the header and trailer. B1 has an even payload length; this script rejects odd length rather than inventing padding behavior. The result is `0xF44B`; write trailer bytes `4B F4` at `0xF0DA5`.
5. Preserve all other bytes, including complete FPGA and PIC records, their headers and trailers, and outer framing. The PIC trailer is retained verbatim; it is not recomputed using the application algorithm.
6. Require output size 3,099,064 bytes and SHA-256 `2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf`.

## Reproduce locally

Dependencies for the application builder are documented in its [README](../prophet_x_combined_application_patch/analysis/combined_patch/README.md). The packaging script uses only Python's standard library. Supply your own private stock BIN and extracted stock application. Run from this B1 directory, placing generated firmware outside the public repository:

```sh
python3 'prophet_x_combined_application_patch/analysis/combined_patch/build_application_patch.py' --input /private/work/ProphetX.elf --output /private/work/B1_candidate.elf
python3 packaging/package_b1.py --stock /private/work/PxUpdate_V2.2.2.0.0.bin --candidate /private/work/B1_candidate.elf --output /private/work/PxUpdate_V2.2.2.0.2.bin
```

Use actual private paths in place of these examples. The output directory must exist. The packager refuses incorrect input identities, input/output path reuse, and overwriting an existing output. It prints a verification report to stdout. The filename supplied above matches the embedded application revision and established updater naming convention; the script does not infer the revision from arbitrary filenames.

Documentation verification reapplied every expected-byte-guarded span from the public patch specification to stock, checked the candidate hash, packaged it, and compared every output byte with the privately held tested BIN. Four modified/truncated input cases were rejected. This verifies reconstruction of B1, not a general-purpose PxUpdate format implementation or new device acceptance test.

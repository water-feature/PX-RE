# Firmware architecture and map

This is an orientation guide to the structures used by this project, not a complete manufacturer specification. Offsets below were checked against the exact factory **2.2.2.0.0** and accepted modified **2.2.2.2.2** packages. Other builds can have different layouts. No firmware bytes are included here.

For installation, use the [main README](README.md) and [recovery guide](recovery.md). For source locations, see the [directory map](firmware_builder/README.md#directory-map). For ancestry and experiments, see the [build history](PX%20patch%20history/BUILD_VERSION_HISTORY.md).

## Components

| Component | Representation | Role and boundary |
|---|---|---|
| QNX application | Record 1; little-endian x86-64 ELF | SSD-resident ProphetX application, including the sample-processing and control code patched by this project. It is distinct from the SSD's QNX boot image and filesystem. |
| FPGA | Record 2; opaque payload | Retained unchanged by the final build, including its complete container record. This project does not provide an internal FPGA map. |
| PIC controller | Record 3; little-endian MIPS image | Controller firmware, including SysEx handling and UI/control paths patched by this project. Address mapping uses base `0x9D000000`. |
| SSD boot image | `.boot/x86_64-generic.bin` on the SSD | QNX boot environment used to build the separate maintenance VM image. It is not the QNX application ELF extracted from record 1. |

The update `.bin`, MIDI recovery `.syx`, extracted application `.elf`, maintenance VM image and full SSD backup are different artifacts. Renaming one does not convert it into another. See [recovery](recovery.md) and [SSD expansion](SSD%20expansion/README.md) for their separate uses.

## Update container

[container.py](firmware_builder/container.py) is the executable format reference. The accepted files contain one `F0` framing byte, three records in order (kinds 1, 2, 3), and one final `F7` byte. This describes the stored update file, not the complete MIDI transfer protocol.

Each record contains:

| Relative offset | Length | Meaning |
|---|---:|---|
| 0 | 1 | Record kind |
| 1 | 1 | Header marker `0x7B` |
| 2 | 5 | Component revision bytes |
| 7 | 1 | Header marker `0x7A` |
| 8 | 4 | Payload length, big-endian |
| 12 | Variable | Payload |
| 12 + payload length | 2 | Trailer |

For records 1 and 2, the trailer is the sum of little-endian 16-bit payload words, modulo 65536, stored little-endian. Odd payload lengths are rejected. Record 3 preserves the legacy two-byte trailer `30 30` (ASCII `00`), not that word sum. PIC transfer blocks have their own checksums; see the [SysEx implementation and validation guide](PX%20patch%20history/B3%20-%20sysex%20channel%20fix/README.md).

The parser rejects incorrect framing, record order/markers, truncated payloads, invalid trailers and trailing data. These structural checks do not authenticate the image; the builder separately checks its factory and final SHA-256 identities.

## Exact package layout

All offsets in this table are **zero-based byte offsets in the complete update file**, written in decimal. Header offsets identify the first byte of each 12-byte record header. Payload lengths exclude headers and trailers.

| Package | Record | Header offset | Payload offset | Payload bytes | Trailer offset |
|---|---|---:|---:|---:|---:|
| Factory 2.2.2.0.0 | QNX | 1 | 13 | 986,520 | 986,533 |
| Factory 2.2.2.0.0 | FPGA | 986,535 | 986,547 | 1,581,716 | 2,568,263 |
| Factory 2.2.2.0.0 | PIC | 2,568,265 | 2,568,277 | 530,784 | 3,099,061 |
| Modified 2.2.2.2.2 | QNX | 1 | 13 | 1,075,240 | 1,075,253 |
| Modified 2.2.2.2.2 | FPGA | 1,075,255 | 1,075,267 | 1,581,716 | 2,656,983 |
| Modified 2.2.2.2.2 | PIC | 2,656,985 | 2,656,997 | 530,784 | 3,187,781 |

The QNX payload grows by 88,720 bytes. Later container records move accordingly; their offsets must be parsed rather than copied from another build. PIC length is unchanged. FPGA content and its record bytes are unchanged.

| Package | Total bytes | SHA-256 |
|---|---:|---|
| Factory 2.2.2.0.0 | 3,099,064 | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| Modified 2.2.2.2.2 | 3,187,784 | `488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c` |

## Address conventions

### QNX ELF

An ELF virtual address is not generally an offset in the extracted file. For a file-backed `PT_LOAD` segment containing address `va`:

```text
ELF file offset = p_offset + (va - p_vaddr)
Update file offset = record 1 payload offset + ELF file offset
```

The requested byte range must fit inside `p_filesz`. Memory beyond that file-backed range, such as BSS, has no corresponding firmware bytes. A disassembler's chosen image base can introduce another address adjustment; identify its convention before using an address from a report.

Key ELF metadata for the two exact images:

| Field | Factory | Modified final |
|---|---|---|
| ELF entry virtual address | `0x81A0` | `0x81A0` |
| Section-table file offset | 984,152 | 1,072,488 |
| Executable `PT_LOAD`: file offset / virtual address | 0 / 0 | 0 / 0 |
| Executable `PT_LOAD`: file-backed length | 644,224 | 1,069,056 |
| Writable `PT_LOAD`: file offset / virtual address | 647,864 / 2,745,016 | 647,864 / 2,745,016 |
| Writable `PT_LOAD`: file-backed length | 25,048 | 25,048 |

These mappings explain why subtracting one fixed base from every QNX address is incorrect. The final executable mapping also spans added helper areas; mapping coverage alone does not establish that space is unused or safe to patch. Consult the relevant feature's ownership, relocation and unwind checks.

### PIC image

For the mapped PIC image used by these patches:

```text
PIC payload offset = PIC virtual address - 0x9D000000
Update file offset = record 3 payload offset + PIC payload offset
```

Instruction words are stored little-endian. MIPS branch delay slots and address-region rules matter when relocating instructions. A payload offset, a controller virtual address, a container offset and an external-flash staging address are separate coordinate systems.

The [SysEx guide](PX%20patch%20history/B3%20-%20sysex%20channel%20fix/README.md) documents the transfer parser and modeled external-flash staging path. It does not establish general bootloader safety or recovery independence. Do not treat an empty or `FF`-filled region as proof that this project owns it.

## Feature locations and evidence

Patch sites and helper placements depend on the exact parent image, so this overview does not assign permanent free-space ranges. Use the feature guides linked from the [changelog](README.md#changelog-for-22222bin) and [build history](PX%20patch%20history/BUILD_VERSION_HISTORY.md) for offsets, expected parent hashes, guards, allowed writes and test scope.

The [source builder](firmware_builder/source_pipeline.py) stages selected sources, replays the accepted chain, and requires the final package hash before creating the requested output. Hash guards check original spans using the user's supplied firmware. Historical test receipts, checks rerun during a build and owner-reported hardware observations are different kinds of evidence; the [build guide](firmware_builder/README.md) explains their limits.

Displayed versions and container revisions are not sufficient identifiers: some experiments reused versions, and component displays can differ from packaging metadata. Use the whole-package SHA-256 to identify an exact build.

## Inspect your own files

To inspect the exact factory container without producing firmware output:

```sh
python3 firmware_builder/container.py /private/path/PxUpdate_V2.2.2.0.0.bin
```

To compare it with the accepted final image, add `--final /private/path/PxUpdate_V2.2.2.2.2.bin`. This checks both pinned identities and reports record offsets, lengths, component hashes and ELF layout differences. On Windows, use `python` and Windows paths.

To extract a replacement QNX application, use [extract_qnx.py](extract_qnx.py) as documented in [recovery.md](recovery.md#obtain-the-replacement-executable). Extraction does not require the macOS compiler toolchain. Keep firmware inputs and extracted outputs outside this repository.

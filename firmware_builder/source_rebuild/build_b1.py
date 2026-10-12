# SPDX-License-Identifier: GPL-2.0-or-later
"""Rebuild retained B1 from the exact factory update and public patch recipe."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from container import FACTORY_SHA256, Record, elf_layout, parse, serialize, sha256, sum16


HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "PX patch history").is_dir() else HERE.parents[1]
SPEC = (ROOT / "PX patch history/B1 - voice steal fix/"
        "prophet_x_combined_application_patch/analysis/combined_patch/patch_spec.json")
EXPECTED_APP = "651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7"
EXPECTED_PACKAGE = "2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf"


def build(factory: bytes, spec: dict) -> bytes:
    if sha256(factory) != FACTORY_SHA256:
        raise ValueError("factory identity mismatch")
    records = parse(factory)
    source = records[0].payload
    if spec["format"] != 2 or spec["input_sha256"] != sha256(source) or spec["input_size"] != len(source):
        raise ValueError("B1 recipe/source identity mismatch")
    app = bytearray(source)
    owned = set()
    for span in spec["spans"]:
        offset = int(span["offset"], 16)
        after = bytes.fromhex(span["replacement_hex"])
        length = span["size"]
        if length != span["expected_size"] or length != len(after) or offset < 0 or offset + length > len(app):
            raise ValueError("invalid B1 recipe span")
        positions = set(range(offset, offset + length))
        if owned & positions or sha256(app[offset:offset + length]) != span["expected_sha256"]:
            raise ValueError(f"overlap or byte guard failure at {offset:#x}")
        app[offset:offset + length] = after
        owned |= positions
    original_loads = [p for p in elf_layout(source)["programs"] if p["type"] == 1]
    installed_loads = [p for p in elf_layout(app)["programs"] if p["type"] == 1]
    if installed_loads != original_loads:
        raise ValueError("B1 changed ELF load layout")
    for hook in spec["integration_hooks"]:
        site, size = int(hook["site"], 16), hook["size"]
        installed = app[site:site + size]
        if hook["kind"] == "nop":
            if installed != b"\x90" * size:
                raise ValueError("B1 NOP hook mismatch")
        else:
            opcode = 0xe8 if hook["kind"] == "call" else 0xe9
            if installed[0] != opcode or site + 5 + struct.unpack_from("<i", installed, 1)[0] != int(hook["target"], 16):
                raise ValueError("B1 branch hook mismatch")
            if installed[5:] != b"\x90" * (size - 5):
                raise ValueError("B1 hook padding mismatch")
    for offset in (0x1f4e3, 0x250ef):
        if app[offset] != 0:
            raise ValueError("B1 revision guard failed")
        app[offset] = 2
    if sha256(app) != EXPECTED_APP:
        raise ValueError("B1 application hash mismatch")
    revision = bytes((2, 2, 2, 0, 2))
    header = bytearray(records[0].header)
    header[2:7] = revision
    updated = Record(1, records[0].offset, bytes(header), bytes(app), sum16(app).to_bytes(2, "little"))
    package = serialize((updated, records[1], records[2]))
    if sha256(package) != EXPECTED_PACKAGE:
        raise ValueError("B1 package hash mismatch")
    reparsed = parse(package)
    if reparsed[0].payload != app or reparsed[1:] != records[1:]:
        raise ValueError("B1 package re-extraction mismatch")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("factory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.factory.resolve() == args.output.resolve():
        raise ValueError("output must differ from factory")
    package = build(args.factory.read_bytes(), json.loads(SPEC.read_text()))
    with args.output.open("xb") as stream:
        stream.write(package)
    print(json.dumps({"status": "PASS", "size": len(package), "sha256": sha256(package),
                      "source": str(SPEC), "factory_derived": True}, indent=2))


if __name__ == "__main__":
    main()

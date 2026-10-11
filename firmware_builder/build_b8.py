# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile retained B8 sources on the generated B5 application and package .0.6."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from container import Record, parse, serialize, sha256, sum16


HERE = Path(__file__).resolve().parent
SOURCES = HERE / "b8_candidate_work"
B5_SHA = "41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587"
CANDIDATE_SHA = "85b76594924f1a8b7deffec1d81f79feb848edf6c631d0eb2b6c24f49aa393f1"
PACKAGE_SHA = "2cd57a89d0873ad7e81c410748e3725de6a336494f4c6af1e0110aba85b15c95"


def build(b5: bytes) -> bytes:
    if sha256(b5) != B5_SHA:
        raise ValueError("B5 input identity mismatch")
    records = parse(b5)
    base_app = HERE / "b5_packaging_work/b5_packaged_qnx.elf"
    base_app.write_bytes(records[0].payload)
    for script in ("emit_b8.py", "build_b8_candidate.py"):
        subprocess.run([sys.executable, script], cwd=SOURCES, check=True,
                       stdout=subprocess.DEVNULL)
    candidate = (SOURCES / "voice_B1_B5_B8_candidate.elf").read_bytes()
    if sha256(candidate) != CANDIDATE_SHA:
        raise ValueError("compiled B8 application hash mismatch")
    header = bytearray(records[0].header)
    header[2:7] = bytes((2, 2, 2, 0, 6))
    header[8:12] = len(candidate).to_bytes(4, "big")
    updated = Record(1, records[0].offset, bytes(header), candidate,
                     sum16(candidate).to_bytes(2, "little"))
    package = serialize((updated, records[1], records[2]))
    if sha256(package) != PACKAGE_SHA:
        raise ValueError("B8 package hash mismatch")
    extracted = parse(package)
    if (extracted[0].payload != candidate or
            any(a.encode() != b.encode() for a, b in zip(extracted[1:], records[1:]))):
        raise ValueError("B8 package re-extraction mismatch")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("b5", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.b5.resolve():
        raise ValueError("output must differ from input")
    package = build(args.b5.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(package)
    print(json.dumps({"status": "PASS", "size": len(package), "sha256": sha256(package),
                      "source_compiled": True, "source_dir": str(SOURCES)}, indent=2))


if __name__ == "__main__":
    main()

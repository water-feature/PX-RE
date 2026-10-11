"""Compile retained B5 sources on the B1 application and package .0.5."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from container import Record, parse, serialize, sha256, sum16


HERE = Path(__file__).resolve().parent
SOURCES = HERE / "b5_candidate_work"
B1_SHA = "2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf"
CANDIDATE_SHA = "07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35"
PACKAGE_SHA = "41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587"


def build(b1: bytes) -> bytes:
    if sha256(b1) != B1_SHA:
        raise ValueError("B1 input identity mismatch")
    records = parse(b1)
    base_app = HERE / "voice_2.2.2.0.2_qnx.elf"
    base_app.write_bytes(records[0].payload)
    # The branch assembler, C compilation, relocation, ELF placement, and
    # independent structural validator run in an isolated private copy.
    for script in ("emit_b5_objects.py", "build_b5_candidate.py"):
        subprocess.run([sys.executable, script], cwd=SOURCES, check=True,
                       stdout=subprocess.DEVNULL)
    candidate = (SOURCES / "voice_2.2.2.0.2_qnx_B5_candidate.elf").read_bytes()
    if sha256(candidate) != CANDIDATE_SHA:
        raise ValueError("compiled B5 application hash mismatch")
    header = bytearray(records[0].header)
    header[2:7] = bytes((2, 2, 2, 0, 5))
    header[8:12] = len(candidate).to_bytes(4, "big")
    updated = Record(1, records[0].offset, bytes(header), candidate,
                     sum16(candidate).to_bytes(2, "little"))
    package = serialize((updated, records[1], records[2]))
    if sha256(package) != PACKAGE_SHA:
        raise ValueError("B5 package hash mismatch")
    extracted = parse(package)
    if (extracted[0].payload != candidate or
            any(a.encode() != b.encode() for a, b in zip(extracted[1:], records[1:]))):
        raise ValueError("B5 package re-extraction mismatch")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("b1", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.b1.resolve():
        raise ValueError("output must differ from input")
    package = build(args.b1.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(package)
    print(json.dumps({"status": "PASS", "size": len(package), "sha256": sha256(package),
                      "source_compiled": True, "source_dir": str(SOURCES)}, indent=2))


if __name__ == "__main__":
    main()

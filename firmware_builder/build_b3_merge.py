"""Apply the public B3 PIC recipe to generated B8 and reproduce merged .0.7."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from container import Record, parse, serialize, sha256, sum16


B8_SHA = "2cd57a89d0873ad7e81c410748e3725de6a336494f4c6af1e0110aba85b15c95"
FINAL_SHA = "2fe41c83415c1d85efd7848a31511157162528ec4a83d08045be7e8bcee2e753"
PIC_SHA = "2f746346fa1e592795fd243a9866a8019e69c2d97ab3d674204bb7f5022ef0cc"
WORDS = {
    0x295b0: (0x0f417b93, 0x0b400480),
    0x1200: (0xffffffff, 0x90a30005),
    0x1204: (0xffffffff, 0x386300f0),
    0x1208: (0xffffffff, 0x10600003),
    0x120c: (0xffffffff, 0x00001021),
    0x1210: (0xffffffff, 0x0f417b93),
    0x1214: (0xffffffff, 0x90a40004),
    0x1218: (0xffffffff, 0x0b40a56e),
    0x121c: (0xffffffff, 0),
    0x258b4: (0x24842220, 0x24842221),
    0x51bc4: (0x24842220, 0x24842221),
}


def build(b8: bytes) -> bytes:
    if sha256(b8) != B8_SHA:
        raise ValueError("B8 input identity mismatch")
    rows = parse(b8)
    app, pic = bytearray(rows[0].payload), bytearray(rows[2].payload)
    for offset, (before, after) in WORDS.items():
        if struct.unpack_from("<I", pic, offset)[0] != before:
            raise ValueError(f"B3 PIC guard failed at {offset:#x}")
        struct.pack_into("<I", pic, offset, after)
    if sha256(pic) != PIC_SHA:
        raise ValueError("B3 PIC recipe hash mismatch")
    # The accepted .0.7 merge applies three additional PIC display/revision
    # words to the PIC implementation and advances only two QNX version bytes.
    for offset, before, after in ((0x258b4, 0x24842221, 0x24842230),
                                  (0x51bc4, 0x24842221, 0x24842230),
                                  (0x52fec, 0x24020002, 0x24020003)):
        if struct.unpack_from("<I", pic, offset)[0] != before:
            raise ValueError(f"B3 merge PIC guard failed at {offset:#x}")
        struct.pack_into("<I", pic, offset, after)
    for offset in (0x1f4e3, 0x250ef):
        if app[offset] != 2:
            raise ValueError("B3 merge QNX revision guard failed")
        app[offset] = 7
    ah, ph = bytearray(rows[0].header), bytearray(rows[2].header)
    ah[2:7] = bytes((2, 2, 2, 0, 7))
    ph[2:7] = bytes((2, 2, 3, 0, 0))
    updated_app = Record(1, rows[0].offset, bytes(ah), bytes(app), sum16(app).to_bytes(2, "little"))
    updated_pic = Record(3, rows[2].offset, bytes(ph), bytes(pic), rows[2].trailer)
    package = serialize((updated_app, rows[1], updated_pic))
    if sha256(package) != FINAL_SHA:
        raise ValueError("B3 merged package hash mismatch")
    recovered = parse(package)
    if (recovered[0].payload != app or recovered[2].payload != pic or
            recovered[1].encode() != rows[1].encode()):
        raise ValueError("B3 merge re-extraction mismatch")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("b8", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.b8.resolve() == args.output.resolve():
        raise ValueError("output must differ from input")
    package = build(args.b8.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(package)
    print(json.dumps({"status": "PASS", "size": len(package), "sha256": sha256(package),
                      "source_recipe": "B3 public build/combined_0_7"}, indent=2))


if __name__ == "__main__":
    main()

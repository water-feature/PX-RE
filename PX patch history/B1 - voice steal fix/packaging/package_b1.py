# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce B1 PxUpdate using privately supplied stock firmware and B1 candidate."""
import argparse
import hashlib
import json
from pathlib import Path

STOCK = "a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9"
CANDIDATE = "a47fa006e7f179b5860ff4e8d7e268dc3e5136c6e5cec3a7ec85087afe9e6b02"
OUTPUT = "2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf"
APP = "651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def records(data):
    require(data[:1] == b"\xf0" and data[-1:] == b"\xf7", "Invalid framing")
    result = []
    pos = 1
    for kind in (1, 2, 3):
        header = data[pos:pos + 12]
        require(len(header) == 12 and header[0] == kind and header[1] == 0x7b
                and header[7] == 0x7a, "Invalid record header")
        size = int.from_bytes(header[8:12], "big")
        end = pos + 12 + size
        require(end + 2 <= len(data) - 1, "Truncated record")
        result.append((pos, pos + 12, end, end + 2))
        pos = end + 2
    require(pos == len(data) - 1, "Unexpected trailing content")
    return result

def package(stock, candidate):
    require(sha(stock) == STOCK and len(stock) == 3099064, "Stock identity mismatch")
    require(sha(candidate) == CANDIDATE and len(candidate) == 986520,
            "Candidate identity mismatch")
    spans = records(stock)
    start, payload, end, record_end = spans[0]
    require((start, payload, end) == (1, 13, 0xf0da5), "Application layout mismatch")
    app = bytearray(candidate)
    for offset in (0x1f4e3, 0x250ef):
        require(app[offset] == 0, "Unexpected revision byte")
        app[offset] = 2
    require(sha(app) == APP, "Versioned application identity mismatch")
    require(len(app) % 2 == 0, "B1 payload must contain complete 16-bit words")
    checksum = sum(int.from_bytes(app[i:i + 2], "little")
                   for i in range(0, len(app), 2)) & 0xffff
    require(checksum == 0xf44b, "Application checksum mismatch")
    output = bytearray(stock)
    output[start + 2:start + 7] = bytes((2, 2, 2, 0, 2))
    output[payload:end] = app
    output[end:record_end] = checksum.to_bytes(2, "little")
    require(records(output) == spans, "Record boundaries changed")
    preserved = {}
    for label, (rstart, _, _, rend) in zip(("FPGA", "PIC"), spans[1:]):
        require(output[rstart:rend] == stock[rstart:rend], label + " record changed")
        preserved[label] = {"complete_record_sha256": sha(stock[rstart:rend]),
                            "byte_identical_to_stock": True}
    require(sha(output) == OUTPUT, "Final update identity mismatch")
    return bytes(output), {"status": "PASS", "stock_sha256": STOCK,
        "candidate_sha256": CANDIDATE, "versioned_application_sha256": APP,
        "output_sha256": OUTPUT, "output_size": len(output),
        "revision": "2.2.2.0.2", "application_checksum": "0xF44B",
        "preserved_records": preserved,
        "scope": "Offline deterministic packaging; no new hardware trial"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(args.output.resolve() not in (args.stock.resolve(), args.candidate.resolve()),
            "Output must differ from inputs")
    output, report = package(args.stock.read_bytes(), args.candidate.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(output)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()

# SPDX-License-Identifier: GPL-2.0-or-later
"""Inspect and losslessly repack Prophet X update containers.

This build component stores no firmware bytes and accepts only
the exact factory update identified below when used for a null repack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


FACTORY_SHA256 = "a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9"
FINAL_SHA256 = "488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sum16(data: bytes) -> int:
    if len(data) % 2:
        raise ValueError("odd payload length")
    return sum(int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)) & 0xffff


@dataclass(frozen=True)
class Record:
    kind: int
    offset: int
    header: bytes
    payload: bytes
    trailer: bytes

    @property
    def payload_offset(self) -> int:
        return self.offset + len(self.header)

    @property
    def trailer_offset(self) -> int:
        return self.payload_offset + len(self.payload)

    def encode(self) -> bytes:
        if len(self.header) != 12 or len(self.trailer) != 2:
            raise ValueError("invalid record field length")
        if int.from_bytes(self.header[8:12], "big") != len(self.payload):
            raise ValueError("header payload length mismatch")
        return self.header + self.payload + self.trailer


def parse(data: bytes) -> tuple[Record, Record, Record]:
    if data[:1] != b"\xf0" or data[-1:] != b"\xf7":
        raise ValueError("invalid SysEx framing")
    cursor = 1
    records = []
    for kind in (1, 2, 3):
        header = data[cursor:cursor + 12]
        if (len(header) != 12 or header[0] != kind or header[1] != 0x7b
                or header[7] != 0x7a):
            raise ValueError(f"invalid record {kind} header at {cursor}")
        length = int.from_bytes(header[8:12], "big")
        end = cursor + 12 + length
        if end + 2 > len(data) - 1:
            raise ValueError(f"truncated record {kind}")
        payload = data[cursor + 12:end]
        trailer = data[end:end + 2]
        if kind in (1, 2) and trailer != sum16(payload).to_bytes(2, "little"):
            raise ValueError(f"record {kind} checksum mismatch")
        if kind == 3 and trailer != b"00":
            raise ValueError("unexpected PIC legacy trailer")
        records.append(Record(kind, cursor, header, payload, trailer))
        cursor = end + 2
    if cursor != len(data) - 1:
        raise ValueError("unexpected trailing bytes")
    return tuple(records)


def serialize(records: tuple[Record, Record, Record]) -> bytes:
    return b"\xf0" + b"".join(row.encode() for row in records) + b"\xf7"


def elf_layout(data: bytes) -> dict:
    """Read enough ELF64 little-endian metadata to audit PX application placement."""
    if data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("application is not little-endian ELF64")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    section_size, section_count, names_index = struct.unpack_from("<HHH", data, 58)
    program_offset = struct.unpack_from("<Q", data, 32)[0]
    program_size, program_count = struct.unpack_from("<HH", data, 54)
    if section_size != 64 or program_size != 56:
        raise ValueError("unexpected ELF descriptor sizes")
    if section_offset + section_count * section_size > len(data):
        raise ValueError("section table exceeds payload")
    if program_offset + program_count * program_size > len(data):
        raise ValueError("program table exceeds payload")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, section_offset + i * 64)
                for i in range(section_count)]
    if names_index >= section_count:
        raise ValueError("invalid section name index")
    names_row = sections[names_index]
    names = data[names_row[4]:names_row[4] + names_row[5]]
    result = {}
    for row in sections:
        name = names[row[0]:].split(b"\0", 1)[0].decode("ascii")
        if row[1] != 8 and row[4] + row[5] > len(data):
            raise ValueError(f"section {name} exceeds payload")
        result[name] = {"type": row[1], "address": row[3],
                        "offset": row[4], "size": row[5]}
    programs = []
    for i in range(program_count):
        row = struct.unpack_from("<IIQQQQQQ", data, program_offset + i * 56)
        if row[2] + row[5] > len(data):
            raise ValueError(f"program segment {i} exceeds payload")
        programs.append({"type": row[0], "flags": row[1], "offset": row[2],
                         "address": row[3], "file_size": row[5],
                         "memory_size": row[6]})
    return {"section_table_offset": section_offset, "section_count": section_count,
            "sections": result, "programs": programs}


def describe(data: bytes) -> dict:
    records = parse(data)
    return {
        "size": len(data), "sha256": sha256(data),
        "records": [
            {"kind": row.kind, "offset": row.offset,
             "revision": list(row.header[2:7]),
             "payload_offset": row.payload_offset,
             "payload_size": len(row.payload),
             "payload_sha256": sha256(row.payload),
             "trailer_offset": row.trailer_offset,
             "trailer_hex": row.trailer.hex()}
            for row in records
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("factory", type=Path)
    parser.add_argument("--final", type=Path, help="private accepted reference for structural comparison")
    parser.add_argument("--null-output", type=Path, help="write a byte-identical factory repack")
    args = parser.parse_args()
    factory = args.factory.read_bytes()
    if sha256(factory) != FACTORY_SHA256:
        raise ValueError("factory SHA-256 mismatch")
    rows = parse(factory)
    repacked = serialize(rows)
    if repacked != factory:
        raise ValueError("factory null repack differs")
    report = {"factory": describe(factory), "null_repack_byte_identical": True}
    if args.null_output:
        if args.null_output.resolve() == args.factory.resolve():
            raise ValueError("output must differ from input")
        with args.null_output.open("xb") as stream:
            stream.write(repacked)
    if args.final:
        final = args.final.read_bytes()
        if sha256(final) != FINAL_SHA256:
            raise ValueError("final SHA-256 mismatch")
        target = parse(final)
        if rows[1].encode() != target[1].encode():
            raise ValueError("FPGA record changed")
        if len(rows[2].payload) != len(target[2].payload):
            raise ValueError("PIC record size changed")
        report["final"] = describe(final)
        report["application_growth"] = len(target[0].payload) - len(rows[0].payload)
        report["fpga_record_unchanged"] = True
        old_app, new_app = rows[0].payload, target[0].payload
        old_elf, new_elf = elf_layout(old_app), elf_layout(new_app)
        report["elf"] = {
            "factory_section_count": old_elf["section_count"],
            "final_section_count": new_elf["section_count"],
            "factory_section_table_offset": old_elf["section_table_offset"],
            "final_section_table_offset": new_elf["section_table_offset"],
            "added_sections": {
                name: section for name, section in new_elf["sections"].items()
                if name not in old_elf["sections"]
            },
            "changed_original_sections": {
                name: {"factory": section, "final": new_elf["sections"][name]}
                for name, section in old_elf["sections"].items()
                if name in new_elf["sections"] and section != new_elf["sections"][name]
            },
            "factory_programs": old_elf["programs"],
            "final_programs": new_elf["programs"],
            "aligned_application_changed_bytes": sum(a != b for a, b in zip(old_app, new_app)),
            "pic_changed_bytes": sum(a != b for a, b in zip(rows[2].payload, target[2].payload)),
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

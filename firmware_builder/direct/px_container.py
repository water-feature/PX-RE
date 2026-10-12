# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure container parser/serializer extracted from reviewed container.py."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sum16(data: bytes) -> int:
    if len(data) % 2:
        raise ValueError('odd payload length')
    return sum((int.from_bytes(data[i:i + 2], 'little') for i in range(0, len(data), 2))) & 65535

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
            raise ValueError('invalid record field length')
        if int.from_bytes(self.header[8:12], 'big') != len(self.payload):
            raise ValueError('header payload length mismatch')
        return self.header + self.payload + self.trailer

def parse(data: bytes) -> tuple[Record, Record, Record]:
    if data[:1] != b'\xf0' or data[-1:] != b'\xf7':
        raise ValueError('invalid SysEx framing')
    cursor = 1
    records = []
    for kind in (1, 2, 3):
        header = data[cursor:cursor + 12]
        if len(header) != 12 or header[0] != kind or header[1] != 123 or (header[7] != 122):
            raise ValueError(f'invalid record {kind} header at {cursor}')
        length = int.from_bytes(header[8:12], 'big')
        end = cursor + 12 + length
        if end + 2 > len(data) - 1:
            raise ValueError(f'truncated record {kind}')
        payload = data[cursor + 12:end]
        trailer = data[end:end + 2]
        if kind in (1, 2) and trailer != sum16(payload).to_bytes(2, 'little'):
            raise ValueError(f'record {kind} checksum mismatch')
        if kind == 3 and trailer != b'00':
            raise ValueError('unexpected PIC legacy trailer')
        records.append(Record(kind, cursor, header, payload, trailer))
        cursor = end + 2
    if cursor != len(data) - 1:
        raise ValueError('unexpected trailing bytes')
    return tuple(records)

def serialize(records: tuple[Record, Record, Record]) -> bytes:
    return b'\xf0' + b''.join((row.encode() for row in records)) + b'\xf7'

def elf_layout(data: bytes) -> dict:
    """Read enough ELF64 little-endian metadata to audit PX application placement."""
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('application is not little-endian ELF64')
    section_offset = struct.unpack_from('<Q', data, 40)[0]
    section_size, section_count, names_index = struct.unpack_from('<HHH', data, 58)
    program_offset = struct.unpack_from('<Q', data, 32)[0]
    program_size, program_count = struct.unpack_from('<HH', data, 54)
    if section_size != 64 or program_size != 56:
        raise ValueError('unexpected ELF descriptor sizes')
    if section_offset + section_count * section_size > len(data):
        raise ValueError('section table exceeds payload')
    if program_offset + program_count * program_size > len(data):
        raise ValueError('program table exceeds payload')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, section_offset + i * 64) for i in range(section_count)]
    if names_index >= section_count:
        raise ValueError('invalid section name index')
    names_row = sections[names_index]
    names = data[names_row[4]:names_row[4] + names_row[5]]
    result = {}
    for row in sections:
        name = names[row[0]:].split(b'\x00', 1)[0].decode('ascii')
        if row[1] != 8 and row[4] + row[5] > len(data):
            raise ValueError(f'section {name} exceeds payload')
        result[name] = {'type': row[1], 'address': row[3], 'offset': row[4], 'size': row[5]}
    programs = []
    for i in range(program_count):
        row = struct.unpack_from('<IIQQQQQQ', data, program_offset + i * 56)
        if row[2] + row[5] > len(data):
            raise ValueError(f'program segment {i} exceeds payload')
        programs.append({'type': row[0], 'flags': row[1], 'offset': row[2], 'address': row[3], 'file_size': row[5], 'memory_size': row[6]})
    return {'section_table_offset': section_offset, 'section_count': section_count, 'sections': result, 'programs': programs}

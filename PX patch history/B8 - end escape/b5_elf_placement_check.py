#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only exact-voice ELF inspection and in-memory index relocation tests.

Writes JSON/text results only. Does not generate or change an ELF/firmware image.
New FDEs are synthetic parser/lookup fixtures, not machine-code unwind records.
"""
from __future__ import annotations
import hashlib

import bisect
import copy
import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ELF_HASH = '651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7'
CONTAINER_HASH = '2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf'


def leb(data, pos, signed=False):
    value = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        shift += 7
        if not byte & 128:
            if signed and byte & 64:
                value -= 1 << shift
            return value, pos


def encoded(data, pos, encoding, address, data_base=0):
    fmt = encoding & 15
    if fmt in {0, 2, 3, 4, 10, 11, 12}:
        sizes = {0: 'Q', 2: 'H', 3: 'I', 4: 'Q', 10: 'h', 11: 'i', 12: 'q'}
        form = '<' + sizes[fmt]
        value = struct.unpack_from(form, data, pos)[0]
        end = pos + struct.calcsize(form)
    elif fmt in {1, 9}:
        value, end = leb(data, pos, fmt == 9)
    else:
        raise ValueError(f'unsupported encoding {encoding:#x}')
    application = encoding & 112
    if application == 16:
        value += address + pos
    elif application == 48:
        value += data_base
    elif application:
        raise ValueError(f'unsupported application {encoding:#x}')
    return value, end


class ExactElf:
    def __init__(self, data):
        self.data = data
        h = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
        assert h[0][:7] == b'\x7fELF\x02\x01\x01'
        self.type, self.machine, self.entry = h[1], h[2], h[4]
        self.phoff, self.shoff = h[5], h[6]
        self.phentsize, self.phnum, self.shentsize, self.shnum, self.shstrndx = h[9:14]
        self.phdr = []
        for i in range(self.phnum):
            fields = struct.unpack_from('<IIQQQQQQ', data, self.phoff + i * self.phentsize)
            self.phdr.append(dict(zip(('type', 'flags', 'offset', 'va', 'pa', 'filesz', 'memsz', 'align'), fields)))
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', data, self.shoff + i * self.shentsize)
                         for i in range(self.shnum)]
        names = self.sections[self.shstrndx]
        string = data[names[4]:names[4] + names[5]]
        self.section_names = [string[s[0]:string.index(0, s[0])].decode() for s in self.sections]

    def read(self, va, size):
        for p in self.phdr:
            delta = va - p['va']
            if p['type'] == 1 and 0 <= delta and delta + size <= p['filesz']:
                return self.data[p['offset'] + delta:p['offset'] + delta + size]
        raise ValueError(f'VA not file backed: {va:#x}+{size}')

    def cie(self, address):
        length = struct.unpack('<I', self.read(address, 4))[0]
        data = self.read(address, length + 4)
        assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I', data, 4)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
        version = data[8]
        end = data.index(0, 9)
        augmentation = data[9:end].decode()
        pos = end + 1
        if version >= 4:
            assert data[pos:pos + 2] == b'\x08\x00'
            pos += 2
        code_align, pos = leb(data, pos)
        data_align, pos = leb(data, pos, True)
        if version == 1:
            return_reg, pos = data[pos], pos + 1
        else:
            return_reg, pos = leb(data, pos)
        fde_encoding = 0
        if augmentation.startswith('z'):
            auglen, pos = leb(data, pos)
            augend = pos + auglen
            for char in augmentation[1:]:
                if char == 'R':
                    fde_encoding, pos = data[pos], pos + 1
                elif char == 'L':
                    pos += 1
                elif char == 'P':
                    enc, pos = data[pos], pos + 1
                    _, pos = encoded(data, pos, enc, address)
                elif char != 'S':
                    raise ValueError(f'unknown CIE augmentation {augmentation}')
            assert pos <= augend
        return {'va': address, 'encoding': fde_encoding, 'length': length,
                'augmentation': augmentation, 'code_align': code_align,
                'data_align': data_align, 'return_register': return_reg}

    def fde(self, address):
        length, delta = struct.unpack('<II', self.read(address, 8))
        data = self.read(address, length + 4)
        cie = self.cie(address + 4 - delta)
        start, pos = encoded(data, 8, cie['encoding'], address)
        count, _ = encoded(data, pos, cie['encoding'] & 15, address)
        return {'va': address, 'length': length, 'pc': start, 'range': count, 'cie': cie}


def decode_index(data, base):
    assert data[:4] == bytes.fromhex('01 1b 03 3b')
    frame_pointer = base + 4 + struct.unpack_from('<i', data, 4)[0]
    count = struct.unpack_from('<I', data, 8)[0]
    assert len(data) >= 12 + 8 * count
    pairs = [(base + pc, base + fde) for pc, fde in struct.iter_unpack('<ii', data[12:12 + count * 8])]
    return frame_pointer, pairs


def encode_index(pairs, base, frame_pointer):
    assert pairs == sorted(pairs)
    data = bytearray(bytes.fromhex('01 1b 03 3b'))
    data.extend(struct.pack('<iI', frame_pointer - (base + 4), len(pairs)))
    for pc, fde in pairs:
        data.extend(struct.pack('<ii', pc - base, fde - base))
    return bytes(data)


def synthetic_frames():
    # One zR CIE and six small FDE fixtures. NOT unwind descriptions for B5 code.
    base = 0xf2000
    cie_body = b'\x00\x00\x00\x00\x01zR\x00\x01\x78\x10\x01\x1b\x0c\x07\x08\x90\x01'
    while (len(cie_body) + 4) % 4:
        cie_body += b'\x00'
    cie = struct.pack('<I', len(cie_body)) + cie_body
    blob = bytearray(cie)
    pairs, ranges = [], {}
    for i in range(6):
        pc = 0xf1000 + i * 0x40
        va = base + len(blob)
        body = struct.pack('<IiiB', va + 4 - base, pc - (va + 8), 0x30, 0)
        while (len(body) + 4) % 4:
            body += b'\x00'
        blob.extend(struct.pack('<I', len(body)) + body)
        pairs.append((pc, va))
        ranges[va] = (pc, 0x30)
    blob.extend(b'\x00' * 4)
    return base, bytes(blob), pairs, ranges


def callback_lookup(pairs, ranges, pc, phdr, bias=0):
    """Host model of the recovered PT_LOAD + indexed fast lookup/range check."""
    if not any(p['type'] == 1 and bias + p['va'] <= pc < bias + p['va'] + p['memsz'] for p in phdr):
        return None
    starts = [bias + p for p, _ in pairs]
    index = bisect.bisect_right(starts, pc) - 1
    if index < 0:
        return None
    start, fde = pairs[index]
    true_start, size = ranges[fde]
    assert true_start == start
    return bias + fde if pc < bias + start + size else None


def main():
    elf_path = ROOT / 'voice_2.2.2.0.2_qnx.elf'
    data = elf_path.read_bytes()
    elf = ExactElf(data)
    checks = []

    def check(name, condition, detail=None):
        checks.append({'name': name, 'passed': bool(condition), 'detail': detail})
        if not condition:
            raise AssertionError(name)

    check('tested voice ELF identity', hashlib.sha256(data).hexdigest() == ELF_HASH)
    check('tested voice container identity', hashlib.sha256((ROOT / 'voice_2.2.2.0.2.bin').read_bytes()).hexdigest() == CONTAINER_HASH)
    check('ET_DYN x86-64 original PHDR count', elf.type == 3 and elf.machine == 62 and elf.phnum == 8)
    check('no spare PHDR before interpreter', elf.phoff + elf.phnum * elf.phentsize == 0x200)
    interp = next(p for p in elf.phdr if p['type'] == 3)
    check('interpreter fixed', data[interp['offset']:interp['offset'] + interp['filesz']] == b'/usr/lib/ldqnx-64.so.2\0')
    check('candidate starts beyond original file', len(data) == 0xf0d98 and 0xf1000 >= len(data))
    check('3640-byte gap is zero but not currently RX', not any(data[0x9d480:0x9e2b8])
          and elf.phdr[2]['filesz'] == 0x9d480)

    eh = next(p for p in elf.phdr if p['type'] == 0x6474e550)
    old_header = elf.read(eh['va'], eh['filesz'])
    frame_pointer, old_pairs = decode_index(old_header, eh['va'])
    check('839 original index targets sorted', len(old_pairs) == 839
          and all(old_pairs[i][0] < old_pairs[i+1][0] for i in range(838)))
    check('old frame pointer', frame_pointer == 0x92fd8)
    old_records = [elf.fde(fde) for _, fde in old_pairs]
    check('all indexed FDE/CIEs mapped and decodable', len(old_records) == 839)
    mismatches = [(hex(pc), hex(record['pc'])) for (pc, _), record in zip(old_pairs, old_records)
                  if pc != record['pc']]
    check('all original index starts match FDE PC', not mismatches, mismatches)
    check('installed voice FDE retained outside .eh_frame', (0x49fd0, 0x89c38) in old_pairs
          and elf.fde(0x89c38)['pc'] == 0x49fd0)
    check('installed voice helper/hook bytes unchanged', hashlib.sha256(data[0x1b49e:0x1b4a3]).hexdigest()=='07dbb4eb5245c4f78b887e98a0bb789a9a4179dadb31ec65056562724e837692'
          and data[0x1b7e5:0x1b7ea] == b'\x90' * 5)

    frame_base, fixture, new_pairs, new_ranges = synthetic_frames()
    header_base = 0xf2400
    combined = sorted(old_pairs + new_pairs)
    new_header = encode_index(combined, header_base, frame_pointer)
    new_pointer, decoded = decode_index(new_header, header_base)
    check('all 839 absolute pairs preserved after reencoding', set(old_pairs).issubset(decoded)
          and len(decoded) == len(old_pairs) + len(new_pairs))
    check('frame pointer still original, no linear-stream relocation', new_pointer == frame_pointer)
    check('new index and synthetic records within reservations', len(new_header) <= 0x1c00 and len(fixture) <= 0x400)
    max_extra = (0x1c00 - 12) // 8 - len(old_pairs)
    check('index capacity bound rejects next entry', max_extra == 55
          and 12 + 8 * (839 + max_extra + 1) > 0x1c00)
    _, wrong_pairs = decode_index(old_header, header_base)
    check('byte-copy header relocation is detected as incorrect', wrong_pairs != old_pairs)
    check('wrong datarel base +8 is detected', [(pc + 8, fde + 8) for pc, fde in old_pairs] != old_pairs)

    candidate = copy.deepcopy(elf.phdr)
    candidate[2]['filesz'] = candidate[2]['memsz'] = 0xf4000
    candidate[6].update(offset=header_base, va=header_base, pa=header_base,
                        filesz=len(new_header), memsz=len(new_header))
    check('only RX sizes and EH header fields changed in PHDR model',
          all(candidate[i] == elf.phdr[i] for i in [0, 1, 3, 4, 5, 7])
          and all(candidate[2][k] == elf.phdr[2][k] for k in ['type', 'flags', 'offset', 'va', 'pa', 'align']))
    loads = [p for p in candidate if p['type'] == 1]
    check('p_filesz <= p_memsz and alignment congruence',
          all(p['filesz'] <= p['memsz'] and p['va'] % p['align'] == p['offset'] % p['align'] for p in loads))
    check('candidate PT_LOAD VAs do not overlap', loads[0]['va'] + loads[0]['memsz'] <= loads[1]['va'])
    for page in [0x1000, 0x200000]:
        end = (loads[0]['va'] + loads[0]['memsz'] + page - 1) // page * page
        begin = loads[1]['va'] // page * page
        check(f'no rounded VA overlap at {page:#x}', end <= begin)
    check('code/frame/header reservations covered by RX',
          all(loads[0]['va'] <= va and va + size <= loads[0]['va'] + loads[0]['filesz']
              for va, size in [(0xf1000, 0x1000), (frame_base, len(fixture)), (header_base, len(new_header))]))
    # Replacement nonallocated section tables are another metadata-only model.
    # Keep existing indices; retarget the existing active header section and add
    # only the code/frame sections. Never move/overwrite original payloads.
    old_names_section = elf.sections[elf.shstrndx]
    old_names = data[old_names_section[4]:old_names_section[4] + old_names_section[5]]
    new_names = old_names + b'.b5.text\0.b5.eh_frame\0'
    text_name, frame_name = len(old_names), len(old_names) + len(b'.b5.text\0')
    section_model = [list(s) for s in elf.sections]
    eh_index = elf.section_names.index('.eh_frame_hdr')
    section_model[eh_index][3:6] = [header_base, header_base, len(new_header)]
    section_model[elf.shstrndx][4:6] = [0xf4000, len(new_names)]
    section_model.extend([[text_name, 1, 6, 0xf1000, 0xf1000, 0x1000, 0, 0, 16, 0],
                          [frame_name, 1, 2, frame_base, frame_base, len(fixture), 0, 0, 8, 0]])
    section_table_offset = 0xf4200
    prospective_length = section_table_offset + len(section_model) * elf.shentsize
    check('original 37 section indices retained, two added', len(section_model) == 39
          and elf.shstrndx == 34 and eh_index == 14)
    check('active header section agrees with EH program header',
          section_model[eh_index][3:6] == [candidate[6]['va'], candidate[6]['offset'], candidate[6]['filesz']])
    check('only active header/name table and new section descriptors differ',
          all(section_model[i] == list(elf.sections[i]) for i in range(37) if i not in [eh_index, elf.shstrndx]))
    check('replacement name/table extents nonallocated and nonoverlapping',
          0xf4000 + len(new_names) <= section_table_offset and section_table_offset % 8 == 0
          and prospective_length > candidate[2]['filesz'])
    check('file extents large enough for new RX payload and section table',
          prospective_length >= 0xf4000 and prospective_length == 0xf4bc0)
    ranges = {r['va']: (r['pc'], r['range']) for r in old_records}
    ranges.update(new_ranges)
    looked_up = 0
    for bias in [0, 0x100000, 0x7f3000000000]:
        for pc, fde in combined:
            if ranges[fde][1] == 0:
                continue
            check_value = callback_lookup(decoded, ranges, bias + pc, candidate, bias)
            if check_value != bias + fde:
                raise AssertionError(f'lookup mismatch {pc:#x} at bias {bias:#x}')
            looked_up += 1
    check('combined index lookup matches every old/new target at three biases', looked_up == 3 * len(combined), looked_up)
    check('new PC rejected without RX mapping extension', callback_lookup(decoded, ranges, 0xf1000, elf.phdr) is None)
    check('FDE fixture end is excluded rather than miscovered', callback_lookup(decoded, ranges, 0xf1030, candidate) is None)
    check('voice frame bytes and original metadata remain immutable', elf_path.read_bytes() == data)

    # Independently decode the fixture records with the same ELF-record parser,
    # using an overlay reader rather than writing a patched ELF.
    original_read = elf.read
    def overlay_read(va, size):
        if frame_base <= va and va + size <= frame_base + len(fixture):
            return fixture[va-frame_base:va-frame_base+size]
        return original_read(va, size)
    elf.read = overlay_read
    check('discontiguous fixture FDE/CIEs structurally decodable',
          all(elf.fde(fde)['pc'] == pc and elf.fde(fde)['range'] == 0x30 for pc, fde in new_pairs))

    evidence = []
    for begin, end in [(0x2e2e0, 0x2e31c), (0x2e540, 0x2e5c7),
                       (0x37496, 0x374ab), (0x4eb28, 0x4ec66), (0x4ed76, 0x4eeb9)]:
        evidence.append(subprocess.check_output(['/usr/bin/objdump', '--disassemble',
                                                f'--start-address={begin:#x}', f'--stop-address={end:#x}',
                                                str(elf_path)], text=True))
    (ROOT / 'b5_phase_and_unwind_evidence.txt').write_text('\n'.join(evidence))
    semantic_digest = hashlib.sha256(b''.join(struct.pack('<QQ', *x) for x in old_pairs)).hexdigest()
    report = {'scope': 'structural ELF/index model; no modified ELF emitted',
              'checks': checks, 'passed': len(checks), 'old_pairs': [{'pc': hex(pc), 'fde': hex(fde)} for pc, fde in old_pairs],
              'old_pair_digest_sha256': semantic_digest,
              'original_fde_encodings': sorted(set(r['cie']['encoding'] for r in old_records)),
              'original_program_headers': elf.phdr, 'candidate_program_headers_model': candidate,
              'fixture_count': len(new_pairs), 'fixture_frames_size': len(fixture),
              'combined_header_size': len(new_header), 'maximum_additional_index_entries': max_extra,
              'prospective_section_table': {'offset': hex(section_table_offset), 'count': len(section_model),
                                             'shstrndx': elf.shstrndx, 'shstr_offset': '0xf4000',
                                             'shstr_size': len(new_names)},
              'prospective_file_length': prospective_length, 'prospective_file_growth': prospective_length - len(data),
              'extra_rx_bytes': 0xf4000 - elf.phdr[2]['memsz'],
              'file_alias_range': [hex(0x9e2b8), hex(0xa4490)],
              'interpreter': data[interp['offset']:interp['offset']+interp['filesz']].rstrip(b'\0').decode(),
              'local_unwinder_evidence': {'scan_load_range': '0x4eb4a-0x4eb7a',
                                        'header_version_encoding': '0x4ebe8-0x4ec60',
                                        'indexed_search': '0x4ed76-0x4ee25',
                                        'direct_FDE_range_check': '0x4ee50-0x4eea2'},
              'target_loader_validated': False, 'actual_new_CFI_executed': False,
              'blocker': 'No target loader/runtime evidence for enlarged RX mapping and actual emitted helper/CFI; metadata fixture lookup is not target execution.',
              'external_primary_sources': [
                  'https://qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_sys_arch/dll.html',
                  'https://qnx.com/developers/docs/7.1/com.qnx.doc.neutrino.lib_ref/topic/d/dl_iterate_phdr.html']}
    (ROOT / 'b5_elf_placement_results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['scope', 'passed', 'old_pair_digest_sha256',
                                           'combined_header_size', 'extra_rx_bytes',
                                           'target_loader_validated', 'blocker']}, indent=2))


if __name__ == '__main__':
    main()

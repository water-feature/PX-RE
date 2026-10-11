#!/usr/bin/env python3
"""Build PxUpdate_V2.2.2.1.1 trace candidate. Run: python3 -I build_pkg.py"""
import hashlib, struct, sys
from pathlib import Path
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', nargs='?', default='full', choices=('full', 'stamps', 'noop'))
parser.add_argument('--workspace', type=Path, required=True, help='Private directory containing in/voice.elf, in/pkg.bin and work/')
args = parser.parse_args()
MODE = args.mode
S = str(args.workspace.resolve())
Path(S, 'work').mkdir(parents=True, exist_ok=True)

pkg = open(f'{S}/in/pkg.bin', 'rb').read()
elf_new = open(f'{S}/work/voice_trace.elf' if MODE == 'full' else f'{S}/work/voice_trace_{MODE}.elf', 'rb').read()
PKG_SHA = 'ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450'
assert hashlib.sha256(pkg).hexdigest() == PKG_SHA

NEW_REV = bytes([2, 2, 2, 1, 1])
FORBIDDEN = [bytes([2, 2, 2, 1, 3]), bytes([2, 2, 2, 1, 15]), bytes([2, 2, 2, 1, 16])]
assert NEW_REV not in FORBIDDEN

def checksum(payload):
    assert len(payload) % 2 == 0
    s = sum(struct.unpack('<%dH' % (len(payload) // 2), payload)) & 0xffff
    return bytes([s & 0xff, s >> 8])          # little-endian word sum, stored byte-swapped (verified on app+fpga)

def parse(b):
    recs, p = [], 1
    assert b[0] == 0xf0
    while p < len(b) - 1:
        t = b[p]; assert b[p + 1] == 0x7b and b[p + 7] == 0x7a
        ln = int.from_bytes(b[p + 8:p + 12], 'big')
        ps = p + 12
        recs.append(dict(type=t, rev=b[p + 2:p + 7], len=ln, payload=b[ps:ps + ln], trailer=b[ps + ln:ps + ln + 2],
                         raw=b[p:ps + ln + 2]))
        p = ps + ln + 2
    assert p == len(b) - 1 and b[-1] == 0xf7
    return recs

old = parse(pkg)
assert [r['type'] for r in old] == [1, 2, 3]
# the rule must reproduce the original app and fpga trailers before it is trusted
for r in old[:2]:
    assert checksum(r['payload']) == r['trailer'], 'checksum rule does not reproduce original'
assert len(elf_new) == old[0]['len']

app = bytes([1, 0x7b]) + NEW_REV + bytes([0x7a]) + len(elf_new).to_bytes(4, 'big') + elf_new + checksum(elf_new)
out = bytes([0xf0]) + app + old[1]['raw'] + old[2]['raw'] + bytes([0xf7])
assert len(out) == len(pkg)
open(f'{S}/work/PxUpdate_V2.2.2.1.1_boottrace.bin' if MODE == 'full' else f'{S}/work/PxUpdate_V2.2.2.1.1_BISECT_{MODE}.bin', 'wb').write(out)

new = parse(out)
assert new[1]['raw'] == old[1]['raw'] and new[2]['raw'] == old[2]['raw']
assert new[1]['payload'] == old[1]['payload'] and new[2]['payload'] == old[2]['payload']
print('package sha256', hashlib.sha256(out).hexdigest(), 'size', len(out))
print('app    rev', list(new[0]['rev']), 'len', new[0]['len'], 'sha256', hashlib.sha256(new[0]['payload']).hexdigest(), 'trailer', new[0]['trailer'].hex())
print('fpga   rev', list(new[1]['rev']), 'len', new[1]['len'], 'sha256', hashlib.sha256(new[1]['payload']).hexdigest(), 'trailer', new[1]['trailer'].hex())
print('pic    rev', list(new[2]['rev']), 'len', new[2]['len'], 'sha256', hashlib.sha256(new[2]['payload']).hexdigest(), 'trailer', new[2]['trailer'].hex())
# byte diff against the baseline package
diff = [i for i in range(len(pkg)) if pkg[i] != out[i]]
print('differing bytes vs baseline package:', len(diff), 'first', hex(diff[0]), 'last', hex(diff[-1]))
assert diff[0] == 7 or diff[0] <= 13
assert all(i < 13 + len(elf_new) + 2 for i in diff)

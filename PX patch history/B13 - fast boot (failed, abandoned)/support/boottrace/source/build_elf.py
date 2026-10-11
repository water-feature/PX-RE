#!/usr/bin/env python3
"""Build the boot-trace ELF from the exact .15 ELF. Run with: python3 -I build_elf.py
Every patch asserts the original bytes first. File size is unchanged."""
import hashlib, struct, subprocess, sys, json
from pathlib import Path
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', nargs='?', default='full', choices=('full', 'stamps', 'noop'))
parser.add_argument('--workspace', type=Path, required=True, help='Private directory containing in/voice.elf, in/pkg.bin and work/')
args = parser.parse_args()
MODE = args.mode
S = str(args.workspace.resolve())
Path(S, 'work').mkdir(parents=True, exist_ok=True)

SRC = f'{S}/in/voice.elf'
OUT = f'{S}/work/voice_trace.elf' if MODE == 'full' else f'{S}/work/voice_trace_{MODE}.elf'
BASE_SHA = 'dd9efbcd2804e02cc4599e72d2ee90f996facce1fa06f1815a0078270566a2fa'

orig = open(SRC, 'rb').read()
assert hashlib.sha256(orig).hexdigest() == BASE_SHA, 'input ELF is not the .15 baseline'
elf = bytearray(orig)

CODE_BASE = 0x1016d0
EH_BASE = 0x102000          # CIE reused by all earlier FDEs in .b15_eh_frame
EH_NEW = 0x10277c           # first free byte after .b15_eh_frame
HDR = 0x103000
HDR_COUNT_OFF = HDR + 8
HDR_TABLE_END_OLD = HDR + 12 + 909 * 8   # 0x104c74

def zero(a, b):
    assert all(c == 0 for c in orig[a:b]), f'{a:#x}-{b:#x} is not zero in the baseline'

# --- 1. assemble helper -----------------------------------------------------
subprocess.run(['nasm', '-f', 'bin', f'-DCODE_BASE={CODE_BASE:#x}', '-l', 'trace.lst',
                '-I', str(Path(__file__).resolve().parent) + '/', str(Path(__file__).resolve().with_name('trace.asm')), '-o', 'trace.bin'], cwd=f'{S}/work', check=True)
blob = open(f'{S}/work/trace.bin', 'rb').read()
magic = struct.pack('<Q', 0xDEADBEEFCAFEF00D)
assert blob.count(magic) == 1
mo = blob.index(magic)
names = ['stamp', 'flush', 'w_main', 'w_serial_beg', 'w_serial_end', 'w_ctor', 'w_index',
         'w_cache_beg', 'w_preload', 'w_select_end', 'w_fpga_open', 'w_sched', 'w_workers', 'w_stream']
nq = (len(blob) - mo - 8) // 8
labels = struct.unpack_from(f'<{nq}Q', blob, mo + 8)
assert nq == 3 * len(names) + 1
fn = {n: labels[3 * i:3 * i + 3] for i, n in enumerate(names)}
code_end = labels[-1]
code = blob[:code_end - CODE_BASE]
assert fn['stamp'][0] == CODE_BASE
assert CODE_BASE + len(code) <= 0x102000 and CODE_BASE >= 0x1016cb
zero(0x1016cb, 0x102000)
elf[CODE_BASE:CODE_BASE + len(code)] = code

# --- 2. call-site patches ---------------------------------------------------
def rel32(frm_next, to):
    d = to - frm_next
    assert -2**31 <= d < 2**31
    return struct.pack('<i', d)

# (site, window length, wrapper, expected original target for plain calls | exact original bytes)
sites = [
    (0x7d5e, 5, 'w_main',       0x79c0),    # MAIN_ENTRY            call procmgr_ability@plt
    (0x7e25, 5, 'w_serial_beg', 0x4a090),   # SERIAL_BEGIN          call COMPort_Open
    (0x7e2c, 5, 'w_serial_end', 0x4a0d0),   # SERIAL_END            call COMPort_SetRTS
    (0x7e7f, 5, 'w_ctor',       0x15f90),   # CTOR_BEGIN/END        call C1
    (0x161a3, 5, 'w_index',     0x33db0),   # INDEX_BEGIN/END       call IndexSampleGroupFiles
    (0x16353, 5, 'w_cache_beg', 0x34b90),   # CACHE_SETUP_BEGIN     call GetGroupFileInfoCache
    (0x1636a, 5, 'w_preload',   0x356b0),   # PRELOAD_BEGIN/END     call CacheSampleGroups
    (0x163b3, 5, 'w_select_end', 0x7930),   # SELECT_END            call operator new[]
    (0x7ee3, 5, 'w_fpga_open',  {'sha256': '6215cc3e682c29f38d11cd8e01dde3586c998acb6ed426396163423906ed28fa', 'size': 5}),
    (0x7f70, 6, 'w_sched',      {'sha256': '337bcaa950858b9d1b0d6616735fbef1a790c8f31ec0f0fad0d91ada55ae525b', 'size': 6}),
    (0x7f81, 5, 'w_workers',    0x18710),   # WORKERS_BEGIN/END     call StartAudioProcessThreads
    (0x7f89, 6, 'w_stream',     {'sha256': 'fd333c0c54180bdb60b745f267fb62e0a6ac113395776592e6fbe38e4cfea6f1', 'size': 6}),
    (0x7f97, 9, 'flush',        {'sha256': '7916b888b27671144046d6e3198540775731573e9dc9a3aad7f08fb0d8472d36', 'size': 9}),  # LOOP_ENTER, 9-byte NOP pad
]
manifest = []
if MODE == 'noop': sites = []
if MODE == 'stamps': sites = [s for s in sites if s[2] != 'flush']
for a, ln, w, exp in sites:
    cur = bytes(orig[a:a + ln])
    if isinstance(exp, int):
        assert cur[0] == 0xe8, hex(a)
        tgt = a + 5 + struct.unpack('<i', cur[1:5])[0]
        assert tgt == exp, f'{a:#x}: call target {tgt:#x} != {exp:#x}'
    else:
        assert len(cur)==exp['size'] and hashlib.sha256(cur).hexdigest()==exp['sha256'], f'{a:#x}: unexpected bytes {cur.hex()}'
    new = b'\xe8' + rel32(a + 5, fn[w][0]) + b'\x90' * (ln - 5)
    assert len(new) == ln
    elf[a:a + ln] = new
    manifest.append({'site': hex(a), 'len': ln, 'wrapper': w, 'wrapper_addr': hex(fn[w][0]),
                     'old': cur.hex(), 'new': new.hex()})

# --- 3. unwind records ------------------------------------------------------
zero(EH_NEW, HDR)
def uleb_adv(d):
    if d < 64: return bytes([0x40 | d])
    if d < 256: return bytes([0x02, d])
    return bytes([0x03]) + struct.pack('<H', d)

fdes = []
pos = EH_NEW
for n in names:
    s, e, t = fn[n]
    cfi = bytes([0x41, 0x0e, 0x10, 0x86, 0x02,      # after push rbp: CFA=rsp+16, rbp at CFA-16
                 0x43, 0x0d, 0x06])                  # after mov rbp,rsp: CFA=rbp+16
    cfi += uleb_adv(e - (s + 4)) + bytes([0x0c, 0x07, 0x08])   # after pop rbp: CFA=rsp+8
    body = struct.pack('<I', (pos + 4) - EH_BASE)           # CIE pointer -> CIE at 0x102000
    body += struct.pack('<i', s - (pos + 8))                # pc_begin, pcrel sdata4
    body += struct.pack('<I', t - s)                        # pc_range
    body += b'\x00' + cfi                                   # augmentation length 0
    body += b'\x00' * ((-len(body)) % 4)
    ent = struct.pack('<I', len(body)) + body
    elf[pos:pos + len(ent)] = ent
    fdes.append((s, pos))
    pos += len(ent)
assert pos <= HDR, 'eh_frame gap overflow'

# --- 4. eh_frame_hdr table (sorted, new code is above all existing entries) --
cnt = struct.unpack_from('<I', orig, HDR_COUNT_OFF)[0]
assert cnt == 909 and HDR + 12 + cnt * 8 == HDR_TABLE_END_OLD
last_init = struct.unpack_from('<i', orig, HDR + 12 + (cnt - 1) * 8)[0] + HDR
assert last_init < min(s for s, _ in fdes)
zero(HDR_TABLE_END_OLD, 0x105000)
new_tab = b''.join(struct.pack('<ii', s - HDR, f - HDR) for s, f in sorted(fdes))
assert HDR_TABLE_END_OLD + len(new_tab) <= 0x105000
elf[HDR_TABLE_END_OLD:HDR_TABLE_END_OLD + len(new_tab)] = new_tab
struct.pack_into('<I', elf, HDR_COUNT_OFF, cnt + len(fdes))

# --- 5. program headers -----------------------------------------------------
PH = 64
def ph(i): return PH + 56 * i
# RW LOAD (index 3): p_memsz 0x13f08 -> 0x14008  (approved +0x100 exception)
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I', orig, ph(3))[0])).hexdigest()=='67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450' and hashlib.sha256(struct.pack('<Q',struct.unpack_from('<Q', orig, ph(3) + 40)[0])).hexdigest()=='10fe042e5ef611976e2feb2145dc4cc9ed1db3743106d375335d4cb6acbd7a3e'
struct.pack_into('<Q', elf, ph(3) + 40, 0x14008)
# GNU_EH_FRAME (index 6): size follows the longer table
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I', orig, ph(6))[0])).hexdigest()=='0fe51dced2745ee6eab34377ad3e64563eef82533a339cae1c75354d09fd1dd5'
old_sz = struct.unpack_from('<Q', orig, ph(6) + 32)[0]
assert old_sz == 0x1c74 and hashlib.sha256(struct.pack('<Q',struct.unpack_from('<Q', orig, ph(6) + 40)[0])).hexdigest()=='7f02272e90d6c9f977d3facd76caa951be964cfd58e092b1def5e7191839679d'
new_sz = old_sz + len(new_tab)
struct.pack_into('<Q', elf, ph(6) + 32, new_sz)
struct.pack_into('<Q', elf, ph(6) + 40, new_sz)

assert len(elf) == len(orig)
open(OUT, 'wb').write(elf)

# --- report -----------------------------------------------------------------
diff = []
i = 0
while i < len(elf):
    if elf[i] != orig[i]:
        j = i
        while j < len(elf) and (elf[j] != orig[j] or (j + 1 < len(elf) and elf[j + 1] != orig[j + 1] and False)):
            j += 1
        diff.append((i, j)); i = j
    else:
        i += 1
rep = {'out_sha256': hashlib.sha256(elf).hexdigest(), 'size': len(elf),
       'code': f'{CODE_BASE:#x}-{CODE_BASE + len(code):#x} ({len(code)} bytes)',
       'fde_range': f'{EH_NEW:#x}-{pos:#x} ({pos - EH_NEW} bytes, {len(fdes)} FDEs)',
       'hdr_count': f'{cnt} -> {cnt + len(fdes)}', 'hdr_size': f'{old_sz:#x} -> {new_sz:#x}',
       'functions': {n: [hex(x) for x in fn[n]] for n in names},
       'patches': manifest,
       'changed_ranges': [f'{a:#x}-{b:#x}' for a, b in diff]}
json.dump(rep, open(f'{S}/work/build_report_{MODE}.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in rep.items() if k not in ('patches', 'functions')}, indent=1))

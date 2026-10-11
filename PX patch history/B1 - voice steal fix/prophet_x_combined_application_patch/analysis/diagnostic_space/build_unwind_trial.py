# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline unwind-layout trial. Never modifies the input ELF or update package.

Run from any directory. Requires pyelftools and Capstone. Output ELF is a layout
test, NOT installable firmware: the seven integration branches are not applied.
"""
from pathlib import Path
from io import BytesIO
import json, struct, hashlib
from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import CallFrameInfo, FDE
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

P = Path(__file__).resolve().parent
raw = (P.parent / 'ProphetX.elf').read_bytes()
elf = ELFFile(BytesIO(raw))
dwarf = elf.get_dwarf_info()
stock = dwarf.EH_CFI_entries()
POOL, POOL_END = 0x89c18, 0x89d0a
OLD_HDR, NEW_HDR = 0x91598, 0x91590
EH = elf.get_section_by_name('.eh_frame')['sh_addr']
DEBUG_FDE = EH + 0x72e0
CODE_BASE, CODE_END, QUIET = 0x49fd0, 0x4a08d, 0x8fed0
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
text = elf.get_section_by_name('.text')
ins = list(md.disasm(text.data(), text['sh_addr']))
assert ins[-1].address + ins[-1].size == text['sh_addr'] + text['sh_size']

def u(n):
    out = bytearray()
    while n >= 128: out.append((n & 127) | 128); n >>= 7
    out.append(n); return bytes(out)

def read_u(b, p):
    n = s = 0
    while True:
        v = b[p]; p += 1; n |= (v & 127) << s; s += 7
        if v < 128: return n, p

def s32(n): return struct.pack('<i', n)
def rec(body):
    body += bytes((-len(body)) % 4)
    return struct.pack('<I', len(body)) + body
def advance(n):
    return bytes([0x40 + n]) if n < 64 else b'\x02' + bytes([n]) if n < 256 else b'\x03' + struct.pack('<H', n)
def cfa(reg, off): return b'\x0c' + u(reg) + u(off)
def saved(reg, off): return bytes([0x80 + reg]) + u(-off // 8)
def same(reg): return b'\x08' + u(reg)

# Prove the five main() strings are only direct arguments to suppressed logger
# calls. This remains a static-reference audit, not a computed-pointer proof.
targets = {0x89c18, 0x89c48, 0x89c80, 0x89cb0, 0x89ce8}
refs = []
for n, i in enumerate(ins):
    for op in i.operands:
        dest = op.imm if op.type == X86_OP_IMM else i.address + i.size + op.mem.disp if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP else None
        if dest is not None and POOL <= dest < POOL_END:
            assert dest in targets and i.mnemonic == 'lea' and i.op_str.startswith('rsi,'), (hex(i.address), i.op_str)
            following = ins[n+1:n+6]
            call = next(q for q in following if q.mnemonic == 'call')
            assert call.op_str == '0x49fd0'
            assert any(q.mnemonic == 'mov' and q.op_str == 'edi, 5' for q in following)
            refs.append([hex(i.address), hex(dest)])
assert len(refs) == 5 and {int(r[1], 16) for r in refs} == targets
assert raw[NEW_HDR:OLD_HDR] == bytes(8)
for i in ins:
    for op in i.operands:
        dest = op.imm if op.type == X86_OP_IMM else i.address+i.size+op.mem.disp if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP else None
        assert dest is None or not NEW_HDR <= dest < OLD_HDR
for section in elf.iter_sections():
    if section['sh_type'] in ('SHT_RELA', 'SHT_REL'):
        for r in section.iter_relocations():
            a = r.entry.get('r_addend', 0)
            assert not (POOL <= a < POOL_END or NEW_HDR <= a < OLD_HDR)
    if section['sh_flags'] & 2 and not section['sh_flags'] & 4 and section['sh_type'] == 'SHT_PROGBITS':
        b = section.data()
        for off in range((-section['sh_addr']) % 8, len(b)-7, 8):
            a = struct.unpack_from('<Q', b, off)[0]
            assert not (POOL <= a < POOL_END or NEW_HDR <= a < OLD_HDR)

# A jump hook represents the original caller's frame. Ordinary CALL wrappers
# represent a separate rsp+8 frame. Copy saved-register rules from stock CFI.
def stock_row(a):
    x = next(x for x in stock if isinstance(x, FDE) and x['initial_location'] <= a < x['initial_location'] + x['address_range'])
    # pyelftools cannot decode GNU_args_size; it doesn't affect register/CFA
    # rules. Remove only that opcode for this inspection.
    x.instructions = [i for i in x.instructions if 'GNU_args_size' not in str(i.opcode)]
    return x, [r for r in x.get_decoded().table if r['pc'] <= a][-1]
handle, hr = stock_row(0x215b8)
_, cr = stock_row(0x1b49e)
assert (hr['cfa'].reg, hr['cfa'].offset) == (6, 16)
assert (cr['cfa'].reg, cr['cfa'].offset) == (7, 128)
regs = [3, 6, 12, 13, 14, 15]
hook_cfi = advance(0x49fe6 - CODE_BASE) + cfa(6, 16)
hook_cfi += b''.join(saved(r, hr[r].arg) for r in regs)
hook_cfi += advance(0x4a066 - 0x49fe6) + cfa(7, 8) + b''.join(same(r) for r in regs)
hook_cfi += advance(0x4a071 - 0x4a066) + cfa(7, 128) + b''.join(saved(r, cr[r].arg) for r in regs)

quiet_blob = (P / 'quiet_code.bin').read_bytes()
qi = list(md.disasm(quiet_blob, QUIET))
quiet_cfi = b''; last = QUIET; depth = 8
regnum = {'rbx': 3, 'r12': 12, 'r13': 13}
for i in qi:
    if i.mnemonic in ('push', 'pop'):
        end = i.address + i.size
        quiet_cfi += advance(end-last); last = end
        if i.mnemonic == 'push':
            depth += 8; quiet_cfi += cfa(7, depth) + saved(regnum[i.op_str], -depth)
        else:
            depth -= 8; quiet_cfi += cfa(7, depth) + same(regnum[i.op_str])
assert depth == 8

# HandleMessage has a real cleanup landing pad. Preserve it for the two new
# calls executing in its frame; dropping the personality/LSDA would skip it.
# Original mutex-lock call's landing pad is a jump to common cleanup 0x241a7.
lsda = handle.lsda_pointer
p = lsda
assert raw[p:p+3] == b'\xff\xff\x01'; p += 3
length, p = read_u(raw, p); end = p + length; original_sites = []
while p < end:
    values = []
    for _ in range(4): v, p = read_u(raw, p); values.append(v)
    original_sites.append(values)
source = next(v for v in original_sites if v[0] <= 0x2174c-0x1e050 < v[0]+v[1])
assert source[3] == 0
landing = 0x1e050 + source[2]
assert raw[landing] == 0xe9 and landing + 5 + struct.unpack_from('<i', raw, landing+1)[0] == 0x241a7
hook_blob = (P / 'hooks_code.bin').read_bytes()
hi = list(md.disasm(hook_blob, 0x49fd4))
calls = [i for i in hi if i.mnemonic == 'call']
assert len(calls) == 3
call_table = b''
for i in calls:
    lp = source[2] if i.address < 0x4a066 else 0
    call_table += u(i.address-CODE_BASE) + u(i.size) + u(lp) + u(0)
# LPStart pcrel sdata4 gives original function base for landing-pad offsets;
# call-site offsets remain relative to the new FDE's initial_location.
lsda_size = 1+4+1+1+len(u(len(call_table)))+len(call_table)

# Reuse the original personality's *indirect pointer slot*, not an absolute
# function address, preserving PIE relocation behavior (encoding 0x9b).
cie = handle.cie
personality_field = EH + cie.offset + 19
assert raw[personality_field-1] == 0x9b
personality_slot = personality_field + struct.unpack_from('<i', raw, personality_field)[0]
cie_body = struct.pack('<I', 0) + b'\x01zPLR\x00\x01\x78\x10\x07\x9b'
new_personality_field = POOL + 4 + len(cie_body)
cie_body += s32(personality_slot-new_personality_field) + b'\x1b\x1b' + cfa(7, 8) + saved(16, -8)
new_cie = rec(cie_body)
assert len(new_cie) == 32

def fde(address, start, size, cfi, lsda_address):
    body = struct.pack('<I', address+4-POOL) + s32(start-(address+8)) + struct.pack('<I', size)
    body += b'\x04' + (s32(lsda_address-(address+17)) if lsda_address else bytes(4)) + cfi
    return rec(body)

hook_fde_address = POOL + len(new_cie)
tmp_hook = fde(hook_fde_address, CODE_BASE, CODE_END-CODE_BASE, hook_cfi, 0)
quiet_fde_address = hook_fde_address + len(tmp_hook)
quiet_fde = fde(quiet_fde_address, QUIET, len(quiet_blob), quiet_cfi, 0)
cfi_bytes = len(new_cie)+len(tmp_hook)+len(quiet_fde)
lsda_address = POOL + cfi_bytes + 4  # zero terminator for independent CFI parsing
new_lsda = b'\x1b' + s32(0x1e050-(lsda_address+1)) + b'\xff\x01' + u(len(call_table)) + call_table
assert len(new_lsda) == lsda_size
hook_fde = fde(hook_fde_address, CODE_BASE, CODE_END-CODE_BASE, hook_cfi, lsda_address)
metadata = new_cie + hook_fde + quiet_fde + bytes(4) + new_lsda
assert len(metadata) <= POOL_END-POOL

# Parse the generated records independently; compare CFA/register rules at
# every instruction boundary to intended frames, including each push/pop.
entries = CallFrameInfo(BytesIO(metadata[:cfi_bytes+4]), cfi_bytes+4, POOL, dwarf.structs, True).get_entries()
new_fdes = [x for x in entries if isinstance(x, FDE)]
assert len(new_fdes) == 2
assert new_fdes[0].lsda_pointer == lsda_address
assert entries[0].augmentation_dict['personality']['function'] + new_personality_field == personality_slot
def row(x, pc): return [r for r in x.get_decoded().table if r['pc'] <= pc][-1]
checks = 0
for i in list(md.disasm((P/'debug_stub.bin').read_bytes(), CODE_BASE)) + hi:
    r = row(new_fdes[0], i.address)
    expected = hr if 0x49fe6 <= i.address < 0x4a066 else cr if i.address >= 0x4a071 else None
    assert (r['cfa'].reg, r['cfa'].offset) == ((expected['cfa'].reg, expected['cfa'].offset) if expected else (7,8))
    for reg in regs:
        if expected: assert r[reg].type == 'OFFSET' and r[reg].arg == expected[reg].arg
        else: assert reg not in r or r[reg].type == 'SAME_VALUE'
    checks += 1
depth = 8; live = {}
for i in qi:
    r = row(new_fdes[1], i.address)
    assert (r['cfa'].reg, r['cfa'].offset) == (7, depth)
    for reg, off in live.items(): assert r[reg].type == 'OFFSET' and r[reg].arg == off
    checks += 1
    if i.mnemonic == 'push': depth += 8; live[regnum[i.op_str]] = -depth
    if i.mnemonic == 'pop': depth -= 8; del live[regnum[i.op_str]]

# Insert one additional lookup entry by moving the header into eight verified
# zero padding bytes. Rebase every data-relative table value to its new base.
hdr = elf.get_section_by_name('.eh_frame_hdr')
old_size = hdr['sh_size']; assert raw[OLD_HDR:OLD_HDR+4] == b'\x01\x1b\x03\x3b'
count = struct.unpack_from('<I', raw, OLD_HDR+8)[0]
assert old_size == 12+8*count
table = []
for j in range(count):
    start, ptr = struct.unpack_from('<ii', raw, OLD_HDR+12+j*8)
    table.append((OLD_HDR+start, OLD_HDR+ptr))
assert (CODE_BASE, DEBUG_FDE) in table
table = [(a, hook_fde_address if a == CODE_BASE else b) for a,b in table]
table.append((QUIET, quiet_fde_address)); table.sort()
new_header = b'\x01\x1b\x03\x3b' + s32(EH-(NEW_HDR+4)) + struct.pack('<I', len(table))
new_header += b''.join(s32(a-NEW_HDR)+s32(b-NEW_HDR) for a,b in table)
assert NEW_HDR+len(new_header) == OLD_HDR+old_size
trial = bytearray(raw); spans = []
def put(offset, b, why):
    before = raw[offset:offset+len(b)]
    trial[offset:offset+len(b)] = b
    spans.append({'offset':hex(offset), 'size':len(b), 'reason':why, 'expected_sha256':hashlib.sha256(before).hexdigest(), 'expected_size':len(before), 'replacement_hex':b.hex()})
put(POOL, metadata, 'new CIE, hook/quiet FDEs, and translated cleanup LSDA')
put(NEW_HDR, new_header, 'rebased lookup header with one new helper entry')
# Keep the original FDE valid for linear scans, but restrict it to the stub.
old = bytearray(raw[DEBUG_FDE:DEBUG_FDE+40]); old[12:16] = struct.pack('<I',4); old[17:] = bytes(23)
put(DEBUG_FDE, bytes(old), 'remove stale DebugPrintf stack rules; stub range only')
for idx, seg in enumerate(elf.iter_segments()):
    if seg['p_type'] == 'PT_GNU_EH_FRAME':
        off = elf['e_phoff'] + idx*elf['e_phentsize']
        h = bytearray(raw[off:off+56])
        struct.pack_into('<QQQQQ', h, 8, NEW_HDR, NEW_HDR, NEW_HDR, len(new_header), len(new_header))
        put(off,bytes(h),'point runtime unwind header at relocated table')
for idx, sec in enumerate(elf.iter_sections()):
    off = elf['e_shoff'] + idx*elf['e_shentsize']
    if sec.name == '.rodata': put(off+32, struct.pack('<Q', sec['sh_size']-8),'exclude consumed trailing padding')
    if sec.name == '.eh_frame_hdr': put(off+16, struct.pack('<QQQ', NEW_HDR, NEW_HDR, len(new_header)),'describe relocated header for ELF tools')
for a, name in [(CODE_BASE,'debug_stub.bin'),(0x49fd4,'hooks_code.bin'),(QUIET,'quiet_code.bin')]: put(a,(P/name).read_bytes(),'placement code trial')
assert len(trial) == len(raw)
(P/'unwind_layout_trial.elf').write_bytes(trial)
(P/'unwind_metadata.bin').write_bytes(metadata)
result = {'input_sha256':hashlib.sha256(raw).hexdigest(), 'metadata_address':hex(POOL), 'metadata_bytes':len(metadata), 'pool_capacity':POOL_END-POOL, 'header_growth':8, 'header_entries_before':count, 'header_entries_after':len(table), 'instruction_boundary_checks':checks, 'string_references':refs, 'personality_pointer_slot':hex(personality_slot), 'original_cleanup_landing':hex(landing), 'translated_calls':[hex(i.address) for i in calls], 'spans':spans, 'limitations':['Offline layout trial; integration branches are absent.', 'Actual QNX unwinder and runtime exceptions/cancellation have not been executed.', 'New FDEs rely on PT_GNU_EH_FRAME indexed lookup; .eh_frame linear fallback lacks the new records.', 'Original cleanup is preserved but does not release new mutex ownership on exception/cancellation.', 'Computed and unaligned pointers into reclaimed strings are not proven absent.']}
(P/'unwind_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {checks} instruction boundaries; {len(metadata)} metadata bytes in {POOL_END-POOL}-byte string pool; {count}->{len(table)} indexed FDE entries; no ELF growth.')
print('Offline placement trial only; original ELF and firmware update remain unchanged.')

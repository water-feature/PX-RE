"""Unpackaged PIC only. Retain .1.2 revision metadata; no updater/QNX output."""
from pathlib import Path
import hashlib, json, struct

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
BASE = 0x9D000000
HELPER = 0x9D07A468
R = dict(zip('zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split(), range(32)))
sha = lambda b: hashlib.sha256(b).hexdigest()

def encode(pc, row, labels):
    op, *a = row
    if op == 'nop': return 0
    if op == 'ehb': return 0xC0
    if op == 'di': return 0x41606000 | R[a[0]] << 16
    if op == 'mtc0_status': return 0x40806000 | R[a[0]] << 16
    if op == 'lui': return 15 << 26 | R[a[0]] << 16 | a[1]
    if op == 'sll': return R[a[1]] << 16 | R[a[0]] << 11 | a[2] << 6
    if op in ('addu', 'subu', 'slt'):
        return R[a[1]] << 21 | R[a[2]] << 16 | R[a[0]] << 11 | {'addu':33,'subu':35,'slt':42}[op]
    if op in ('addiu', 'lw', 'sw'):
        dst, src, imm = a
        assert -32768 <= imm <= 32767
        return {'addiu':9,'lw':35,'sw':43}[op] << 26 | R[src] << 21 | R[dst] << 16 | (imm & 65535)
    if op in ('beq', 'bne'):
        target = labels.get(a[2], a[2]); disp = (target - pc - 4) // 4
        assert target % 4 == 0 and -32768 <= disp <= 32767
        return {'beq':4,'bne':5}[op] << 26 | R[a[0]] << 21 | R[a[1]] << 16 | (disp & 65535)
    if op in ('j', 'jal'):
        target = a[0]; assert target % 4 == 0 and target >> 28 == (pc + 4) >> 28
        return {'j':2,'jal':3}[op] << 26 | ((target >> 2) & 0x3FFFFFF)
    if op == 'jr': return R[a[0]] << 21 | 8
    raise AssertionError(row)

def build():
    source = ROOT / 'b9_250_candidate_work/pic_2.2.2.1.2.bin'
    old = source.read_bytes()
    assert sha(old) == '8f3fcbccd5763324e5f0b7d9cc5941df806a9ecb46affa5c18f5f4d1b082a16c'
    rows = [
        ('addiu','sp','sp',-32), ('sw','ra','sp',28),
        ('sw','s2','sp',24), ('sw','s1','sp',20), ('sw','s0','sp',16),
        ('addu','s1','a0','zero'),
        ('sll','v0','s1',2), ('sll','v1','s1',4), ('subu','v1','v1','v0'),
        ('lui','t1',0x8001), ('addiu','t1','t1',0xBF0), ('addu','v1','v1','t1'),
        ('di','t0'), ('ehb',), ('lw','s0','v1',8), ('sw','zero','v1',8),
        ('mtc0_status','t0'), ('ehb',),
        ('beq','s0','zero','exit'), ('nop',),
        ('slt','t0','s0','zero'), ('sll','t0','t0',1),
        ('addiu','s2','zero',1), ('subu','s2','s2','t0'),
        ('addu','a0','s1','zero'), ('jal',0x9D07DB44), ('addu','a1','s2','zero'),
        ('subu','s0','s0','s2'), ('bne','s0','zero','loop'), ('nop',),
        ('lw','s0','sp',16), ('lw','s1','sp',20), ('lw','s2','sp',24),
        ('lw','ra','sp',28), ('jr','ra'), ('addiu','sp','sp',32),
    ]
    labels = {'loop':HELPER+24*4, 'exit':HELPER+30*4}
    assert len(rows) == 36 and HELPER + len(rows)*4 == 0x9D07A4F8
    new = bytearray(old); patches = []
    def put(pc, word, why):
        off = pc-BASE; before = old[off:off+4]; after = struct.pack('<I',word)
        new[off:off+4] = after
        patches.append({'address':hex(pc),'offset':hex(off),'before':before.hex(),'after':after.hex(),'reason':why})
    for pc, expected in [(0x9D07A34C,'62d4cc4d21be2d02e11e210f1a1a0e1ad333a487a148d004cbb54ff1435d831b'),(0x9D07A3C8,'daf3d11b3aa21b4ce65e75a298fca5f94e4c045f2509564c509f884170d0b56a')]:
        assert sha(old[pc-BASE:pc-BASE+8]) == expected
        put(pc,0,'global canonical slow-path bypass')
    assert sha(old[0x7A208:0x7A210]) == 'f8ef6a4938dc02b3660371e5ef293f9361ce9af83991c9a997b667cfe39b08ae'
    put(0x9D07A208,encode(0x9D07A208,('j',HELPER),labels),'service entry jump')
    put(0x9D07A20C,0,'service entry delay slot; original prologue skipped')
    for i,row in enumerate(rows): put(HELPER+i*4,encode(HELPER+i*4,row,labels),'replay helper in unreachable acceleration code')
    changes = [i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    allowed = [(0x7A208,0x7A210),(0x7A34C,0x7A350),(0x7A3C8,0x7A3CC),(0x7A468,0x7A4F8)]
    assert len(new) == len(old) == 530784
    assert all(any(a<=i<z for a,z in allowed) for i in changes)
    name = 'pic_B14_global_no_acceleration_unpackaged.bin'
    (OUT/name).write_bytes(new)
    report = {'baseline':str(source.relative_to(ROOT)),'baseline_sha256':sha(old),
              'candidate':name,'candidate_sha256':sha(new),'size':len(new),
              'revision_metadata':'inherited .1.2 unchanged; no new release revision',
              'helper_start':hex(HELPER),'helper_end_exclusive':hex(HELPER+144),
              'helper_instructions':36,'helper_bytes':144,'patch_words':len(patches),
              'changed_bytes':len(changes),'allowed_ranges':allowed,'patches':patches,
              'QNX':'not modified','packaged':False}
    (OUT/'patch_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'assembly_input.json').write_text(json.dumps({'rows':rows,'labels':labels,'base':HELPER},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='patches'},indent=2))

if __name__ == '__main__': build()

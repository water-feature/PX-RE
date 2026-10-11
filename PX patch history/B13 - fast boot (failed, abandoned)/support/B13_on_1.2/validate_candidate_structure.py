from pathlib import Path
import struct, hashlib
ROOT=Path(__file__).resolve().parent
base=(ROOT/'baseline_qnx.elf').read_bytes()
cand=(ROOT/'candidate_qnx.elf').read_bytes()
assert len(base)==len(cand)==0xFDBC8
# exact allowed mutation spans (half-open)
spans=[
 (0x1f4e3,0x1f4e4,'application-report-revision'),
 (0x250ef,0x250f0,'application-gate-revision'),
 (0x3527D,0x35281,'startup-call-disp'),
 (0xF9240,0xF93C6,'helper-text'),
 (0xFA528,0xFA594,'helper-cfi+terminator'),
 (0xFB008,0xFB00C,'eh-count'),
 (0xFCB3C,0xFCB44,'eh-index-entry'),
]
# phdr GNU_EH_FRAME p_filesz/memsz
phoff=struct.unpack_from('<Q',base,0x20)[0]; phentsz=struct.unpack_from('<H',base,0x36)[0]; phnum=struct.unpack_from('<H',base,0x38)[0]
for i in range(phnum):
 o=phoff+i*phentsz
 if struct.unpack_from('<I',base,o)[0]==0x6474E550:
  spans += [(o+32,o+40,'ph-filesz'),(o+40,o+48,'ph-memsz')]
# section size fields 14/39/40
shoff=struct.unpack_from('<Q',base,0x28)[0]; shentsz=struct.unpack_from('<H',base,0x3a)[0]
for idx in (14,39,40):
 o=shoff+idx*shentsz+32; spans.append((o,o+8,f'sh{idx}-size'))

def allowed(i): return any(a<=i<b for a,b,_ in spans)
bad=[i for i,(a,b) in enumerate(zip(base,cand)) if a!=b and not allowed(i)]
assert not bad, [hex(x) for x in bad[:20]]
# every declared span should either differ or intentionally contain inserted bytes
print('candidate sha256',hashlib.sha256(cand).hexdigest())
print('changed bytes',sum(a!=b for a,b in zip(base,cand)))
for a,b,n in spans:
 d=sum(base[i]!=cand[i] for i in range(a,b)); print(f'{n:22s} {a:#x}-{b:#x} changed={d}/{b-a}')
# hook target
assert cand[0x3527c]==0xe8
assert 0x35281+struct.unpack_from('<i',cand,0x3527d)[0]==0xf9240
# helper call targets
for field,target,name in [(0xf9266,0x75a0,'open'),(0xf9281,0x78c0,'read'),(0xf928d,0x7810,'close'),(0xf93ad,0x34ef0,'fallback')]:
 assert field+4+struct.unpack_from('<i',cand,field)[0]==target,(name,hex(field+4+struct.unpack_from('<i',cand,field)[0]))
# note field offsets are displacement fields, instruction next = field+4
# EH header exact preservation + append
hb=0xfb000
assert base[hb:hb+4]==cand[hb:hb+4]==bytes([1,0x1b,0x03,0x3b])
assert struct.unpack_from('<I',base,hb+8)[0]==870
assert struct.unpack_from('<I',cand,hb+8)[0]==871
assert base[hb+12:0xfcb3c]==cand[hb+12:0xfcb3c]
pc,fd=struct.unpack_from('<ii',cand,0xfcb3c)
assert hb+pc==0xf9240 and hb+fd==0xfa540
# strictly sorted PC table
n=871; pcs=[]
for i in range(n): pcs.append(hb+struct.unpack_from('<i',cand,hb+12+i*8)[0])
assert all(pcs[i]<pcs[i+1] for i in range(n-1)) and pcs[-1]==0xf9240
# helper FDE record: CIE len=0x14; FDE at +0x18 len=0x4c; pc-relative initial loc resolves to helper; range 0x1a0
EH=0xfa528
assert struct.unpack_from('<I',cand,EH)[0]==0x14
assert struct.unpack_from('<I',cand,EH+0x18)[0]==0x4c
init_disp=struct.unpack_from('<i',cand,EH+0x20)[0]
assert EH+0x20+init_disp==0xf9240
assert struct.unpack_from('<I',cand,EH+0x24)[0]==0x186
assert cand[EH+0x68:EH+0x6c]==b'\0'*4
# mapping: helper/text/cfi/header all lie in existing RX PT_LOAD
for addr in (0xf9240,0xf93c5,0xfa528,0xfa593,0xfb000,0xfcb43): assert addr < 0xfd000
print('ALL STRUCTURAL CHECKS PASS')

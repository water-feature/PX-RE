from pathlib import Path
import struct, hashlib
ROOT=Path(__file__).resolve().parent
base=(ROOT/'v10_exact_reconstructed.elf').read_bytes()
cand=(ROOT/'v10_b13_uuid_v4_candidate.elf').read_bytes()
assert len(base)==len(cand)==0xFDBC8
# exact allowed mutation spans (half-open)
spans=[
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
 if hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',base,o)[0])).hexdigest()=='0fe51dced2745ee6eab34377ad3e64563eef82533a339cae1c75354d09fd1dd5':
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
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',base,hb+8)[0])).hexdigest()=='d5c4545138d26b9f7d7fdf5c5919513b6b8019ac59a45993505ac203abe8cff0'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',cand,hb+8)[0])).hexdigest()=='6941a2fad6b5edcff624fe523ef771377d9a8da1647bccb3d02c45951cbe2141'
assert base[hb+12:0xfcb3c]==cand[hb+12:0xfcb3c]
pc,fd=struct.unpack_from('<ii',cand,0xfcb3c)
assert hb+pc==0xf9240 and hb+fd==0xfa540
# strictly sorted PC table
n=871; pcs=[]
for i in range(n): pcs.append(hb+struct.unpack_from('<i',cand,hb+12+i*8)[0])
assert all(pcs[i]<pcs[i+1] for i in range(n-1)) and pcs[-1]==0xf9240
# helper FDE record: CIE len=0x14; FDE at +0x18 len=0x4c; pc-relative initial loc resolves to helper; range 0x1a0
EH=0xfa528
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',cand,EH)[0])).hexdigest()=='447e12701a0d03cf90a4ad7f02f1a045b35d284e26fe520440edb116d76bf700'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',cand,EH+0x18)[0])).hexdigest()=='33149ff2dc4209e1a1ef29589fe8a3e5d59cb05f0d75531c5d4e17cf72eb6882'
init_disp=struct.unpack_from('<i',cand,EH+0x20)[0]
assert EH+0x20+init_disp==0xf9240
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',cand,EH+0x24)[0])).hexdigest()=='7b777a855e98994332ec090e91bc1cdea0cac51f50572752f2f816b7640a517c'
assert cand[EH+0x68:EH+0x6c]==b'\0'*4
# mapping: helper/text/cfi/header all lie in existing RX PT_LOAD
for addr in (0xf9240,0xf93c5,0xfa528,0xfa593,0xfb000,0xfcb43): assert addr < 0xfd000
print('ALL STRUCTURAL CHECKS PASS')

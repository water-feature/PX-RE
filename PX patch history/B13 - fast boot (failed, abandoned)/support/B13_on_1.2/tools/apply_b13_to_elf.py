from pathlib import Path
import struct, subprocess, hashlib

import argparse,json
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser()
ap.add_argument('--baseline',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--expected-baseline-sha256',required=True)
ap.add_argument('--object',type=Path,default=ROOT.parent/'B13_v4_review/b13_fast_uuid_v4.o')
args=ap.parse_args()
BASE=args.baseline;OBJ=args.object;OUT=args.output
assert BASE.resolve()!=OUT.resolve(), 'Output must differ from baseline'
assert not OUT.exists(), 'Output already exists; choose a new output path'
contract=json.loads((ROOT/'integration_contract.json').read_text())
assert hashlib.sha256(OBJ.read_bytes()).hexdigest()==contract['helper_object_sha256'],'Helper object differs from audited object'
subprocess.check_call(['python3',str(ROOT/'check_cache_callers.py'),str(BASE)],stdout=subprocess.DEVNULL)
raw=BASE.read_bytes()
assert hashlib.sha256(raw).hexdigest()==args.expected_baseline_sha256.lower(),'Baseline SHA-256 mismatch'
for g in contract['guards']:
 block=bytearray(raw[g['offset']:g['offset']+g['length']])
 for off in g['ignored_version_offsets']:block[off-g['offset']]=0
 assert hashlib.sha256(block).hexdigest()==g['sha256'],'Re-audit required: '+g['name']
TEXT_BASE=0xF9240
EH_BASE=0xFA528       # replace existing .b8.eh_frame zero terminator
HDR_BASE=0xFB000
CALL_SITE=0x3527C
# relocation field offsets within .text -> existing ELF target
TARGETS={
    0x26:0x75A0,   # open@plt
    0x41:0x78C0,   # read@plt
    0x4D:0x7810,   # close@plt
    0x16D:0x34EF0, # stock GetGroupFileInfo fallback
}

def section_bin(name,out):
    subprocess.check_call(['objcopy','-O','binary','--only-section='+name,str(OBJ),str(out)])
    return bytearray(Path(out).read_bytes())

text=section_bin('.text',str(OUT.with_suffix('.helper_text.bin')))
eh=section_bin('.eh_frame',str(OUT.with_suffix('.helper_eh.bin')))
assert len(text)==0x186, hex(len(text))
assert len(eh)==0x68, hex(len(eh))

for roff,target in TARGETS.items():
    disp=target-(TEXT_BASE+roff+4)
    assert -(1<<31) <= disp < (1<<31)
    struct.pack_into('<i',text,roff,disp)
# .eh_frame R_X86_64_PC32 at +0x20: placed .text - relocation address
struct.pack_into('<i',eh,0x20,TEXT_BASE-(EH_BASE+0x20))

p=bytearray(BASE.read_bytes()); orig=bytes(p)
assert hashlib.sha256(orig).hexdigest()==args.expected_baseline_sha256.lower()
assert len(p)==0xFDBC8
# Current B8 reservation identities
assert p[0xF923B:0xFA000] == b'\0'*(0xFA000-0xF923B)
assert p[EH_BASE:EH_BASE+4] == b'\0'*4
assert p[0xFA52C:0xFB000] == b'\0'*(0xFB000-0xFA52C)
assert p[0xFCB3C:0xFD000] == b'\0'*(0xFD000-0xFCB3C)
# Original boot worker call target must be stock GetGroupFileInfo.
assert p[CALL_SITE] == 0xE8
old_disp=struct.unpack_from('<i',p,CALL_SITE+1)[0]
assert CALL_SITE+5+old_disp == 0x34EF0

# place helper + standalone CIE/FDE; restore zero terminator
p[TEXT_BASE:TEXT_BASE+len(text)] = text
p[EH_BASE:EH_BASE+len(eh)] = eh
p[EH_BASE+len(eh):EH_BASE+len(eh)+4] = b'\0'*4
# hook only startup preload call
struct.pack_into('<i',p,CALL_SITE+1,TEXT_BASE-(CALL_SITE+5))

# section table helpers
e_shoff=struct.unpack_from('<Q',p,0x28)[0]
e_shentsize=struct.unpack_from('<H',p,0x3A)[0]
e_shnum=struct.unpack_from('<H',p,0x3C)[0]
assert e_shentsize==64 and e_shnum==41

def sh(idx): return e_shoff+idx*e_shentsize
def sh_addr(idx): return struct.unpack_from('<Q',p,sh(idx)+16)[0]
def sh_off(idx): return struct.unpack_from('<Q',p,sh(idx)+24)[0]
def sh_size(idx): return struct.unpack_from('<Q',p,sh(idx)+32)[0]
def set_sh_size(idx,size): struct.pack_into('<Q',p,sh(idx)+32,size)
assert (sh_addr(39),sh_off(39),sh_size(39)) == (0xF8000,0xF8000,0x123B)
assert (sh_addr(40),sh_off(40),sh_size(40)) == (0xFA000,0xFA000,0x52C)
assert (sh_addr(14),sh_off(14),sh_size(14)) == (0xFB000,0xFB000,0x1B3C)
set_sh_size(39,(TEXT_BASE+len(text))-0xF8000)
set_sh_size(40,(EH_BASE+len(eh)+4)-0xFA000)
set_sh_size(14,0x1B44)

# PT_GNU_EH_FRAME grows by one 8-byte binary-search entry. RX LOAD already spans fd000.
e_phoff=struct.unpack_from('<Q',p,0x20)[0]
e_phentsize=struct.unpack_from('<H',p,0x36)[0]
e_phnum=struct.unpack_from('<H',p,0x38)[0]
found=False
for i in range(e_phnum):
    ph=e_phoff+i*e_phentsize
    typ=struct.unpack_from('<I',p,ph)[0]
    off=struct.unpack_from('<Q',p,ph+8)[0]
    filesz=struct.unpack_from('<Q',p,ph+32)[0]
    if typ==1 and off==0:
        assert filesz==0xFD000
    if typ==0x6474E550:
        assert off==HDR_BASE and filesz==0x1B3C
        struct.pack_into('<Q',p,ph+32,0x1B44)
        struct.pack_into('<Q',p,ph+40,0x1B44)
        found=True
assert found

# Existing header: version=1, eh ptr encoding pcrel/sdata4, count udata4, table datarel/sdata4.
assert p[HDR_BASE:HDR_BASE+4] == bytes([1,0x1B,0x03,0x3B])
count=struct.unpack_from('<I',p,HDR_BASE+8)[0]
assert count==870
entry=HDR_BASE+12+count*8
assert entry==0xFCB3C
# Helper is after all existing PC entries, so append sorted final row.
struct.pack_into('<I',p,HDR_BASE+8,count+1)
struct.pack_into('<ii',p,entry,TEXT_BASE-HDR_BASE,(EH_BASE+0x18)-HDR_BASE)

assert len(p)==len(orig)
allowed=[(CALL_SITE+1,CALL_SITE+5),(TEXT_BASE,TEXT_BASE+len(text)),(EH_BASE,EH_BASE+len(eh)+4),(HDR_BASE+8,HDR_BASE+12),(entry,entry+8)]
for idx in (14,39,40):allowed.append((sh(idx)+32,sh(idx)+40))
for i in range(e_phnum):
 ph=e_phoff+i*e_phentsize
 if hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',p,ph)[0])).hexdigest()=='0fe51dced2745ee6eab34377ad3e64563eef82533a339cae1c75354d09fd1dd5':allowed.append((ph+32,ph+48))
assert all(any(a<=i<z for a,z in allowed) for i,(a,b) in enumerate(zip(orig,p)) if a!=b),'Unexpected mutation'
# Recheck actual RX mapping for the full added regions.
for start,end in ((TEXT_BASE,TEXT_BASE+len(text)),(EH_BASE,EH_BASE+len(eh)+4),(HDR_BASE,entry+8)):
 mapped=False
 for i in range(e_phnum):
  ph=e_phoff+i*e_phentsize
  typ,flags=struct.unpack_from('<II',p,ph);off,va=struct.unpack_from('<QQ',p,ph+8);filesz=struct.unpack_from('<Q',p,ph+32)[0]
  if typ==1 and flags&5==5 and off<=start and end<=off+filesz and va==off:mapped=True
 assert mapped, 'Added region not covered by expected RX mapping'
OUT.write_bytes(p)
receipt={'baseline_sha256':hashlib.sha256(orig).hexdigest(),'candidate_sha256':hashlib.sha256(p).hexdigest(),'allowed_difference_spans':allowed,'version_bytes_modified':False,'protected_contracts':'pass','status':'ELF candidate only; container not created'}
OUT.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
# Difference accounting
changes=[i for i,(a,b) in enumerate(zip(orig,p)) if a!=b]
print('out',OUT)
print('size',len(p),'sha256',hashlib.sha256(p).hexdigest())
print('helper text',hex(TEXT_BASE),hex(TEXT_BASE+len(text)),len(text))
print('helper eh',hex(EH_BASE),hex(EH_BASE+len(eh)),len(eh),'fde',hex(EH_BASE+0x18))
print('hook',hex(CALL_SITE),'old->',hex(0x34EF0),'new->',hex(TEXT_BASE))
print('changed_bytes',len(changes),'first',hex(min(changes)),'last',hex(max(changes)))

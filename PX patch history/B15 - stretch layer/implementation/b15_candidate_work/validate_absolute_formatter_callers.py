"""Bounded fitted formatter caller inventory and exhaustive 16-bit guard execution.
Does not execute full renderers or model their results. No firmware writes.
"""
import os,json,struct,hashlib
os.environ['B15_PLACED']='1'
import validate_pic_absolute as v
O=v.O;BASE=v.m.BASE;ENTRY=0x9d05f7f4;RESUME=ENTRY+8;STRCAT=0x9d08169c
expected=[0x031e0c,0x031eac,0x03af30,0x03afbc,0x03b298,0x03b310,
          0x03df40,0x03e158,0x03e3e0,0x03e46c,0x03e56c,0x03e5c0,
          0x03e6b4,0x03e77c,0x03e93c,0x03e99c,0x03ef4c,0x03f0b4,
          0x03f17c,0x03f2e8,0x060bfc]
fixed={0x03df40:0xb7,0x03e158:0xb8,0x03e3e0:0xc1,0x03e46c:0xc2,
       0x03e56c:0xc3,0x03e5c0:0xb9,0x03e6b4:0xc4,0x03e77c:0xba,
       0x03e93c:0xbb,0x03e99c:0xc5,0x03ef4c:0x65,0x03f0b4:0x22,
       0x03f17c:0x24,0x03f2e8:0x63}
def inventory(image):
 hits=[]
 for off in range(0,len(image)-3,4):
  w=struct.unpack_from('<I',image,off)[0]
  if w>>26 in (2,3) and (((BASE+off+4)&0xf0000000)|((w&0x3ffffff)<<2))==ENTRY:hits.append(off)
 return hits
assert inventory(v.raw)==inventory(v.img)==expected
# Full stock formatter body after the displaced prologue is unchanged.
assert v.img[0x5f7fc:0x60bec]==v.raw[0x5f7fc:0x60bec]
assert v.m.decode(v.img,ENTRY)==('j',v.L['b15_format'])
assert not ENTRY<=RESUME<ENTRY+8
# The fallback changes only scratch t0 beyond the stock prologue. It is not
# consumed by stock formatter instructions; exclude its inline switch table.
for pc in list(range(RESUME,0x9d05f844,4))+list(range(0x9d05fecc,0x9d060bec,4)):
 try:
  assert 't0' not in v.m.decode(v.raw,pc),(hex(pc),'t0 operand')
 except AssertionError as error:
  if 'unhandled' not in str(error):raise
  w=struct.unpack_from('<I',v.raw,pc-BASE)[0]
  assert 8 not in ((w>>21)&31,(w>>16)&31),(hex(pc),'undecoded possible t0 operand')
c=v.CPU();sp=c.g('sp');buf=0x80061000
baseline_regs=c.r.copy();count=0
# All 16-bit parameter IDs at the special value, and all 16-bit values for
# both special IDs. Extra high-bit parameter IDs must also fall through.
inputs=((pid,65535) for pid in range(65536))
def values():
 yield from inputs
 for pid in (0x1c,0x5d):
  for n in range(65535):yield pid,n
 for pid in (0x1001c,0x1005d,0xffffffff):yield pid,65535
for pid,n in values():
 c.r=baseline_regs.copy();c.trace.clear()
 for r,x in zip(('a0','a1','a2','ra'),(pid,n,buf,v.STOP)):c.s(r,x)
 before=c.r.copy();end=c.run(ENTRY,{RESUME,STRCAT},maxsteps=32)
 pending=pid in (0x1c,0x5d) and n==65535
 assert end==(STRCAT if pending else RESUME),(pid,n,hex(end))
 if not pending:
  for reg in range(32):
   if reg not in (v.m.R['sp'],v.m.R['t0']):assert c.r[reg]==before[reg],(pid,n,reg)
  assert c.g('sp')==sp-48 and c.read(sp-4,4)==v.STOP
 count+=1
# Execute every unchanged real JAL and its actual delay word, then the fitted
# hook, for an ordinary value. Caller pre-state is seeded, not a full renderer.
callers=[]
for off in expected:
 c=v.CPU();pc=BASE+off;pid=fixed.get(off,0x20);n=1;sp=c.g('sp')
 for r,x in zip(('a0','a1','a2','v0'),(pid,n,buf,n)):c.s(r,x)
 assert v.img[off-8:off+8]==v.raw[off-8:off+8]
 # Preserve the caller's final a0 setup when it precedes the JAL.
 if off in fixed:
  writes=[v.m.decode(v.img,p) for p in (pc-8,pc-4,pc+4)]
  assert ('addiu','a0','zero',pid) in writes
 c.run(pc,{RESUME},maxsteps=32)
 assert c.g('a0')==pid and c.g('a1')==n
 assert c.g('sp')==sp-48 and c.read(sp-4,4)==pc+8
 callers.append({'call':hex(pc),'parameter':hex(pid) if off in fixed else 'dynamic (0x20 seeded)','status':'PASS call/delay/hook; stock resume reached'})
# Literal pointer inventory covers raw stored entry aliases, not arbitrary
# multi-step computed addresses or unknown callback registration.
literals=[]
for off in range(len(v.raw)-3):
 w=struct.unpack_from('<I',v.raw,off)[0]
 if w in (ENTRY,ENTRY-0x40000000,ENTRY-0x80000000):literals.append([hex(BASE+off),hex(w)])
report={'status':'PASS_BOUNDED_FORMATTER_CALLER_GUARD','formatter':hex(ENTRY),'resume':hex(RESUME),
 'guard_cases':count,'direct_callers':callers,'entry_literal_alias_hits':literals,
 'unchanged_stock_body':[hex(RESUME),hex(BASE+0x60bec)],
 'fitted_sha256':hashlib.sha256(v.img).hexdigest(),
 'modeled':'MIPS interpreter; seeded caller state. Stops at unchanged stock-body resume, not full renderer/parameter-specific callee execution.',
 'limits':'All raw direct J/JAL references listed. Literal pointer scan is not exhaustive indirect/computed/callback closure. Hardware and physical display NOT VERIFIED.'}
(O/'absolute_formatter_callers_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

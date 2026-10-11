"""Execute actual .1.15 PIC setter/clamp/getter instructions, never patch a file.

Metadata loading, notification and UI calls are recorded stubs. This validates
setter integration, not external loading, interrupts or real hardware.
"""
from pathlib import Path
import struct, json, sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'b11_pic_tools'))
import decode_pic as pic
R={s:i for i,s in enumerate(pic.r)}
BASE=0x9d000000
PARAM=0x8000046c
def signed(x): return x-0x100000000 if x&0x80000000 else x

class CPU:
 def __init__(self,overlay=None,callbacks=None):
  self.r=[0]*32;self.mem={};self.overlay=overlay or {};self.calls=[];self.trace=[]
  self.r[29]=0x80070000;self.r[28]=0x80060000;self.callbacks=callbacks or {};self.real_effects=set()
 def load(self,a,n):
  if BASE<=a and a+n<=BASE+len(pic.b): return int.from_bytes(pic.b[a-BASE:a-BASE+n],'little')
  return sum(self.mem.get(a+i,0)<<(8*i) for i in range(n))
 def store(self,a,n,v):
  for i in range(n):self.mem[a+i]=(v>>(8*i))&255
 def word(self,p):return self.overlay[p] if p in self.overlay else self.load(p,4)
 def plain(self,w,p):
  r=self.r;op=w>>26;s=(w>>21)&31;t=(w>>16)&31;d=(w>>11)&31;n=(w>>6)&31;fn=w&63;u=w&65535;i=u if u<32768 else u-65536
  if op==0:
   if fn==0:r[d]=r[t]<<n
   elif fn==2:r[d]=r[t]>>n
   elif fn==3:r[d]=signed(r[t])>>n
   elif fn in (32,33):r[d]=r[s]+r[t]
   elif fn in (34,35):r[d]=r[s]-r[t]
   elif fn==36:r[d]=r[s]&r[t]
   elif fn==37:r[d]=r[s]|r[t]
   elif fn==38:r[d]=r[s]^r[t]
   elif fn==42:r[d]=int(signed(r[s])<signed(r[t]))
   elif fn==43:r[d]=int(r[s]<r[t])
   elif fn==10:
    if r[t]==0:r[d]=r[s]
   elif fn==11:
    if r[t]!=0:r[d]=r[s]
   else:raise AssertionError((hex(p),pic.dec(p,w)))
  elif op in (8,9):r[t]=r[s]+i
  elif op==10:r[t]=int(signed(r[s])<i)
  elif op==11:r[t]=int(r[s]<(i&0xffffffff))
  elif op==12:r[t]=r[s]&u
  elif op==13:r[t]=r[s]|u
  elif op==14:r[t]=r[s]^u
  elif op==15:r[t]=u<<16
  elif op in (32,33,35,36,37):
   size={32:1,33:2,35:4,36:1,37:2}[op];v=self.load((r[s]+i)&0xffffffff,size)
   if op in (32,33) and v&(1<<(size*8-1)):v-=1<<(size*8)
   r[t]=v
  elif op in (40,41,43):self.store((r[s]+i)&0xffffffff,{40:1,41:2,43:4}[op],r[t])
  elif op==31 and fn==10:r[d]=self.load((r[s]+r[t])&0xffffffff,4)
  else:raise AssertionError((hex(p),pic.dec(p,w)))
  self.r=[v&0xffffffff for v in r];self.r[0]=0
 def run(self,start,stops,limit=5000):
  p=start
  # Only these external effects are mocked; all setter logic and existing
  # patch interceptors on the category paths execute from the real image.
  mocks={0x9d041048,0x9d04d7b8,0x9d03ec34,0x9d036a28,0x9d0792a0,0x9d01d4bc}-self.real_effects
  for step in range(limit):
   if p in stops:return p
   if p in self.callbacks:
    self.calls.append((p,self.r[4:8]));self.callbacks[p](self);p=self.r[31];continue
   if p in mocks:
    args=self.r[4:8];self.calls.append((p,args))
    self.r[2]=0
    p=self.r[31];continue
   self.trace.append(p)
   w=self.word(p);op=w>>26;s=(w>>21)&31;t=(w>>16)&31;u=w&65535;i=u if u<32768 else u-65536;fn=w&63
   dest=None;likely=False;take=True
   if op in (2,3):
    dest=((p+4)&0xf0000000)|((w&0x3ffffff)<<2)
    if op==3:self.r[31]=p+8
   elif op==0 and fn in (8,9):
    dest=self.r[s]
    if fn==9:self.r[(w>>11)&31]=p+8
   elif op in (4,5,6,7,20,21,22,23):
    take={4:self.r[s]==self.r[t],5:self.r[s]!=self.r[t],6:signed(self.r[s])<=0,7:signed(self.r[s])>0}[op if op<20 else op-16]
    dest=p+4+i*4;likely=op>=20
   elif op==1:
    assert t in (0,1,2,3),(hex(p),t)
    take=signed(self.r[s])<0 if t in (0,2) else signed(self.r[s])>=0;likely=t>=2;dest=p+4+i*4
   if dest is None:self.plain(w,p);p+=4
   else:
    if take or not likely:self.plain(self.word(p+4),p+4)
    p=dest if take else p+8
  raise AssertionError(('limit',hex(p),[hex(x) for x in self.trace[-15:]]))

def encode_helper(addr,ret):
 # Read old A/B categories from registers saved by the absolute setter.
 # Nonmanual calls branch directly to stock clamp; signed displacement fits.
 lines=[f'lw t0,0x2c,sp','lui t1,0x9d02',f'ori t1,t1,{ret&65535}',
        'bne t0,t1,0x9d04d4fc','sll t0,a0,2','addu t0,t0,sp','lw t0,0x24,t0',
        'beq t0,s3,0x9d04d4fc','sltiu t0,a2,1','addu a2,a2,t0','j 0x9d04d4fc','nop']
 # Reuse the authorized explicit encoder without invoking its output driver.
 scope={};src=(ROOT.parent/'b11_pic_tools/measure_corrected.py').read_text()
 exec(compile(src.split('out=Path(__file__).parent')[0],'<encoder>','exec'),scope)
 def enc(p,line):
  if line.startswith('ori '):
   t,s,n=line[4:].split(',');return (13<<26)|(R[s]<<21)|(R[t]<<16)|int(n,0)
  if line.startswith('j '):return (2<<26)|((int(line[2:],0)>>2)&0x3ffffff)
  return scope['encode'](p,line)
 return {addr+4*i:enc(addr+4*i,line) for i,line in enumerate(lines)},lines

HELPER=0x9d02dd08
RETURN=0x9d02df0c
helper,helper_lines=encode_helper(HELPER,RETURN)
# This 48-byte contiguous helper is a sizing probe and exceeds the original
# 36-byte DD08 allocation by 12 bytes. It is never installed in firmware.
overlay=dict(helper)
for site in (0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624):overlay[site]=(3<<26)|((HELPER>>2)&0x3ffffff)

def scenario(inst,edit,old,counts,remembered,manual=True,direction=1,enabled=True):
 c=CPU(overlay if manual else overlay)
 category=(0x24,0x65)[inst];instrument=category-1;group=category-2
 groups=(0,32)
 for bank in (0,1):
  b=PARAM+bank*0xd6e
  c.store(b+group*2,2,groups[bank]);c.store(b+category*2,2,old[bank]);c.store(b+instrument*2,2,0)
  c.store(b+(0x11 if inst==0 else 0x52)*2,2,int(enabled))
  for cat in range(17):c.store(0x80037e90+8*(17*groups[bank]+cat),4,counts[bank])
 # 9D01E334 indexes a0+60; the Type path's argument is bank/instrument selector.
 c.store(0x80052e18+2*60,2,remembered[0])
 c.store(0x80052e18+2*61,2,remembered[1])
 # Both Instrument 1 and 2 A restoration calls use a0=0; B uses a0=1.
 c.r[20]=old[0];c.r[21]=old[1]
 saved=tuple(c.r[16:24]);start_sp=c.r[29]
 c.r[31]=RETURN if manual else 0x9d0267c0
 c.r[4]=0;c.r[5]=edit;c.r[6]=category;c.r[7]=direction&0xffffffff
 c.store(c.r[29]+0x10,4,16)
 c.store(0x80006ffe,2,1)
 stop=c.r[31];c.run(0x9d04fa6c,{stop})
 target=max(0,min(16,old[0 if edit in (0,2) else 1]+direction))
 active=(0,1) if edit==2 else (edit,)
 got=[c.load(PARAM+b*0xd6e+instrument*2,2) for b in (0,1)]
 expected=[]
 for b in (0,1):
  # Restore source is a0=0 (A) or a0=1 (B). In the actual paths those
  # arguments are set before 9D01E334, as verified by instruction execution.
  s=remembered[b]
  expected.append(min(max(s,1) if manual and old[b]!=target else s,counts[b]-1) if b in active else 0)
 assert got==expected,(inst,edit,old,counts,remembered,manual,direction,got,expected)
 assert tuple(c.r[16:24])==saved,'callee saved registers'
 assert c.r[29]==start_sp,'stack balance'
 assert [c.load(PARAM+b*0xd6e+category*2,2) for b in (0,1)]==[target if b in active else old[b] for b in (0,1)]
 return c

if __name__=='__main__':
 count=0;sites=set();witnesses=[]
 for inst in (0,1):
  for edit in (0,1,2):
   for old in ((0,0),(16,16),(0,16),(16,0),(2,3),(2,12),(5,5)):
    for counts in ((1,1),(2,1),(1,2),(17,4)):
     for remembered in ((0,0),(1,1),(255,255)):
      for manual in (False,True):
       for direction in (-1,1):
        c=scenario(inst,edit,old,counts,remembered,manual,direction)
        count+=1;sites.update(set(c.trace)&{0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624})
 summary={'actual_setter_cases':count,'replacement_sites_executed':[hex(s) for s in sorted(sites)],'external_effects':'metadata loading, notifications, UI and sample-presence helper are stubs','helper_active_bytes':len(helper)*4,'snapshot_instruction_bytes':20,'firmware_modified':False}
 (ROOT/'setter_results.json').write_text(json.dumps(summary,indent=2)+'\n')
 (ROOT/'boundary_helper_listing.txt').write_text('\n'.join(f'{p:08x} {helper[p]:08x} {line}' for p,line in zip(helper,helper_lines))+'\n')
 print(json.dumps(summary,indent=2))

"""Fitted renderer execution; selected-bank and physical drawing calls modeled."""
import sys,struct,os
from pathlib import Path
os.environ["B15_PLACED"]="1"
sys.path.insert(0,str(Path(__file__).resolve().parent))
import validate_pic_absolute as v
assert v.placed
assert v.m.decode(v.img,0x9d031da0)==('jal',v.L['b15_effective_get'])
assert v.m.decode(v.img,0x9d05f7f4)==('j',v.L['b15_format'])
# Both resumes begin immediately after the two overwritten instruction words.
for start,resume in ((0x9d031da0,0x9d031da8),(0x9d05f7f4,0x9d05f7fc)):
 assert not start<=resume<start+8
prior=v.p.decode
def decode(b,pc):
 w=struct.unpack_from('<I',b,pc-v.m.BASE)[0]
 if w&0xffe007ff==0x7c000620:return ('seb',next(k for k,n in v.m.R.items() if n==(w>>11)&31),next(k for k,n in v.m.R.items() if n==(w>>16)&31))
 if w>>26==0 and w&63 in (24,16,18):
  names={n:k for k,n in v.m.R.items()}
  if w&63==24:return ('mult',names[(w>>21)&31],names[(w>>16)&31])
  return ('mfhi' if w&63==16 else 'mflo',names[(w>>11)&31])
 if w>>26==0 and w&63==3:
  names={n:k for k,n in v.m.R.items()};return ('sra',names[(w>>11)&31],names[(w>>16)&31],(w>>6)&31)
 if w>>26 in (42,46):
  names={n:k for k,n in v.m.R.items()};off=w&65535;off=off if off<32768 else off-65536
  return ('swl' if w>>26==42 else 'swr',names[(w>>16)&31],off,names[(w>>21)&31])
 return prior(b,pc)
v.p.decode=decode
class CPU(v.CPU):
 def simple(self,row):
  if row[0]=='seb':
   x=self.g(row[2])&255;self.s(row[1],x if x<128 else x-256);return
  if row[0]=='mult':
   value=(v.m.signed(self.g(row[1]))*v.m.signed(self.g(row[2])))&((1<<64)-1);self.hi=value>>32;self.lo=value&0xffffffff;return
  if row[0] in ('mfhi','mflo'):self.s(row[1],self.hi if row[0]=='mfhi' else self.lo);return
  if row[0]=='sra':self.s(row[1],v.m.signed(self.g(row[2]))>>row[3]);return
  if row[0] in ('swl','swr'):
   addr=self.g(row[3])+row[2];k=addr&3;value=self.g(row[1])
   if row[0]=='swl':self.write(addr-k,value>>(8*(3-k)),k+1)
   else:self.write(addr,value,4-k)
   return
  super().simple(row)
 def external(self,pc):
  if pc in (0x9d0689d8,0x9d068d64):
   if pc==0x9d068d64:
    ptr=self.g('a2');s=bytearray()
    while self.read(ptr+len(s),1):s.append(self.read(ptr+len(s),1))
    self.draws.append(bytes(s))
   return True
  return super().external(pc)
for scenario in ("pending","valid","disabled"):
 for bank in (0,1):
  for pid in (0x1c,0x5d):
   c=CPU();c.draws=[];c.s('ra',v.STOP);c.run(v.L['b15_pic_init'],{v.STOP})
   # Selected bank is an explicit modeled dependency.
   old=c.external
   def external(pc):
    if pc==0x9d031b70:c.s('v0',bank);return True
    return old(pc)
   c.external=external
   c.write(0x8000046c+2*(bank*0x6b7+pid-10),1,2)
   c.write(0x8000046c+2*(bank*0x6b7+pid),3,2)
   pair=2*bank+(pid==0x5d)
   if scenario=='valid':c.write(v.S+16*pair+4,2,1)
   if scenario=='disabled':c.write(0x8000046c+2*(bank*0x6b7+pid-10),0,2)
   expected=65535 if scenario=='pending' else (2 if scenario=='valid' else 3)
   obj=0x80062000;c.write(obj+178,pid,2);c.write(obj+194,expected,2)
   for mode in (0,2):
    sp=c.g('sp');c.write(sp+16,mode,1);c.write(sp+20,0,4)
    for r,x in zip(('a0','a1','a2','a3'),(obj,10,20,0)):c.s(r,x)
    c.s('ra',v.STOP);c.run(0x9d031d28,{v.STOP},maxsteps=100000)
    assert c.g('sp')==sp
    assert c.read(obj+194,2)==expected
    assert c.read(0x8000046c+2*(bank*0x6b7+pid),2)==3
   text=b'Samp Vel: '+(b'--' if scenario=='pending' else (b'Layer 2' if scenario=='valid' else b'Layer 3'))
   assert c.draws==[text]*3,c.draws
   print(bank,hex(pid),'PASS',scenario,'fresh/cache')

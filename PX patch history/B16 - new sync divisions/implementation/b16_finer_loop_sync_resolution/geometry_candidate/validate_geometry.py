# SPDX-License-Identifier: GPL-2.0-or-later
"""Focused validation of emitted bytes; no firmware writes."""
from pathlib import Path
import runpy,struct,json
D=Path(__file__).resolve().parent;B=D.parent;BASE=0x9d000000
p=runpy.run_path(str(B/'safety_review/tight_editor_probe.py'))
# Load existing scoped CPU and runner definitions only, without running tests/output writes.
s=(B/'geometry_review/proposal_probe.py').read_text();ns={'C':p['CPU'],'BASE':BASE};exec(s[s.index('class CPU'):s.index('cases=0;rows=[]')],ns)
run=ns['run']
def validate(image):
 old=(B.parent/'b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin').read_bytes();cases=0
 for ident in range(0x6b6):
  maximum=struct.unpack_from('<H',old,0x47498+12*ident)[0]
  vals=range(18) if ident in (29,94) else sorted({0,1,min(maximum,15),maximum//2,maximum})
  for layer in (0,1):
   for raw in vals:
    z=run(image,None,ident,raw,layer)
    if ident in (29,94) and raw>=16:assert z.reg[21]==(3 if raw==16 else 1)
    else:
     a=run(old,None,ident,raw,layer);assert (z.reg[21],z.lo,z.hi)==(a.reg[21],a.lo,a.hi)
     assert z.reg[16:21]==a.reg[16:21] and z.reg[22:24]==a.reg[22:24] and z.reg[28:31]==a.reg[28:31]
    cases+=1
 # Execute actual getters and downstream clipping/draw arguments, with only drawing I/O intercepted.
 source=(B/'in_place_validation/preflight.py').read_text();cpu_ns={'__file__':str(B/'in_place_validation/preflight.py')};exec(source[:source.index('# Combined display execution')],cpu_ns);cpu_ns['data']={};BaseCPU=cpu_ns['CPU']
 class CPU(BaseCPU):
  def plain(self,w):
   op=w>>26;rs=w>>21&31;t=w>>16&31;rd=w>>11&31;fn=w&63
   if op==28 and fn==2:self.reg[rd]=(self.reg[rs]*self.reg[t])&0xffffffff
   elif op==0 and fn==4:self.reg[rd]=(self.reg[t]<<(self.reg[rs]&31))&0xffffffff
   elif op==0 and fn==27:assert self.reg[t];self.lo,self.hi=divmod(self.reg[rs],self.reg[t])
   elif op==0 and fn==18:self.reg[rd]=self.lo
   elif op==0 and fn==52:assert self.reg[rs]!=self.reg[t]
   elif op==31 and fn==32 and w>>6&31==24:
    v=self.reg[t]&65535;self.reg[rd]=(v if v<32768 else v-65536)&0xffffffff
   else:return super().plain(w)
   self.reg[0]=0
 def draw(img,ident,raw,layer,center,start,end):
  c=CPU(img);c.reg=[0x12000000+i for i in range(32)];c.reg[0]=0;c.reg[16]=0x80060000;c.reg[17]=BASE+0x47498;c.reg[18]=center;c.reg[19]=center+5;c.reg[3]=ident;c.reg[28]=0x80007ff0;c.reg[29]=0x80070000
  inst=0 if ident==29 else 1;offset=65*inst;ids=[offset+7,ident,offset+15,offset+9]
  for o,val in zip((0xb2,0xb4,0xb6,0xb8),ids):c.write(c.reg[16]+o,2,val)
  c.write(0x80052e5c,2,1-layer)
  for bank in (0,1):
   for param,value in zip(ids,(start,raw,0,end)):c.write(0x8000046c+2*(param+bank*0x6b7),2,value)
  calls=[]
  def hook(cpu,pc):
   if pc in (BASE+0x67ad0,BASE+0x67a2c,BASE+0x686bc):calls.append([hex(pc),*cpu.reg[4:8]]);return True
   return False
  c.run(BASE+0x3b0a0,BASE+0x3b238,hook=hook)
  assert c.reg[29]==0x80070000 and c.reg[16]==0x80060000 and c.reg[28]==0x80007ff0
  assert len(calls)==3 and calls[-1][0]==hex(BASE+0x686bc)
  return calls
 draws=0;representative=[]
 for ident in (29,94):
  off=0 if ident==29 else 65;sm=struct.unpack_from('<H',old,0x47498+12*(off+7))[0];em=struct.unpack_from('<H',old,0x47498+12*(off+9))[0]
  for layer in (0,1):
   for raw in range(18):
    for center in (0,1,6,7,8,60,117,118,123,124,180,239,245,246):
     for start,end in ((0,em),(sm//4,em*3//4),(sm//2,em//2)):
      z=draw(image,ident,raw,layer,center,start,end)
      if raw<16:assert z==draw(old,ident,raw,layer,center,start,end),(ident,raw,layer,center,start,end,z)
      left,right=z[-1][1],z[-1][3];assert 5<=left<=right<=251,(raw,z)
      if raw>=16:assert right-left<=2*(3 if raw==16 else 1),(raw,z)
      draws+=1
    if ident==29 and layer==0 and raw in (1,0,16,17):representative.append({'raw':raw,'halfwidth':run(image,None,ident,raw,layer).reg[21],'unclipped_draw':draw(image,ident,raw,layer,123,0,em)[-1]})
 return {'status':'PASS','emitted_width_instruction_cases':cases,'actual_getters_clipping_draw_argument_cases':draws,'representative':representative,'limits':['Scoped interpreter, not a complete PIC emulator','Drawing I/O intercepted; panel pixels and hardware not tested','General recovery independence remains NOT VERIFIED']}
if __name__=='__main__':
 import sys
 r=validate(Path(sys.argv[1]).read_bytes());(D/'geometry_results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

#!/usr/bin/env python3
"""Execute emitted helper words in the inherited bounded MIPS interpreter.
The synthetic execution image is IN MEMORY ONLY, not a firmware payload.
"""
from pathlib import Path
import struct,json,sys
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'b9_250_candidate_work'));import mips_check as m
raw_decode=m.decode
S=0x80057aa0

def decode(b,pc):
 w=struct.unpack_from('<I',b,pc-m.BASE)[0]
 if w>>26==0 and w&63==4:return ('sllv',m.REGS[(w>>11)&31],m.REGS[(w>>16)&31],m.REGS[(w>>21)&31])
 if w&0xffe0ffff==0x41606000:return ('di',m.REGS[(w>>16)&31])
 if w&0xffe0ffff==0x40806000:return ('mtc0_status',m.REGS[(w>>16)&31])
 return raw_decode(b,pc)
m.decode=decode
class CPU(m.CPU):
 def __init__(self,image):
  super().__init__(image);self.status=1;self.sent=[];self.redraws=[];self.stock_edits=[]
 def simple(self,row):
  if row[0]=='sllv':self.s(row[1],self.g(row[2])<<(self.g(row[3])&31));return
  if row[0]=='di':self.s(row[1],self.status);self.status&=~1;return
  if row[0]=='mtc0_status':self.status=self.g(row[1]);return
  super().simple(row)
 def external(self,pc):
  answer=0
  if pc==0x9d075c1c:self.sent.append(self.g('a0'))
  elif pc==0x9d04d300:
   bank=self.g('a0');pid=self.g('a1');answer=self.read(0x8000046c+2*(bank*0x6b7+pid),2)
  elif pc==0x9d03dcd8:answer=5
  elif pc==0x9d036a38:self.redraws.append((self.g('a0'),self.g('a1')))
  elif pc==0x9d075c24:
   self.sent.append(self.g('a0'));self.s('ra',self.read(self.g('sp')+20,4));self.s('sp',self.g('sp')+24)
  elif pc==0x9d04fa74:
   self.stock_edits.append((self.g('a0'),self.g('a1'),self.g('a2'),self.g('a3')))
   self.s('ra',self.read(self.g('sp')+28,4));self.s('sp',self.g('sp')+32)
  else:return False
  # Legitimate o32 clobbers including argument home area: catches hidden reliance.
  sp=self.g('sp');ra=self.g('ra')
  for i in list(range(2,16))+[24,25]:self.r[i]=0xbad00000+i
  for off in range(0,16,4):self.write(sp+off,0xdecafbad,4)
  self.s('v0',answer);self.s('ra',ra);return True

def main():
 asm=json.loads((OUT/'pic_helpers_assembly.json').read_text());labels={k:int(v,16) for k,v in asm['labels'].items()}
 original=(ROOT/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
 code=(OUT/'pic_helpers_unplaced.bin').read_bytes();image=bytearray(original)
 image[0x2a0:0x2a0+len(code)]=code # test-only overlay deliberately NOT WRITTEN to disk
 c=CPU(image);return_pc=0x9d088000;cases=[]
 def call(name,*args):
  for r,value in zip(('a0','a1','a2','a3'),args):c.s(r,value)
  c.s('ra',return_pc);saved={r:c.g(r) for r in ('s0','s1','s2','s3','s4','s5','s6','s7','gp','sp','fp')}
  c.run(labels[name],{return_pc},maxsteps=10000)
  assert c.g('ra')==return_pc
  for r,value in saved.items():assert c.g(r)==value,(name,r)
  return c.g('v0')
 def pkt(p,e,n):return e<<9|p<<7|n
 call('b15_pic_init');assert c.read(S,64)==0;cases.append('cold init exact64')
 for p in range(4):
  for j in range(500):assert call('b15_pic_edit',p)==1
  for j in range(500):assert call('b15_pic_receive',0x4051,pkt(p,0,j%17))==1
  assert c.read(S+12*p,2)==c.read(S+12*p+2,2)==500
 call('b15_pic_service')
 for p in range(4):
  bank=p>>1;pid=0x1c+(p&1)*0x41
  assert c.read(0x8000046c+2*(bank*0x6b7+pid),2)==499%17
 assert len(c.redraws)==4;cases.append('2000 mirrors count independently of mailbox coalescing; private stores/redraw')
 # Query fence and context epoch: receive snapshot, barrier, apply, then advance.
 call('b15_pic_fence_start',15,1000)
 query=c.read(S+52,2);assert c.sent[-1]==0x40520000|(query<<9)|15
 assert not call('b15_pic_receive',0x4052,query<<9|15)
 for p in range(4):assert call('b15_pic_receive',0x4051,pkt(p,0,p+1)|0x40)
 assert call('b15_pic_receive',0x4052,query<<9|15)
 assert not call('b15_pic_fence_finish',1)
 call('b15_pic_service');assert call('b15_pic_fence_finish',1)
 for p in range(4):assert c.read(S+12*p+6,1)==1
 assert not call('b15_pic_receive',0x4051,pkt(0,0,16));cases.append('snapshot coverage; main apply before epoch advance; stale mirror rejected')
 call('b15_pic_fence_start',15,10);assert call('b15_pic_fence_poll',9)==1
 assert call('b15_pic_fence_poll',10)==3;assert not call('b15_pic_edit',0)
 call('b15_pic_fence_start',15,20)
 for p in range(4):call('b15_pic_receive',0x4051,pkt(p,1,0)|0x40)
 call('b15_pic_receive',0x4052,c.read(S+52,2)<<9|15);call('b15_pic_service');assert call('b15_pic_fence_finish',0)
 cases.append('bounded deadline and query recovery without replay')
 # Refused starts cannot overwrite a live transaction or its deadline/mask.
 call('b15_pic_init')
 for mask in (0,16,0xffffffff):
  before=c.read(S,64);sent=len(c.sent)
  assert call('b15_pic_fence_start',mask,100)==0
  assert c.read(S,64)==before and len(c.sent)==sent and c.status==1
 for phase in (1,2):
  c.write(S+54,phase,1);before=c.read(S,64);sent=len(c.sent)
  assert call('b15_pic_fence_start',1,100)==0
  assert c.read(S,64)==before and len(c.sent)==sent and c.status==1
 call('b15_pic_init');assert not call('b15_pic_edit',4)
 cases.append('invalid pair/mask and WAIT/READY reentry rejected without mutation; IRQ restored')
 # No-held enable must emit no prepare command or increment capture tags.
 c.sent=[];c.s('s1',128);before=c.read(S,64)
 call('b15_capture_prepare',2)
 assert not c.sent and c.read(S,64)==before
 cases.append('no-held prepare leaves capture state untouched')
 # Stock display getter bank2 means A; it must not index a non-existent pair4.
 c.write(0x8000046c+2*0x12,1,2);c.write(S+4,7,1);c.write(S+24+4,12,1)
 c.write(0x8000046c+2*(0x6b7+0x12),1,2)
 assert call('b15_effective_get',0,0x1c)==7
 assert call('b15_effective_get',1,0x1c)==12
 assert call('b15_effective_get',2,0x1c)==7
 cases.append('display A+B aliases A; no pair4/global-state read')
 # Physical held-key snapshot commands before the stock panic; both banks.
 root=0x80052e18;c.write(root+6,1,2);c.s('s0',root);c.s('s1',64)
 c.sent=[];call('b15_capture_prepare',2)
 assert [x>>16 for x in c.sent]==[0x4048,0x4048]
 assert [((x&65535)>>7)&3 for x in c.sent]==[1,3]
 assert [x&127 for x in c.sent]==[64,64]
 for p in (1,3):c.write(0x8000046c+2*((p>>1)*0x6b7+0x55),67,2)
 c.sent=[];call('b15_capture_commit',0,2,0x54,0)
 assert [x>>16 for x in c.sent]==[0x4049,0x4049] and all(x&127==67 for x in c.sent)
 cases.append('A+B instrument2 prepare/commit; final stored key; o32 clobber survival')
 # All four normal IDs counted at packed transport; control401c must NOT alias.
 call('b15_pic_init');c.sent=[]
 for cmd,p in ((0x1c,0),(0x5d,1),(0x81c,2),(0x85d,3)):
  call('b15_absolute_account',cmd<<16|4)
  assert c.read(S+12*p,2)==1
 call('b15_absolute_account',0x401c0001)
 assert [c.read(S+12*p,2) for p in range(4)]==[1]*4
 cases.append('A/B ordinary absolute completion ownership; 40xx family no alias')
 # Relative encoder A+B independent pair commands; preserves fifth argument frame.
 call('b15_pic_init')
 for bank in range(2):c.write(0x8000046c+2*(bank*0x6b7+0x12),1,2)
 c.sent=[];c.write(c.g('sp')+16,16,4);call('b15_encoder',0,2,0x1c,-1&0xffffffff)
 assert [x>>16 for x in c.sent]==[0x404b,0x404d]
 assert all(x&65535==65535 for x in c.sent)
 assert c.read(S,2)==1 and c.read(S+24,2)==1
 cases.append('A+B relative encoder; fifth-argument placement; signed reversal payload')
 # Repeated ordered reversals are independently counted; no algebraic coalescing.
 c.sent=[]
 for delta in (1,-1,16,-16)*100:
  call('b15_encoder',0,2,0x1c,delta&0xffffffff)
 assert len(c.sent)==800
 assert [x&65535 for x in c.sent]==[d&65535 for d in (1,-1,16,-16)*100 for _ in range(2)]
 assert c.read(S,2)==401 and c.read(S+24,2)==401
 # Signed clipping, counter wrap/overflow refusal and mixed enabled A/disabled B.
 for delta,want in ((100,16),(-100,65520)):
  c.sent=[];call('b15_encoder',0,0,0x1c,delta&0xffffffff)
  assert len(c.sent)==1 and c.sent[0]&65535==want
 c.write(S,65535,2);c.write(S+2,65535,2)
 assert call('b15_pic_edit',0)==1 and c.read(S,2)==0
 c.write(S,32767,2);c.write(S+2,0,2);before=c.read(S,64)
 assert not call('b15_pic_edit',0) and c.read(S,64)==before
 c.write(S,0,2);c.write(0x8000046c+2*(0x6b7+0x12),0,2)
 c.sent=[];c.stock_edits=[];call('b15_encoder',0,2,0x1c,1)
 assert len(c.sent)==1 and len(c.stock_edits)==1 and c.stock_edits[0][1]==1
 cases.append('800 ordered reversal packets; signed clips; counter wrap/overflow; mixed A+B stock routing')
 # Interior ISR adapter must preserve all caller registers it touches, and
 # rejoin the original housekeeping instead of returning out of the interrupt.
 c.write(c.g('sp')+20,0x404a,4);c.write(c.g('sp')+16,pkt(0,0,6),4)
 saved=c.r.copy();c.run(labels['b15_rx_entry'],{0x9d05153c})
 for r in ('ra','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','t8','t9','sp'):
  assert c.g(r)==saved[m.R[r]],r
 c.write(c.g('sp')+20,0x403d,4);saved=c.r.copy()
 c.run(labels['b15_rx_entry'],{0x9d0511ac})
 assert c.g('v0')==0x403d and c.g('v1')==0x402e and c.g('sp')==saved[m.R['sp']]
 cases.append('ISR volatile preservation and exact handled/unhandled rejoins')
 assert c.status==1
 # All emitted control transfers have a non-control delay slot and valid encoding.
 controls={'j','jal','jr','beq','bne','bltz','bgez','bgtz','blez','beql','bnel'}
 for off in range(len(code)//4):
  pc=m.BASE+0x2a0+4*off;row=decode(image,pc)
  if row[0] in controls:assert decode(image,pc+4)[0] not in controls
 report={'status':'COMPONENT_PASS_NOT_RELEASE','machine_code_executed':True,'cases':cases,
 'emitted_bytes':len(code),'code_fits_audited_region':len(code)<=0x960,
 'synthetic_execution_image_written':False,'o32_callee_saved_and_return_checked':True,
 'IRQ_status_restored':True,'limits':'External stock callees are contracts; no physical interrupt interleavings, integrated PIC payload, save/load caller gating or hardware execution.'}
 (OUT/'pic_execution_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

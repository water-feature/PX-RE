# SPDX-License-Identifier: GPL-2.0-or-later
"""Scoped tests of emitted PIC words, actual QNX execution and ELF metadata."""
import hashlib
from pathlib import Path
import struct,json,subprocess,math
import build as b
D=b.D
signed=lambda n:n-0x100000000 if n&0x80000000 else n
class CPU:
 def __init__(self,image):self.b=image;self.r=[0]*32;self.mem={};self.trace=[]
 def read(self,a,n):
  if b.BASE<=a<b.BASE+len(self.b):return int.from_bytes(self.b[a-b.BASE:a-b.BASE+n],'little')
  return sum(self.mem.get(a+i,0)<<(8*i) for i in range(n))
 def write(self,a,n,v):
  for i in range(n):self.mem[a+i]=(v>>(8*i))&255
 def plain(self,w):
  op=w>>26;s=(w>>21)&31;t=(w>>16)&31;d=(w>>11)&31;imm=w&65535;si=imm if imm<32768 else imm-65536;fn=w&63
  if op==0:
   if fn==0:self.r[d]=self.r[t]<<((w>>6)&31)
   elif fn==2:self.r[d]=self.r[t]>>((w>>6)&31)
   elif fn==33:self.r[d]=self.r[s]+self.r[t]
   elif fn==35:self.r[d]=self.r[s]-self.r[t]
   elif fn==37:self.r[d]=self.r[s]|self.r[t]
   elif fn==42:self.r[d]=int(signed(self.r[s])<signed(self.r[t]))
   elif fn==43:self.r[d]=int(self.r[s]<self.r[t])
   elif fn==11:
    if self.r[t]:self.r[d]=self.r[s]
   else:raise AssertionError(('unsupported R',hex(w)))
  elif op==9:self.r[t]=self.r[s]+si
  elif op==11:self.r[t]=int(self.r[s]<(si&0xffffffff))
  elif op==12:self.r[t]=self.r[s]&imm
  elif op==15:self.r[t]=imm<<16
  elif op in (35,37):self.r[t]=self.read((self.r[s]+si)&0xffffffff,4 if op==35 else 2)
  elif op in (41,43):self.write((self.r[s]+si)&0xffffffff,2 if op==41 else 4,self.r[t])
  else:raise AssertionError(('unsupported op',hex(w)))
  self.r=[v&0xffffffff for v in self.r];self.r[0]=0
 def run(self,pc,stop):
  for k in range(200):
   if pc==stop:return
   self.trace.append(pc);w=self.read(pc,4);op=w>>26;s=(w>>21)&31;t=(w>>16)&31;imm=w&65535;si=imm if imm<32768 else imm-65536;fn=w&63;target=None
   if op in (2,3):
    target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
    if op==3:self.r[31]=pc+8
   elif op in (4,5):target=pc+4+si*4 if ((self.r[s]==self.r[t])==(op==4)) else pc+8
   elif op==1 and t==0:target=pc+4+si*4 if signed(self.r[s])<0 else pc+8
   elif op==0 and fn==8:target=self.r[s]
   if target is None:self.plain(w);pc+=4
   else:self.plain(self.read(pc+4,4));pc=target
  raise AssertionError('execution limit')
def edit(image,ident,layer,rawA,rawB,delta,flag,maxv):
 c=CPU(image);sp=0x80070000;c.r[29]=sp;c.r[31]=0x9d077770
 saved={i:0x5a000000+i for i in range(16,24)}
 for i,v in saved.items():c.r[i]=v
 c.r[4:8]=[flag,layer,ident,delta&0xffffffff];c.write(sp+16,4,maxv)
 for lay,value in enumerate((rawA,rawB)):c.write(0x8000046c+2*(ident+lay*0x6b7),2,value)
 c.run(0x9d04fa6c,0x9d04dacc)
 assert c.r[29]==sp and c.r[31]==0x9d077770 and all(c.r[i]==v for i,v in saved.items())
 assert c.r[4:7]==[flag,layer,ident]
 return c.r[7],c

def uleb(buf,p):
 v=0;s=0
 while True:
  x=buf[p];p+=1;v|=(x&127)<<s;s+=7
  if not x&128:return v,p

def row_at(buf,code,start,target,initial=None):
 # Decode the actual parent FDE and proposed explicit-state FDE; only actual opcodes needed.
 p=0;pc=start;row={} if initial is None else dict(initial);stack=[]
 while p<len(code):
  op=code[p];p+=1
  if op==0:continue
  if op&0xc0==0x40:
   nxt=pc+(op&63)
   if nxt>target:break
   pc=nxt;continue
  if op==3:
   advance=struct.unpack_from('<H',code,p)[0];p+=2
   if pc+advance>target:break
   pc+=advance
  elif op==10:stack.append(dict(row))
  elif op==11:row=stack.pop()
  elif op==12:
   reg,p=uleb(code,p);off,p=uleb(code,p);row['CFA']=('register_offset',reg,off)
  elif op==15:
   n,p=uleb(code,p);row['CFA']=('expression',code[p:p+n].hex());p+=n
  elif op==16:
   reg,p=uleb(code,p);n,p=uleb(code,p);row[reg]=('expression',code[p:p+n].hex());p+=n
  else:raise AssertionError(('CFI opcode',hex(op)))
 return row

def main():
 pic=(D/'pic_2.2.2.2.0_B16_offline.bin').read_bytes();app=(D/'voice_2.2.2.2.0_B16_offline_qnx.elf').read_bytes();oldpic=b.PIC.read_bytes();oldapp=b.QNX.read_bytes();build=json.loads((D/'build_results.json').read_text())
 assert b.sha(pic)==build['PIC_sha256'] and b.sha(app)==build['QNX_sha256']
 # Actual instruction execution through existing B11 wrapper/common frame into setter.
 sync=0;non=0;rank=lambda r:17-r if r>=16 else r+2
 for ident in (0x1d,0x5e):
  for layer in (0,1,2):
   for flag in (0,1):
    for raw in range(18):
     for delta in list(range(-128,129))+[-32768,32767,-2147483648,2147483647]:
      aa,bb=raw,(raw+7)%18;selected=aa if layer!=1 else bb
      result,c=edit(pic,ident,layer,aa,bb,delta,flag,17)
      k=signed((rank(selected)+delta)&0xffffffff);k=max(0,min(17,k));want=17-k if k<2 else k-2
      assert result==want
      assert 0x9d000e00 in c.trace and 0x9d0816e0 in c.trace
      sync+=1
 for ident in range(0x6b7):
  if ident in (0x1d,0x5e):continue
  for layer in (0,1,2):
   for delta in (-128,-1,0,1,128):
    a,_=edit(oldpic,ident,layer,63,127,delta,1,127);z,c=edit(pic,ident,layer,63,127,delta,1,127)
    assert a==z and 0x9d000e00 in c.trace;non+=1
 # Hook delay slot and preserved surrounding logic.
 assert pic[0x4fab8:0x4fb10]==oldpic[0x4fab8:0x4fb10]
 assert pic[:0xe00]==oldpic[:0xe00] and pic[0xec0:0x1000]==oldpic[0xec0:0x1000]
 for o in (0x475f4,0x47900):assert struct.unpack_from('<H',pic,o)[0]==17
 oldlabels=[];labels=[]
 for i in range(18):
  ptr=struct.unpack_from('<I',pic,0xe64+4*i)[0]-b.BASE;s=pic[ptr:].split(b'\0',1)[0].decode();labels.append(s)
  if i<16:
   oldptr=struct.unpack_from('<I',oldpic,0x62074+4*i)[0]-b.BASE;oldlabels.append(oldpic[oldptr:].split(b'\0',1)[0].decode());assert labels[-1]==oldlabels[-1]
 assert labels[16:]==['1/32 Step','1/64 Step']
 # New/old codes remain raw 16-bit values; codec model, not on-device preset I/O.
 codec=0
 for r in range(18):
  for ident in (0x1d,0x5e):
   for layer in (0,1):
    stored=struct.pack('<H',r);assert struct.unpack('<H',stored)[0]==r
    wire=(r&127,(r>>7)&127);assert wire[0]+(wire[1]<<7)==r;codec+=1
 # Exact emitted transport checksum arithmetic on all 130 PIC blocks.
 blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)];gp=0x80007ff0;c=CPU(pic);c.r[28]=gp
 for block in blocks:
  c.write(gp-0x7f20,4,0);pcs=range(0x9d044484,0x9d04449c,4) if len(block)==4096 else range(0x9d04466c,0x9d044684,4)
  for lo,hi in zip(block[::2],block[1::2]):
   c.write(gp-0x7f1c,4,lo);c.r[2]=hi
   for pc in pcs:c.plain(c.read(pc,4))
  expected=sum(struct.unpack('<'+'H'*(len(block)//2),block))&65535;assert c.read(gp-0x7f20,2)==expected
  for value in (expected,expected^1):
   c.r[2]=value&255;c.r[5]=value>>8;c.r[3]=expected
   for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):c.plain(c.read(pc,4))
   assert (c.r[2]==c.r[3])==(value==expected)
 # ELF load extents and all original unwind-index entries are untouched.
 ns,secs,ph,*_=b.elf(app);ons,osecs,oph,*_=b.elf(oldapp)
 assert [x for x in ph if x[0]==1]==[x for x in oph if x[0]==1]
 assert app[0x10300c:0x104c74]==oldapp[0x10300c:0x104c74]
 count=struct.unpack_from('<I',app,0x103008)[0];assert count==910
 entries=[struct.unpack_from('<ii',app,0x10300c+i*8) for i in range(count)];assert [x[0] for x in entries]==sorted(set(x[0] for x in entries))
 assert entries[-1]==(0x101700-0x103000,0x10277c-0x103000)
 # The inherited aggregate contains object-file zero terminators (first at 0x1025a0).
 # Its authoritative runtime search path is the existing global sorted index.
 # Validate every indexed FDE independently; do not alter inherited terminators.
 for initial,relative in entries:
  f=0x103000+relative;n,delta,pc,span=struct.unpack_from('<IIiI',app,f)
  assert n>=12 and f+n+4<=len(app)
  assert f+8+pc==0x103000+initial
  cie=f+4-delta;assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',app,cie+4)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
 # Last baseline FDE ends exactly where the appended record begins.
 last=0x103000+entries[-2][1]
 assert last+4+struct.unpack_from('<I',oldapp,last)[0]==0x10277c
 p=0x10277c;n,delta,pc,span=struct.unpack_from('<IIiI',app,p);assert p+4-delta==0x92fd8 and p+8+pc==0x101700 and span==136
 oldn=struct.unpack_from('<I',app,0x95338)[0];oldcode=app[0x95338+17:0x95338+4+oldn]
 newcode=app[p+17:p+4+n]
 oldrow=row_at(app,oldcode,0x195d0,0x1ae55);newrow=row_at(app,newcode,0x101700,0x101700);assert oldrow==newrow,(oldrow,newrow)
 # Execute emitted x86_64 instructions in an isolated host harness.
 result=subprocess.run([str(D/'native_mapper_test'),str(b.QNX),str(D/'voice_2.2.2.2.0_B16_offline_qnx.elf')],check=True,capture_output=True,text=True)
 native=json.loads(result.stdout)
 b.put('native_mapper_results.json',(json.dumps(native,indent=2)+'\n').encode())
 report={'status':'PASS','PIC_sha256':b.sha(pic),'QNX_sha256':b.sha(app),'PIC_sync_emitted_instruction_cases':sync,'PIC_nonSync_baseline_comparisons':non,'PIC_call_frame_registers_delay_slots':'PASS: actual emitted words, scoped software interpreter','PIC_display_labels':labels,'preset_transport_codec_model_cases':codec,'preset_storage_and_transport_instructions':'UNCHANGED, except two metadata maxima; codec model only','PIC_transport_blocks':len(blocks),'PIC_valid_corrupt_checksum_comparisons':len(blocks)*2,'ELF_PT_LOAD_unchanged':True,'original_unwind_entries_preserved':909,'new_unwind_row_matches_original_at_hook':True,'new_FDE_index_lookup':'PASS; all 910 indexed FDEs validated, new record contiguous with last existing FDE','linear_scan_limit':'Inherited .b15_eh_frame has internal zero terminators; no claim of whole-section linear enumeration','CFI_state':str(newrow),'QNX_native':native,'outside_B16_ranges_unchanged':True,'hardware':'NOT VERIFIED','limitations':['PIC instruction interpreter is scoped, not a complete PIC32 emulator','native QNX mapper test excludes surrounding audio engine and executes via Rosetta','CFI structurally validated, not tested with QNX unwinder','preset codec model and unchanged-code comparison are not on-device preset recall','risk-assessed PIC allocation and undocumented bootloader/computed references remain hardware risks']}
 b.put('validation_results.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report,indent=2))
if __name__=='__main__':main()

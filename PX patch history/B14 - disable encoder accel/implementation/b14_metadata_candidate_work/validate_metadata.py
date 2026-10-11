# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute candidate/stock metadata and real SPI/formatter words against an SPI model.
Only parameter getters/bounds/unrelated UI notification contracts are summarized.
SPI model covers CS, command/address, receive FIFO, bounded delays and fault completion.
No elapsed-time/silicon/display claim.
"""
from pathlib import Path
import sys,json,hashlib,struct,random,itertools
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'b9_250_candidate_work'));import mips_check as m
OLD=(R/'b14_packaging_work/pic_2.2.2.1.4.bin').read_bytes();NEW=(O/'pic_B14_metadata_bulk_read_unpackaged.bin').read_bytes()
manifest=json.loads((O/'patch_manifest.json').read_text())
assert hashlib.sha256(OLD).hexdigest()==manifest['baseline_sha256']
assert hashlib.sha256(NEW).hexdigest()==manifest['candidate_sha256']
STOP=0x9d081950;PARAM=0x8000046c;META=0x80037d3c;DIRTY=0x80053930
BUF=0xbf821420;STAT=0xbf821410;CSCLR=0xbf860134;CSSET=0xbf860138
orig_decode=m.decode
def decode(image,pc):
 w=struct.unpack_from('<I',image,pc-m.BASE)[0];op=w>>26;rs=w>>21&31;rt=w>>16&31;rd=w>>11&31;sa=w>>6&31;fn=w&63
 if op==31 and fn==0:return ('ext',m.REGS[rt],m.REGS[rs],sa,rd+1)
 if op==0 and fn==3:return ('sra',m.REGS[rd],m.REGS[rt],sa)
 if op==0 and fn==24:return ('mult',m.REGS[rs],m.REGS[rt])
 if op==0 and fn in (16,18):return ('mfhi' if fn==16 else 'mflo',m.REGS[rd])
 if op in (42,46):
  imm=w&65535;return ('swl' if op==42 else 'swr',m.REGS[rt],imm if imm<32768 else imm-65536,m.REGS[rs])
 return orig_decode(image,pc)
m.decode=decode
class CPU(m.CPU):
 def __init__(self,image,record=None,delay=0,fault=None):
  self.cs=False;self.tx=[];self.transactions=[];self.header=[];self.address=0;self.rx=0;self.polls=0;self.status_polls=[];self.spi_reads=[]
  self.delay=delay;self.fault=fault;self.wait=0;self.transfer_index=-1;self.record=record or bytes(range(64));self.flash={};self.metadata=[];self.notify=[];self.hi=0;self.lo=0
  super().__init__(image)
  self.write(0x80006ffe,1,2)
  for part in (0,1):
   for inst in (0,1):
    for par,val in ((0x22,2),(0x23,3),(0x24,1),(0x11,1)):
     self.write(PARAM+part*0xd6e+2*(par+0x41*inst),val,2)
  for group in range(97):
   for cat in range(17):self.write(0x80037e94+(group*17+cat)*8,100*group+cat,4)
  for off in (-0x7c8c,-0x7c88,-0x7cac,-0x7ca8):self.write(m.GP+off,-1,4)
  for i in range(256):self.write(META-32+i,0x9b,1)
  self.writes=[]
 def read(self,a,n):
  a&=0xffffffff
  if a==STAT:
   self.polls+=1
   if self.wait>0:self.wait-=1;return 0
   return 1
  if a==BUF:
   self.spi_reads.append(self.rx);return self.rx
  return super().read(a,n)
 def write(self,a,v,n):
  a&=0xffffffff
  if a==CSCLR and v&0x8000:
   assert not self.cs;self.cs=True;self.header=[];self.transactions.append([])
  if a==CSSET and v&0x8000:
   assert self.cs;self.cs=False
  if a==BUF:
   assert self.cs
   v&=255;self.tx.append(v);self.transactions[-1].append(v);self.transfer_index+=1
   if len(self.header)<4:
    self.header.append(v);assert self.header[0]==3
    if len(self.header)==4:self.address=int.from_bytes(bytes(self.header[1:]),'big')
    self.rx=0x5a
   else:
    assert v==0
    self.rx=self.flash.get(self.address,self.record[self.address&63]);self.address=(self.address+1)&0xffffff
   delay=self.delay(self.transfer_index) if callable(self.delay) else self.delay
   self.wait=100000 if self.fault==self.transfer_index or self.fault=='all' else delay
  super().write(a,v,n)
 def simple(self,row):
  op,*a=row
  if op=='ext':self.s(a[0],self.g(a[1])>>a[2]&((1<<a[3])-1));return
  if op=='sra':self.s(a[0],m.signed(self.g(a[1]))>>a[2]);return
  if op=='mult':
   value=(m.signed(self.g(a[0]))*m.signed(self.g(a[1])))&0xffffffffffffffff
   self.lo=value&0xffffffff;self.hi=value>>32;return
  if op in ('mfhi','mflo'):self.s(a[0],self.hi if op=='mfhi' else self.lo);return
  if op in ('swl','swr'):
   addr=(self.g(a[2])+a[1])&0xffffffff;word=self.g(a[0]).to_bytes(4,'little');k=addr&3
   if op=='swl':
    for j in range(k+1):self.write((addr&~3)+j,word[3-k+j],1)
   else:
    for j in range(4-k):self.write(addr+j,word[j],1)
   return
  super().simple(row)
 def getter(self,part,par):return self.read(PARAM+(part&1)*0xd6e+par*2,2)
 def external(self,pc):
  a=[self.g(x) for x in ('a0','a1','a2','a3')]
  if pc==0x9d041048:self.metadata.append(a[:2]);return False
  if pc==0x9d04d300:self.s('v0',self.getter(a[0],a[1]));return True
  if pc==0x9d04d4fc:self.s('v0',a[2]&65535);return True
  if pc==0x9d0816e0:self.s('v0',max(0,min(a[2],a[0]+m.signed(a[1]))));return True
  if pc in (0x9d0792e0,0x9d079300):self.s('v0',16);return True
  if pc==0x9d01e318:self.s('v0',1);return True
  if pc==0x9d01e334:self.s('v0',3);return True
  if pc in (0x9d04d7b8,0x9d01d4bc,0x9d01b46c,0x9d036a28):arity={0x9d04d7b8:2,0x9d01d4bc:0,0x9d01b46c:2,0x9d036a28:3}[pc];self.notify.append((hex(pc),a[:arity]));self.s('v0',0);return True
  if pc in (0x9d080e2c,0x9d080e60):self.s('v0',a[0]);return True
  return False
 def call(self,part,inst,slot=3,head=None):
  self.write(PARAM+part*0xd6e+2*(0x23+0x41*inst),slot,2)
  if head is not None:self.write(0x80037e94+(2*17+1)*8,head,4)
  self.s('a0',part);self.s('a1',inst);self.s('ra',STOP);before=self.r.copy();sp=self.g('sp');guard=self.read(sp,32)
  self.run(0x9d041048,{STOP},maxsteps=1500000)
  for reg in [*m.REGS[16:24],'gp','sp','fp']:assert self.g(reg)==before[m.R[reg]],reg
  assert self.g('ra')==STOP and self.read(sp,32)==guard and not self.cs
  return bytes(self.read(META+(part*2+inst)*64+i,1) for i in range(64)),self.g('v0')
def compare(part,inst,record,delay=0,slot=3,head=None):
 a=CPU(OLD,record,delay);b=CPU(NEW,record,delay)
 av=a.call(part,inst,slot,head);bv=b.call(part,inst,slot,head);assert av==bv,(part,inst,record.hex(),av,bv)
 for i in range(-32,256):assert a.read(META+i,1)==b.read(META+i,1),(i,av,bv)
 assert a.metadata==b.metadata and a.notify==b.notify
 if slot and head!=-1:
  assert len(a.tx)==320 and len(a.transactions)==64 and len(b.tx)==68 and len(b.transactions)==1
  addresses=[int.from_bytes(bytes(t[1:4]),'big') for t in a.transactions]
  start=int.from_bytes(bytes(b.transactions[0][1:4]),'big')
  assert addresses==list(range(start,start+64))
 else:assert not a.tx and not b.tx
 return a,b
records=[bytes(range(64)),bytes(64),bytes([255])*64,bytes([0x7f])*64,bytes([0x80])*64]
rng=random.Random(1406)
for _ in range(24):records.append(bytes(rng.randrange(256) for i in range(64)))
# Ensure normal/ff attributes and error-name path cover all directions and ASCII lengths.
records += [bytes(list(range(44))+[v,5]+list(range(46,64))) for v in (0,1,254,255)]
normal=0
for part,inst,record in itertools.product((0,1),(0,1),records):compare(part,inst,record);normal+=1
special=0
for part,inst in itertools.product((0,1),(0,1)):
 for slot,head in ((0,None),(3,-1)):compare(part,inst,records[0],slot=slot,head=head);special+=1
 for slot in (1,9,10,99,100,999,1000,65534,65535):compare(part,inst,bytes([255])*64,slot=slot,head=0);special+=1
waitcases=0
for delay in (1,2,7,63,249):
 for part,inst in itertools.product((0,1),(0,1)):compare(part,inst,records[0],delay=delay);waitcases+=1
for seed in range(8):
 r=random.Random(seed);delays=[r.randrange(8) for _ in range(320)]
 compare(seed&1,seed>>1&1,records[seed],delay=lambda i:delays[i]);waitcases+=1
# Fault contract: bounded completion and CS release, not successful data equivalence.
faultcases=[]
for fault in (0,1,2,3,4,5,25,47,67,'all'):
 c=CPU(NEW,records[0],fault=fault);c.call(0,0)
 assert len(c.tx)==68 and len(c.transactions)==1 and not c.cs
 assert c.polls<=68*250
 faultcases.append({'transfer':fault,'polls':c.polls,'bounded':True,'CS_released':True})
# Execute whole dedicated routes with real metadata SPI and dependent-attribute getters.
routes=[]
for kind in ('Instrument','Type'):
 for part,inst,gate,delta,group in itertools.product((0,1),(0,1),(0,1),(-1,1),((0,1) if kind=='Type' else (0,))):
  pair=[]
  for image in (OLD,NEW):
   c=CPU(image,records[0]);c.write(0x80006ffe,gate,2);state=0x80052e18;event=0x80060000
   c.write(state+6,inst,2);c.write(state+0x44,part,2);c.write(state+0x20,group,2);c.write(event+8,delta,4)
   c.s('a0',state);c.s('a1',event);c.s('s0',state);c.s('s1',event)
   c.run(0x9d02a6b0 if kind=='Instrument' else 0x9d02a74c,{0x9d0291c8},maxsteps=100000)
   pair.append(c)
  a,b=pair
  assert a.metadata==b.metadata and a.notify==b.notify,(kind,part,inst,gate,delta,group,a.metadata,b.metadata,a.notify,b.notify)
  assert bytes(a.read(PARAM+i,1) for i in range(0x1adc))==bytes(b.read(PARAM+i,1) for i in range(0x1adc))
  assert bytes(a.read(META+i,1) for i in range(256))==bytes(b.read(META+i,1) for i in range(256))
  assert [a.read(DIRTY+4*i,4) for i in range(6)]==[b.read(DIRTY+4*i,4) for i in range(6)]
  reads=(1+gate) if kind=='Instrument' else gate
  assert len(a.transactions)==reads*64 and len(b.transactions)==reads
  assert len(a.tx)==reads*320 and len(b.tx)==reads*68
  routes.append({'kind':kind,'part':part,'instrument':inst,'output_gate':gate,'delta':delta,'group':group,'records':reads,'baseline_SPI_bytes':len(a.tx),'candidate_SPI_bytes':len(b.tx)})
diff=[i for i,(a,b) in enumerate(zip(OLD,NEW)) if a!=b]
assert len(NEW)==len(OLD)==530784 and all(any(lo<=i<hi for lo,hi in ((0x411c8,0x41214),(0x41278,0x41280))) for i in diff)
report={'status':'PASS','candidate_sha256':hashlib.sha256(NEW).hexdigest(),'record_equivalence_cases':normal,'special_format_slot_zero_missing_cases':special,'delayed_ready_equivalence_cases':waitcases,'fault_bounded_completion_cases':faultcases,'dedicated_handler_cases':routes,'all_other_bytes_identical_to_1_4':True,'SPI_implementation':'Actual 40230 prefix, 420cc byte-transfer and stock single-byte 40a4c execute; CS/FIFO/flash hardware modeled','formatter_implementation':'Actual 5f770 decimal conversion, f850 strcpy, fcec strlen and SWL/SWR suffix writes execute','limits':'No silicon/timing/visible-display guarantee; SPI fault content may differ because stock has no error/retry return. IRQ ownership audited separately.'}
(O/'validation_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {normal} records, {special} special/error, {waitcases} ready delays, {len(faultcases)} bounded faults, {len(routes)} full handlers; unchanged .1.4 display/B9/detents')
if __name__=='__main__':pass

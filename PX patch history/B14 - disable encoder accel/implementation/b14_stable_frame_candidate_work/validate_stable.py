"""Run actual emitted control words with explicit drawing and OLED contracts."""
from pathlib import Path
import sys,json,hashlib,random,struct
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'b9_250_candidate_work'));import mips_check as m
BASE=m.BASE;GP=m.GP;STOP=0x9d081950;DIRTY=0x80053930
FLAG=GP-0x7fef;COUNT=GP-0x7dec;SELECT=GP-0x7de4
old=(ROOT/'b14_metadata_packaging_work/pic_2.2.2.1.6.bin').read_bytes()
new=(OUT/'pic_B14_stable_frame_unpackaged.bin').read_bytes()
orig=m.decode
def decode(image,pc):
 w=int.from_bytes(image[pc-BASE:pc-BASE+4],'little')
 if w>>26==31 and w&63==32 and w>>6&31==24:return ('seh',m.REGS[w>>11&31],m.REGS[w>>16&31])
 return orig(image,pc)
m.decode=decode
class CPU(m.CPU):
 def __init__(self,image=new):
  super().__init__(image);self.inside_render=False;self.fields=[];self.rows=[]
  self.want=[0]*6;self.have=[0]*6;self.screen=[None]*128;self.frame=None;self.frames=[];self.secondary_rows=[]
  self.write(FLAG,1,1);self.write(COUNT,0,2);self.write(GP-0x7fee,1,1);self.write(GP-0x7ff0,1,1)
  self.s('s5',1)
 def simple(self,row):
  if row[0]=='seh':
   v=self.g(row[2])&65535;self.s(row[1],v if v<32768 else v-65536);return
  super().simple(row)
 def render(self):
  before=self.r.copy();ra=self.g('ra');sp=self.g('sp');self.s('ra',STOP);pc=BASE+0x3ed0c
  initial_fields=len(self.fields);initial_frame=self.frame;initial_have=self.have.copy()
  while True:
   stop=self.run(pc,{STOP,BASE+0x3ed84},maxsteps=2000)
   if stop==STOP:break
   assert self.read(FLAG,1)==1, 'draw while transfer active'
   assert self.g('sp')==sp-104
   field=self.g('s0');assert 0<=field<6
   self.fields.append(field);self.have[field]=self.want[field]
   # Summary of unchanged field drawing, with ABI-adversarial clobbers.
   for i in [*range(1,16),24,25]:self.r[i]=0xbad00000+i
   for off in range(0,16,4):self.write(self.g('sp')+off,0xdecafbad,4)
   self.s('s1',DIRTY+24);self.s('s2',DIRTY);pc=BASE+0x3ee4c
  for reg in [*m.REGS[16:24],'gp','sp','fp']:assert self.g(reg)==before[m.R[reg]],reg
  self.s('ra',ra)
  if len(self.fields)>initial_fields:
   assert self.have==self.want
   assert (self.read(FLAG,1),self.read(COUNT,2))==(0,128)
   self.frame=tuple(self.have);self.frames.append(self.frame)
  else:assert self.frame==initial_frame and self.have==initial_have
  assert len(self.fields)-initial_fields<=6
 def external(self,pc):
  if pc==BASE+0x3ed0c and not self.inside_render:
   self.inside_render=True;self.render();self.inside_render=False;return True
  if pc==BASE+0x3de2c:return True # independent secondary rendering, writes only buffer2
  if pc==BASE+0x72608:
   row=self.g('a0');assert 1<=row<=128
   self.secondary_rows.append(row);return True
  if pc==BASE+0x72294:
   row=self.g('a0');assert 1<=row<=128
   assert self.read(FLAG,1)==0 and tuple(self.have)==self.frame
   self.rows.append((row,self.frame));self.screen[row-1]=self.frame
   ra=self.g('ra')
   for i in [*range(1,16),24,25]:self.r[i]=0xbad00000+i
   self.s('ra',ra);return True
  return False
 def change(self,mask):
  for i in range(6):
   if mask>>i&1:self.want[i]+=1;self.write(DIRTY+i*4,1,4)
 def advance(self):self.s('s5',1);self.run(BASE+0x532e8,{BASE+0x532fc},maxsteps=5000)
 def pending(self):return any(self.read(DIRTY+4*i,4) for i in range(6))
 def drain(self):
  n=0
  while self.pending() or self.read(FLAG,1)==0:
   self.advance();n+=1;assert n<=259
  assert all(x==tuple(self.want) for x in self.screen)
  return n

# Guard must preserve all pending dirty flags and ABI when transfer is active.
guard_cases=0
for count in range(129):
 for mask in range(64):
  c=CPU();c.change(mask);c.write(FLAG,0,1);c.write(COUNT,count,2)
  before=c.r.copy();mem=dict(c.mem);c.inside_render=True;c.render()
  assert c.mem==mem and not c.fields
  assert all(c.r[i]==before[i] for i in range(32) if i!=2)
  guard_cases+=1
render_cases=0
for mask in range(64):
 c=CPU();c.change(mask);c.inside_render=True;c.render()
 assert c.fields==[i for i in range(6) if mask>>i&1] and not c.pending()
 render_cases+=1
secondary_guard_cases=0
for count in range(129):
 for mask in (0,6,7,48,56,63):
  c=CPU();c.change(mask);c.write(GP-0x7ff0,0,1);c.write(GP-0x7dea,count,2)
  mem=dict(c.mem);c.inside_render=True;c.render()
  assert c.mem==mem and not c.fields
  secondary_guard_cases+=1

# Resume cancels before drawing: execute call-site hook and its actual delay.
resume_cases=0
for flag in (0,1):
 for count in (0,1,64,128):
  c=CPU();c.write(FLAG,flag,1);c.write(COUNT,count,2);before=c.r.copy()
  c.run(BASE+0x298d8,{BASE+0x298e0})
  assert (c.read(FLAG,1),c.read(COUNT,2),c.read(SELECT,4))==(1,0,1)
  assert all(c.r[i]==before[i] for i in range(32) if i not in (2,31))
  assert c.g('ra')==BASE+0x298e0;resume_cases+=1

# Cancellation wrappers are checked up to original bodies; stock drawing/clear
# bodies remain exact baseline bytes. Original stack and RA stores must match.
wrapper_cases=0
for entry,stop,frame,primary_only in [(0x3ecb0,0x3ecb8,24,False),(0x7e408,0x7e410,24,True),(0x7e274,0x7e27c,0,True)]:
 for flag in (0,1):
  for count in (0,1,64,128):
   for index in (0,1,2):
    c=CPU();c.write(FLAG,flag,1);c.write(COUNT,count,2);c.s('a0',index);c.s('ra',STOP)
    before=c.r.copy();c.run(BASE+entry,{BASE+stop})
    expected=(1,0) if not primary_only or index==1 else (flag,count)
    assert (c.read(FLAG,1),c.read(COUNT,2))==expected
    for reg in [*m.REGS[16:24],'gp','fp']:assert c.g(reg)==before[m.R[reg]],reg
    assert c.g('sp')==before[29]-frame
    if frame:assert c.read(c.g('sp')+20,4)==STOP
    else:
     reference=CPU(old);reference.r=before.copy()
     reference.run(BASE+entry,{BASE+stop})
     assert c.r==reference.r, 'leaf clear replay must match baseline register state'
    if entry==0x3ecb0:assert all(c.read(DIRTY+4*i,4)==1 for i in range(6))
    wrapper_cases+=1
blank_cases=0
for flag in (0,1):
 for count in (0,1,64,128):
  c=CPU();c.write(FLAG,flag,1);c.write(COUNT,count,2);c.s('v0',1)
  args=[c.g(r) for r in ('a0','a1','a2','a3')]
  c.run(BASE+0x29ce0,{BASE+0x6a8cc})
  assert (c.read(FLAG,1),c.read(COUNT,2),c.read(SELECT,4))==(1,0,1)
  assert c.g('ra')==BASE+0x29ce8 and args==[c.g(r) for r in ('a0','a1','a2','a3')]
  blank_cases+=1
clear_destination_cases=0
for entry in (0x7e274,0x7e408):
 for index in (0,1,2):
  for count in (0,1,64,128):
   a=CPU(old);b=CPU();a.s('a0',index);b.s('a0',index)
   a.s('ra',STOP);b.s('ra',STOP)
   for c in (a,b):c.write(FLAG,0,1);c.write(COUNT,count,2)
   a.run(BASE+entry,{BASE+0x80f4c});b.run(BASE+entry,{BASE+0x80f4c})
   assert a.r==b.r, 'clear destination/call registers must match original instructions'
   assert b.g('a0')==0x8003a458+index*0x8008 and b.g('a1')==0 and b.g('a2')==32768
   clear_destination_cases+=1

# Independent idle/frozen policy oracle: rendered latest state at idle only,
# row counter always decreases through a complete generation during input.
def oracle(flag,count,dirty,eligible):
 if not eligible:return flag,count,dirty,None,False
 rendered=bool(flag and dirty)
 if rendered:flag,count,dirty=0,128,0
 row=None
 if flag==0:
  if count:row=count;count-=1
  else:flag=1
 return flag,count,dirty,row,rendered
stream_cases=[]
for mask in (3,6,7,24,48,56,63):
 for period in (1,2,3,8,128,160):
  c=CPU();flag,count,dirty=1,0,0;oracle_frames=0
  for step in range(512):
   if step%period==0:c.change(mask);dirty|=mask
   f,n,d,row,rendered=oracle(flag,count,dirty,True)
   prior=len(c.rows);c.advance()
   assert (c.read(FLAG,1),c.read(COUNT,2))==(f,n)
   assert c.pending()==bool(d)
   actual=c.rows[prior:];assert [x[0] for x in actual]==([] if row is None else [row])
   flag,count,dirty=f,n,d;oracle_frames+=rendered
  assert len(c.frames)==oracle_frames and len(c.frames)>=3
  # Every completed frame is128 consecutive row sends from an immutable image.
  for i in range(len(c.rows)//128):
   block=c.rows[i*128:(i+1)*128]
   assert [x[0] for x in block]==list(range(128,0,-1))
   assert len({x[1] for x in block})==1
  drained=c.drain()
  stream_cases.append({'mask':mask,'period':period,'frames_started':len(c.frames),'drain_passes':drained})
random_cases=0
for seed in range(20):
 rng=random.Random(seed);c=CPU();flag,count,dirty=1,0,0
 for step in range(512):
  if rng.random()<.7:
   mask=rng.randrange(1,64);c.change(mask);dirty|=mask
  eligible=rng.random()<.8;c.write(GP-0x7fee,int(eligible),1)
  flag,count,dirty,row,rendered=oracle(flag,count,dirty,eligible)
  before=len(c.rows);c.advance()
  assert (c.read(FLAG,1),c.read(COUNT,2))==(flag,count)
  assert c.pending()==bool(dirty)
  assert [x[0] for x in c.rows[before:]]==([] if row is None else [row])
 c.write(GP-0x7fee,1,1);c.drain();random_cases+=1

# One-time frame remains equivalent to stock when at most one field is dirty.
equivalence_cases=0
for mask in (0,1,2,4,8,16,32):
 a=CPU(old);b=CPU();a.change(mask);b.change(mask)
 for step in range(132):a.advance();b.advance()
 assert a.rows==b.rows and a.have==b.have and a.screen==b.screen
 equivalence_cases+=1
transition_cases=0
for cut in (0,1,63,64,127,128):
 for transition in ('page','resume','blank_wake','primary_clear','secondary_clear'):
  c=CPU();c.change(63);c.inside_render=True;c.render();c.inside_render=False
  for _ in range(cut):c.advance()
  c.change(63);rows_before=len(c.rows)
  if transition=='page':
   c.s('ra',STOP);c.run(BASE+0x3ecb0,{BASE+0x3ecb8})
   # Summary of unchanged page clear/divider body and original epilogue.
   c.have=[-1]*6;c.s('sp',c.g('sp')+24);c.s('ra',STOP)
  elif transition=='resume':
   c.run(BASE+0x298d8,{BASE+0x298e0})
   # Wake path subsequently calls the actual full-dirty invalidator.
   c.s('ra',STOP);c.run(BASE+0x3ec50,{STOP})
  elif transition=='blank_wake':
   c.s('v0',1);c.run(BASE+0x29ce0,{BASE+0x6a8cc});c.have=[-1]*6
   # Original synchronous blank transfer is summarized; wake invalidates all.
   c.run(BASE+0x298d8,{BASE+0x298e0});c.s('ra',STOP);c.run(BASE+0x3ec50,{STOP})
  else:
   index=1 if transition=='primary_clear' else 2
   c.s('a0',index);c.s('ra',STOP);c.run(BASE+0x7e274,{BASE+0x7e27c})
   if index==1:c.have=[-1]*6;c.run(BASE+0x3ec50,{STOP})
  if transition=='secondary_clear':
   assert c.read(FLAG,1)==0 and c.read(COUNT,2)==128-cut
  else:assert (c.read(FLAG,1),c.read(COUNT,2))==(1,0)
  c.drain()
  # After cancellation only latest-generation rows are sent. The secondary
  # path finishes the unchanged old generation before the latest one.
  after=c.rows[rows_before:]
  if transition!='secondary_clear':
   assert len(after)==128 and [x[0] for x in after]==list(range(128,0,-1))
   assert all(x[1]==tuple(c.want) for x in after)
  transition_cases+=1
secondary_fairness_cases=0
for mask in (6,7,48,56,63):
 for secondary_count in (2,64,128):
  c=CPU();c.change(mask);c.inside_render=True;c.render();c.inside_render=False
  # Existing secondary renderer starts a transfer alongside the first frame.
  c.write(GP-0x7ff0,0,1);c.write(GP-0x7dea,secondary_count,2)
  for step in range(128):c.change(mask);c.advance()
  assert c.read(COUNT,2)==0 and not c.secondary_rows
  c.advance() # Finish primary; secondary remains pending.
  frame_count=len(c.frames)
  for step in range(secondary_count//2):
   c.change(mask);c.advance()
   assert len(c.frames)==frame_count
  assert c.secondary_rows==list(range(secondary_count,0,-1))
  c.advance() # Existing secondary completion marks idle.
  assert c.read(GP-0x7ff0,1)==1
  c.advance();assert len(c.frames)==frame_count+1
  assert c.frame==tuple(c.want);c.drain();secondary_fairness_cases+=1
report={'status':'PASS','candidate_sha256':hashlib.sha256(new).hexdigest(),
 'guard_cases':guard_cases,'secondary_guard_cases':secondary_guard_cases,'secondary_fairness_cases':secondary_fairness_cases,'render_masks':render_cases,'resume_cases':resume_cases,
 'cancellation_wrapper_cases':wrapper_cases,'clear_destination_equivalence_cases':clear_destination_cases,'blank_cases':blank_cases,'sustained_stream_cases':stream_cases,
 'random_gated_cases':random_cases,'stock_equivalence_cases':equivalence_cases,'mid_transfer_transition_cases':transition_cases,
 'limits':['Drawing glyph/pixel bodies and OLED hardware are explicit summaries.',
 'Main-pass counts are not milliseconds; synchronous replay cost remains unchanged.',
 'No silicon timing, visual tearing, physical edge acquisition or arbitrary-pointer ownership proof.']}
(OUT/'validation_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sustained_stream_cases'},indent=2))

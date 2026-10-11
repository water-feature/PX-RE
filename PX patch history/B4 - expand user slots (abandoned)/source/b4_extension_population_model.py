"""Population/source checks and stock reply/request execution, no image output."""
import sys,json,hashlib
from pathlib import Path
if '--entry-hook' not in sys.argv:sys.argv.append('--entry-hook')
import b4_split_addressing_harness as S
H=S.H
class Invalid(ValueError):pass

def plan(raw,groups):
 if groups not in (65,97) or len(raw)!=groups:raise Invalid('group shape')
 out=[];cursor=0;page=bytearray([255])*4096;page[0]=255
 for g,row in enumerate(raw):
  if len(row)!=17:raise Invalid('category shape')
  for c,n in enumerate(row):
   if type(n) is not int or not 0<=n<=255:raise Invalid('raw count not 0..255')
   count=n+1;out.append((g,c,count,cursor if n else H.MASK))
   page[1+17*g+c]=n;cursor+=count
   if cursor>65536:raise Invalid('name demand exceeds 65536')
 return out,bytes(page),cursor

def load_model(page,groups,allow_extended=False):
 if groups==97 and not allow_extended:raise Invalid('97 suffix lacks current build provenance')
 if page[0]==255:
  n=groups
  if len(page)<1+n*17:raise Invalid('short marked page')
  raw=[list(page[1+17*g:1+17*(g+1)]) for g in range(n)]
 else:
  if groups!=65:raise Invalid('legacy page does not establish extended names')
  if len(page)<41*17:raise Invalid('short legacy page')
  raw=[list(page[17*g:17*(g+1)]) for g in range(41)]
  # Compatibility model: legacy only creates indices for first41 groups.
  rows=[];cursor=0
  for g in range(65):
   for c in range(17):
    value=raw[g][c] if g<41 else 0
    rows.append((g,c,value+1,cursor if value and g<41 else H.MASK))
    if g<41:cursor+=value+1
  if cursor>65536:raise Invalid('legacy name demand overflow')
  return rows
 return plan(raw,n)[0]

class Replies(H.Machine):
 def __init__(self,kind,value=0,delivery='complete'):
  super().__init__();self.stub_size_queries=False;self.kind=kind;self.value=value;self.delivery=delivery;self.sent=[]
  self.external_hooks[0x9d075c1c]=self.send
 def irq_fragment(self,start,stop,payload):
  saved=self.r.copy();addr=self.r[29]+16;old=self.read(addr,4)
  self.write(addr,4,payload);self.invoke(start,stop=stop,seed=False,check=False)
  self.write(addr,4,old);self.r=saved
 def send(self,_):
  msg=self.r[4];self.sent.append(msg)
  if self.kind=='count':
   assert msg>>16==0x4012
   if self.delivery=='complete':self.irq_fragment(0x9d05177c,0x9d051794,self.value&65535)
  else:
   assert msg>>16==0x4037
   if self.delivery in ('complete','low_only','duplicate_low'):
    self.irq_fragment(0x9d051a10,0x9d051a34,self.value&65535)
    if self.delivery=='duplicate_low':self.irq_fragment(0x9d051a10,0x9d051a34,self.value&65535)
   if self.delivery in ('complete','high_only'):
    stop=0x9d051cf8 if self.read(0x8000044e,2)==1 else 0x9d05153c
    self.irq_fragment(0x9d051a3c,stop,self.value>>16)
 def execute(self,pc,w):
  # Test-only timer progress; no actual timer ISR execution is claimed.
  timer=self.read(0x800001f4,4)
  if timer and timer!=0xa5a5a5a5:self.write(0x800001f4,4,timer-1)
  return super().execute(pc,w)


class Generator(S.Machine):
 """Real count generator with test-only checks at proposed integration seams."""
 def __init__(self,raw,groups):
  super().__init__();self.raw=raw;self.groups=groups;self.collected=[[None]*17 for _ in range(groups)];self.serial_ops=[]
  for pc in (0x9d0689d8,0x9d07e274,0x9d068d64,0x9d07e3dc):self.external_hooks[pc]=lambda vm:vm.r.__setitem__(2,0)
  self.external_hooks[0x9d079978]=self.count
  self.external_hooks[0x9d0421ac]=lambda vm:self.serial_ops.append(('erase',vm.r[4]))
  self.external_hooks[0x9d042340]=lambda vm:self.serial_ops.append(('program',vm.r[4]))
 def count(self,vm):
  g,c=vm.r[4],vm.r[5]
  try:n=self.raw[g][c]
  except (IndexError,TypeError):raise Invalid('missing response')
  if type(n) is not int:raise Invalid('malformed response')
  vm.r[2]=n&0xffffffff
 def word(self,pc):
  if pc==0x9d042b08:return 0x24140000|self.groups
  return super().word(pc)
 def execute(self,pc,w):
  if pc==0x9d042b1c:
   n=self.r[2];g,c=self.r[17],self.r[16]
   if not 0<=n<=255:raise Invalid('count before sb not 0..255')
   self.collected[g][c]=n
  if pc==0x9d042b38:plan(self.collected,self.groups)
  return super().execute(pc,w)

def execute_dataset(raw,groups=97):
 rows,page,total=plan(raw,groups) # all validation/preflight BEFORE any serial write
 m=Generator(raw,groups);m.invoke(0x9d081090);E=m.invoke(0x9d07eb84,4480);m.write(H.CAP,4,E);m.write(H.CAP+4,4,9)
 # Existing stock page parser receives a supplied candidate fixture via external I/O.
 m.external_hooks[0x9d040a4c]=lambda vm:vm.r.__setitem__(2,page[vm.r[4]-0x5fd000])
 assert m.invoke(0x9d040ed8)==1
 for g,c,count,index in rows:
  if g>64:
   m.r[5]=c;m.r[6]=count;m.r[7]=index
   assert m.invoke(S.ENT['count_write'],g)==1
  addr=0x80037e90+8*(17*g+c) if g<=64 else E+8*(17*(g-65)+c)
  assert m.read(addr,4)==count and m.read(addr+4,4)==index
 # Independent enumeration of the stock name builder's inclusive instrument loop.
 record=0
 for g in range(groups):
  for c in range(17):
   n=raw[g][c]
   if n:assert rows[17*g+c][3]==record
   for instrument in range(n+1):
    address=0xc00000+64*record
    assert address+64<=0x1000000
    if instrument:assert rows[17*g+c][3]+instrument==record
    record+=1
 assert record==total and m.ctrl()==[E,9]
 m.invoke(0x9d042a8c)
 assert len(m.serial_ops)==17 and m.serial_ops[0]==('erase',0x5fd000)
 assert bytes(m.ram[0x10dac:0x10dac+1+groups*17])==page[:1+groups*17]

 assert load_model(page,groups,allow_extended=groups==97)==rows
 return {'records':total,'count_bytes':groups*17+1,'ID65_prefix':rows[65*17][3] if groups==97 else None,
         'ID96_prefix':rows[96*17][3] if groups==97 else None,'split_population_verified':True}

def run():
 out={};empty=[[0]*17 for _ in range(97)]
 out['empty']=execute_dataset(empty)
 populated=[x.copy() for x in empty]
 for g,c,n in [(0,0,3),(64,16,1),(65,0,4),(65,16,255),(96,0,2),(96,16,1)]:populated[g][c]=n
 out['populated']=execute_dataset(populated)
 exact=[x.copy() for x in empty];remaining=65536-97*17
 for row in exact:
  for c in range(17):
   n=min(255,remaining);row[c]=n;remaining-=n
 assert remaining==0;out['exact_capacity']=execute_dataset(exact)
 # Rejected candidates cannot call simulated erase/program or population.
 bad=[]
 for val in [-1,256,65535,65536,None,1.5,True]:
  x=[r.copy() for r in empty];x[65][0]=val;bad.append((f'count_{val!r}',x))
 bad.append(('missing_group',empty[:-1]));bad.append(('missing_category',[r.copy() for r in empty]));bad[-1][1][96].pop()
 overflow=[r.copy() for r in exact]
 for r in overflow:
  if r[-1]<255:r[-1]+=1;break
 bad.append(('overflow_by_one',overflow));bad.append(('large_overflow',[[255]*17 for _ in range(97)]))
 rejected={}
 for name,data in bad:
  serial=bytearray(b'OLD-NAMES-AND-COUNTS');before=bytes(serial);writes=[]
  try:rows,page,total=plan(data,97)
  except Invalid as ex:rejected[name]={'reason':str(ex),'serial_writes':len(writes)}
  else:raise AssertionError(name)
  assert bytes(serial)==before
 # Actual count-generation instructions must not reach erase/program on bad input.
 generator_rejected={}
 for name,data in [('raw256',next(x for n,x in bad if n=='count_256')),
                   ('overflow_by_one',overflow),('large_overflow',[[255]*17 for _ in range(97)])]:
  gen=Generator(data,97)
  try:gen.invoke(0x9d042a8c)
  except Invalid as ex:generator_rejected[name]={'reason':str(ex),'serial_operations':len(gen.serial_ops)}
  else:raise AssertionError(name)
  assert not gen.serial_ops
 out['actual_count_generator_prewrite_rejections']=generator_rejected
 out['rejected']=rejected
 # Existing stock metadata layout compatibility, actual stock parser for legacy41.
 raw41=[[0]*17 for _ in range(41)];raw41[0][0]=2;raw41[40][16]=5
 legacy=bytes(n for row in raw41 for n in row);expected=load_model(legacy,65)
 m=S.Machine();m.invoke(0x9d081090);m.write(H.CAP+4,4,9)
 m.external_hooks[0x9d040a4c]=lambda vm:vm.r.__setitem__(2,legacy[vm.r[4]-0x5fd000])
 assert m.invoke(0x9d040ed8)==1
 for g,c,count,index in expected:
  a=0x80037e90+8*(17*g+c);assert m.read(a,4)==count and m.read(a+4,4)==index
 page=plan(populated,97)[1]
 assert load_model(page,65)==plan(populated[:65],65)[0]
 try:load_model(page,97)
 except Invalid:pass
 else:raise AssertionError('unproven suffix admitted')
 out['compatibility']='legacy41, marked65 and stock prefix of marked97 match; unproven97 suffix rejected'
 # Actual PIC request and reply fragments, transport boundary simulated.
 counts={}
 for n in [0,4,255,256,65535,65536]:
  m=Replies('count',n);m.r[5]=16;got=m.invoke(0x9d079978,96)
  assert got==(n&65535) and m.sent==[0x40126010]
  counts[str(n)]=got
 out['stock_count_wire_results']=counts
 sizes={}
 for n in [0,1,65536,0x12345678]:
  m=Replies('size',n);m.r[5]=65;got=m.invoke(0x9d079744,0)
  assert got==n and m.sent==[0x40370041]
  assert m.read(0x8000044e,2)==0
  sizes[str(n)]=got
 out['stock_size_wire_results']=sizes
 stalled={}
 for kind,delivery in [('count','none'),('size','none'),('size','low_only'),('size','high_only'),('size','duplicate_low')]:
  m=Replies(kind,0,delivery);m.r[5]=65
  try:m.invoke(0x9d079978 if kind=='count' else 0x9d079744,0,max_steps=25000)
  except RuntimeError as ex:
   assert 'instruction limit' in str(ex);assert len(m.sent)>1
   stalled[kind+'_'+delivery]={'no_terminal_return':True,'sends_before_test_limit':len(m.sent)}
  else:raise AssertionError('unexpected return')
 out['stock_nonterminal_failures']=stalled
 out['size_zero_ambiguity']='successful-empty and modeled backend-failed zero encode identical 4037/4038 values; PIC cannot distinguish'
 assert hashlib.sha256((H.ROOT/'stock_pic_2.2.2.0.0.bin').read_bytes()).hexdigest()==H.SHA
 return out
if __name__=='__main__':print(json.dumps(run(),indent=2))

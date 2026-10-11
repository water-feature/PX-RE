"""Read-only firmware validation; proposed changes exist only in memory."""
from pathlib import Path
import runpy,struct,json,hashlib
D=Path(__file__).resolve().parent; B=D.parent; R=B.parent
p=runpy.run_path(str(B/'safety_review/tight_editor_probe.py'))
BASE=p['BASE']; OldCPU=p['CPU']; signed=p['signed']
image=(R/'b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin').read_bytes()
assert hashlib.sha256(image).hexdigest()==p['PIN']
words={int(a,16):int(w,16) for a,w,*_ in (line.split('\t') for line in (D/'expected_words.tsv').read_text().splitlines())}
assert {k:v for k,v in words.items() if p['START']<=k<p['END']}==p['program']()[0]
data={BASE+0x62074+i:v for i,v in enumerate(b'1/32 Step\0' + b'1/64 Step\0'+bytes([156,144,132,120,108,96,84,76,64,56,48,40,32,24,12,0,232,242])+b'\0\0')}
for o in (0x475f4,0x47900):data[BASE+o]=17;data[BASE+o+1]=0
class CPU(OldCPU):
 def read(self,a,n):
  return sum((self.mem.get(a+i,data.get(a+i, self.image[a+i-BASE] if BASE<=a+i<BASE+len(self.image) else 0)))<<(8*i) for i in range(n))
 def plain(self,w):
  op=w>>26;s=w>>21&31;t=w>>16&31;u=w&65535;k=u if u<32768 else u-65536
  if op in (32,36):
   v=self.read((self.reg[s]+k)&0xffffffff,1);self.reg[t]=(v-256 if op==32 and v>=128 else v)&0xffffffff
  elif op==40:self.write((self.reg[s]+k)&0xffffffff,1,self.reg[t])
  elif op==13:self.reg[t]=self.reg[s]|u
  elif op==0 and w&63==2:self.reg[w>>11&31]=self.reg[t]>>(w>>6&31)
  else:return super().plain(w)
  self.reg[0]=0
 def run(self,pc,stop,limit=60000,hook=None):
  for _ in range(limit):
   if pc==stop:return
   if hook and hook(self,pc):pc=self.reg[31];continue
   self.trace.append(pc);w=self.word(pc);op=w>>26;s=w>>21&31;t=w>>16&31;k=w&65535;k=k if k<32768 else k-65536;target=None;delay=True
   if op in (2,3):
    target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
    if op==3:self.reg[31]=pc+8
   elif op in (4,5,20,21):
    taken=(self.reg[s]==self.reg[t])==(op in (4,20));target=pc+4+4*k if taken else pc+8;delay=taken or op<20
   elif op==1 and t==0:target=pc+4+4*k if signed(self.reg[s])<0 else pc+8
   elif op==0 and w&63==8:target=self.reg[s]
   if target is None:self.plain(w);pc+=4
   else:
    if delay:self.trace.append(pc+4);self.plain(self.word(pc+4))
    pc=target
  raise AssertionError(('instruction limit',hex(pc)))
def fresh():
 c=CPU(image,words);c.reg=[0x51000000+i*0x111 for i in range(32)];c.reg[0]=0;c.reg[29]=0x80070000;c.reg[31]=0x9d077770;return c
# Combined display execution, including original append and original epilogue.
labels=[];display=0
for raw in range(18):
 ptr=BASE+0x61f8c+data[BASE+0x62088+raw];c=fresh();label=bytearray()
 while c.read(ptr+len(label),1):label.append(c.read(ptr+len(label),1))
 labels.append(label.decode())
 oldptr=struct.unpack_from('<I',image,0x62074+4*raw)[0] if raw<16 else None
 if oldptr:assert ptr==oldptr
 assert len(label)<=9
 for prefix in (b'',b'Sync: ',b'X'*31):
  c=fresh();sp=c.reg[29];ret=c.reg[31];saved=c.reg[16:22].copy();dest=0x80060000
  for i in range(6):c.write(sp+0x14+4*i,4,saved[i])
  c.write(sp+0x2c,4,ret)
  for i,v in enumerate(b'\xa5'+prefix+b'\0'+b'\xa5'*24):c.write(dest-1+i,1,v)
  c.reg[5]=raw;c.reg[6]=dest;c.writes=[];c.run(BASE+0x60278,ret)
  want=prefix+label+b'\0'
  assert bytes(c.read(dest+i,1) for i in range(len(want)))==want
  assert c.read(dest-1,1)==165 and c.read(dest+len(want),1)==165
  assert all(dest+len(prefix)<=a<dest+len(want) and n==1 for a,n in c.writes)
  assert c.reg[2]==saved[0] and c.reg[16:22]==saved and c.reg[29]==sp+48 and c.reg[31]==ret
  display+=1
assert labels[-2:]==['1/32 Step','1/64 Step']
# Editor, wrapper, helper liveness tests from existing probe, without its output writes.
source=(B/'safety_review/tight_editor_probe.py').read_text();source=source[:source.index("    listing='\\n'.join")]+"    return {'sync':sync,'nonSync':non,'BPM':bpm,'setter_context':chain}\n"
ns={'__file__':str(B/'safety_review/tight_editor_probe.py'),'__name__':'preflight_import'};exec(compile(source,'existing_scoped_tests','exec'),ns);counts=ns['main']()
# Execute all actual call instructions and their actual delay slots through wrapper/editor.
routes=[];routecases=0;order=[17,16]+list(range(16))
for row in (B/'ENCODER_CALLERS.tsv').read_text().splitlines()[1:]:
 addr,route,param,sync=row.split('\t')
 if sync!='true':continue
 pc=int(addr,16);assert struct.unpack_from('<I',image,pc-BASE)[0]==0x0f413e9b;routes.append(addr)
 for ident in ((int(param,16),) if param in ('1d','5e') else (0x1d,0x5e)):
  for layer in (0,1,2):
   for rank,raw in enumerate(order):
    for delta in (-1,1):
     c=fresh();sp=c.reg[29];saved=c.reg[16:24].copy();c.reg[4:8]=[1,layer,ident,delta&0xffffffff];c.reg[2]=17;c.write(sp+16,4,17)
     aa,bb=(raw,order[(rank+5)%18]);selected=aa if layer in (0,2) else bb
     for bank,value in enumerate((aa,bb)):c.write(0x8000046c+2*(ident+bank*0x6b7),2,value)
     c.run(pc,BASE+0x4dacc)
     assert c.reg[7]==order[max(0,min(17,order.index(selected)+delta))]
     assert c.reg[5:7]==[layer,ident] and c.reg[29]==sp and c.reg[31]==pc+8 and c.reg[16:24]==saved
     routecases+=1
assert len(routes)==13
# Absolute setter range validator, all unsigned 16-bit inputs, both Sync IDs.
absolute=0
for ident in (0x1d,0x5e):
 for value in range(65536):
  c=fresh();c.reg[4:7]=[0,ident,value];c.run(BASE+0x4d4fc,c.reg[31]);assert c.reg[2]==min(value,17),(ident,value,c.reg[2]);absolute+=1
result={'status':'PASS','independent_tool':'Ghidra 12.1.4 MIPS:LE:32:default; 51 exact assembled words and decoded flows/delay slots','display_cases':display,'labels':labels,'route_cases':routecases,'routes':routes,'absolute_cases':absolute,**counts}
(D/'preflight_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only symbolic instruction check; never assembles or patches firmware."""
from pathlib import Path
import json
O=Path(__file__).resolve().parent
rows=[];labels={}
for line in (O/'decoder_layout.txt').read_text().splitlines():
 if not line or line.startswith('#'):continue
 if line.endswith(':'):labels[line[:-1]]=len(rows);continue
 op,*args=line.replace(',',' ').split();rows.append((op,args))
def run(enc,q,timer,warm,direction,last):
 r=dict.fromkeys('zero a0 a1 a2 a3 v0 v1 t0 t1 ra'.split(),0);r['a0']=enc
 mem={0:q>>2,1:q&3,2:warm,4:direction,5:timer,6:last}
 def val(s):return r[s] if s in r else int(s,0)
 def one(row):
  op,a=row
  if op=='nop':return
  if op=='li':r[a[0]]=val(a[1]);return
  if op=='lui':r[a[0]]=val(a[1])<<16;return
  if op in ('lbu','sb'):
   off,base=a[1][:-1].split('(');off=int(off,0)
   if op=='lbu':r[a[0]]=mem[off]
   else:mem[off]=val(a[0])&255
   return
  d,x,y=a;v=val(x);w=val(y)
  r[d]={'sll':lambda:v<<w,'sllv':lambda:v<<w,'addu':lambda:v+w,'addiu':lambda:v+w,'subu':lambda:v-w,'andi':lambda:v&w,'or':lambda:v|w,'sltu':lambda:int(v<w),'sltiu':lambda:int(v<w),'movz':lambda:v if w==0 else r[d],'movn':lambda:v if w!=0 else r[d]}[op]()&0xffffffff
 pc=0
 while True:
  op,a=rows[pc]
  if op=='jr':one(rows[pc+1]);break
  if op in ('j','beq','bne'):
   target=labels[a[-1]];take=op=='j' or ((val(a[0])==val(a[1]))==(op=='beq'))
   one(rows[pc+1]);pc=target if take else pc+2
  else:one(rows[pc]);pc+=1
 return (r['v0'] if r['v0']<2**31 else r['v0']-2**32,mem[2],mem[4],mem[5],mem[6])
def ref(enc,q,t,w,d,last):
 if q not in (1,7,8,14,2,4,11,13) or last==q:return 0,w,d,255,last
 neg=int(q in (1,7,8,14));canonical=q==(1 if neg else 4)
 if d==neg:last=q
 if enc not in (4,5,18,19) or t<229:w=0;delta=int(canonical)
 elif d!=neg:delta=0
 elif w<3:w+=1;delta=int(canonical)
 elif not canonical:delta=1
 else:delta=1 if t<234 else 2 if t<238 else 3 if t<244 else 4 if t<250 else (7 if neg else 10)
 return -delta if neg else delta,w,neg,255,last
n=0
for enc in range(21):
 for q in range(16):
  for timer in (0,228,229,233,234,237,238,243,244,249,250,255):
   for warm in (0,1,2,3,255):
    for direction in (0,1):
     for last in (q,(q+1)%16):
      a=run(enc,q,timer,warm,direction,last);b=ref(enc,q,timer,warm,direction,last)
      assert a==b,(enc,q,timer,warm,direction,last,a,b)
      n+=1
report={'status':'PASS_SYMBOLIC_ONLY','cases':n,'decoder_words':len(rows),'decoder_bytes':4*len(rows),'decoder_end':hex(0x9d07a298+4*len(rows)),'limits':'Valid sampled bytes0..3 and direction0/1. No emitted-code, IRQ, complete HSM or hardware execution. No firmware assembled or modified.'}
(O/'layout_results.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

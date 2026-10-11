# SPDX-License-Identifier: GPL-2.0-or-later
"""B4 instruction-design model. Never reads or writes a firmware image.

Encodes proposed guard words in memory, executes them with MIPS delay slots,
and compares the result with an independent boundary oracle. The lazy bound
initializer is a stub; this is not full allocator or hardware validation.
"""
import random, json
BASE=0x80053ae0; CAP=0x80057ad8; MASK=0xffffffff
REG='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
N={s:i for i,s in enumerate(REG)}
src='''
addiu sp sp -32
sw ra 28 sp
sw s0 24 sp
lui s0 0x8005
lw v0 0x3a64 s0
bne v0 zero validate
nop
sw a0 16 sp
jal 0x9d07f9f0
nop
lw v0 0x3a64 s0
lw a0 16 sp
beq v0 zero enomem
nop
validate:
lw t0 0x3a6c s0
lw t1 0x3a68 s0
lui t2 0xe000
and t3 v0 t2
lui t4 0x8000
beq t3 t4 alias_ok
nop
lui t4 0xa000
bne t3 t4 einval
nop
alias_ok:
xor t4 t0 v0
and t4 t4 t2
bne t4 zero einval
nop
xor t4 t1 v0
and t4 t4 t2
bne t4 zero einval
nop
lui t2 0x1fff
ori t2 t2 0xffff
and t0 t0 t2
and t1 t1 t2
and t3 v0 t2
lui t4 0x0005
ori t4 t4 0x3ae0
sltu t5 t0 t4
bne t5 zero einval
nop
lui t6 0x0005
ori t6 t6 0x7ad8
sltu t5 t6 t1
bne t5 zero einval
nop
sltu t5 t1 t0
bne t5 zero einval
nop
sltu t5 t3 t0
bne t5 zero einval
nop
sltu t5 t1 t3
bne t5 zero einval
nop
addu v1 v0 a0
xor t4 v1 v0
lui t6 0xe000
and t4 t4 t6
bne t4 zero range_error
nop
and t4 v1 t2
blez a0 shrink
nop
sltu t5 v1 v0
bne t5 zero enomem
nop
sltu t5 t1 t4
bne t5 zero enomem
nop
j commit
nop
shrink:
sltu t5 v0 v1
bne t5 zero einval
nop
sltu t5 t4 t0
bne t5 zero einval
nop
commit:
sw v1 0x3a64 s0
j done
nop
range_error:
blez a0 einval
nop
enomem:
addiu v1 zero 12
j error
nop
einval:
addiu v1 zero 22
error:
sw v1 0x3ad8 s0
addiu v0 zero -1
done:
lw ra 28 sp
lw s0 24 sp
jr ra
addiu sp sp 32
'''
def parse(src,start):
 ops=[];labels={}
 for line in src.strip().splitlines():
  if line.endswith(':'):labels[line[:-1]]=start+4*len(ops)
  else:ops.append(line.split())
 return ops,labels
START=0x9d001280;ops,labels=parse(src,START)
def val(x):return labels[x] if x in labels else int(x,0)
def enc(t,pc):
 op,*a=t
 if op=='nop':return 0
 if op in ['addu','and','xor','sltu']:
  d,s,r=map(N.get,a);return s<<21|r<<16|d<<11|{'addu':33,'and':36,'xor':38,'sltu':43}[op]
 if op=='jr':return N[a[0]]<<21|8
 if op=='lui':return 15<<26|N[a[0]]<<16|val(a[1])
 if op in ['addiu','ori']:
  return {'addiu':9,'ori':13}[op]<<26|N[a[1]]<<21|N[a[0]]<<16|(val(a[2])&65535)
 if op in ['lw','sw']:return {'lw':35,'sw':43}[op]<<26|N[a[2]]<<21|N[a[0]]<<16|(val(a[1])&65535)
 if op in ['beq','bne']:return {'beq':4,'bne':5}[op]<<26|N[a[0]]<<21|N[a[1]]<<16|(((val(a[2])-pc-4)//4)&65535)
 if op=='blez':return 6<<26|N[a[0]]<<21|(((val(a[1])-pc-4)//4)&65535)
 if op in ['j','jal']:return {'j':2,'jal':3}[op]<<26|((val(a[0])>>2)&0x3ffffff)
 raise ValueError(t)
words=[enc(t,START+4*i) for i,t in enumerate(ops)]
def phys(a):return a&0x1fffffff if a>>29 in [4,5] else a
def run(br,lo,up,inc,lazy=None):
 R=[0]*32;R[4]=inc&MASK;R[16]=0x11223344;R[29]=0x8007ffc0;R[31]=0x9d0814b4
 M={phys(0x80053a64):br,phys(0x80053a6c):lo,phys(0x80053a68):up,phys(0x80053ad8):77,phys(CAP):0xabcdef01,phys(CAP+4):0xabcdef02}
 stores=[];pc=START;steps=0
 def step(w,p):
  o=w>>26;s=w>>21&31;t=w>>16&31;d=w>>11&31;f=w&63;im=w&65535;si=im if im<32768 else im-65536;dest=None
  if w==0:pass
  elif o==0:
   if f==8:dest=R[s]
   elif f in [33,36,38,43]:R[d]={33:lambda:R[s]+R[t],36:lambda:R[s]&R[t],38:lambda:R[s]^R[t],43:lambda:int(R[s]<R[t])}[f]()&MASK
   else:raise ValueError(hex(w))
  elif o==15:R[t]=im<<16
  elif o==9:R[t]=(R[s]+si)&MASK
  elif o==13:R[t]=R[s]|im
  elif o in [35,43]:
   a=phys((R[s]+si)&MASK)
   if o==35:R[t]=M.get(a,0)
   else:M[a]=R[t];stores.append(a)
  elif o in [4,5,6]:
   take=R[s]==R[t] if o==4 else R[s]!=R[t] if o==5 else R[s]==0 or R[s]>=0x80000000
   dest=p+4+si*4 if take else p+8
  elif o in [2,3]:
   dest=((p+4)&0xf0000000)|((w&0x3ffffff)<<2)
   if o==3:R[31]=p+8
  else:raise ValueError(hex(w))
  R[0]=0;return dest
 while START<=pc<START+4*len(words):
  steps+=1
  if steps>1000:raise RuntimeError('loop')
  i=(pc-START)//4;w=words[i];dest=step(w,pc)
  if dest is None:pc+=4;continue
  assert step(words[i+1],pc+4) is None
  if dest==0x9d07f9f0:
   if lazy is not None:M[phys(0x80053a64)],M[phys(0x80053a6c)],M[phys(0x80053a68)]=lazy
   # Deliberately clobber caller-saved inputs: saved increment must survive.
   R[4]=0xdeadbeef;pc=R[31]
  else:pc=dest
 assert R[16]==0x11223344 and R[29]==0x8007ffc0 and R[31]==0x9d0814b4
 assert M[phys(CAP)]==0xabcdef01 and M[phys(CAP+4)]==0xabcdef02
 return R[2],M[phys(0x80053a64)],M[phys(0x80053ad8)],stores
def oracle(br,lo,up,inc,lazy=None):
 if br==0:
  if lazy is not None:br,lo,up=lazy
  if br==0:return MASK,br,12
 alias=br>>29
 if alias not in [4,5] or lo>>29!=alias or up>>29!=alias:return MASK,br,22
 b,l,u=br&0x1fffffff,lo&0x1fffffff,up&0x1fffffff
 if not BASE&0x1fffffff<=l<=b<=u<=CAP&0x1fffffff:return MASK,br,22
 signed=inc if inc<0x80000000 else inc-0x100000000
 nxt=b+signed
 if signed>0 and nxt>u:return MASK,br,12
 if signed<=0 and nxt<l:return MASK,br,22
 return br,(br+signed)&MASK,77
cases=[('zero',BASE,BASE,CAP,0,None),('grow-to-end',CAP-8,BASE,CAP,8,None),('cross-end',CAP-8,BASE,CAP,9,None),('at-end',CAP,BASE,CAP,1,None),('shrink-to-base',BASE+8,BASE,CAP,-8,None),('below-base',BASE,BASE,CAP,-1,None),('huge-growth',BASE,BASE,CAP,0x7fffffff,None),('huge-shrink',BASE,BASE,CAP,-0x80000000,None),('old-upper',BASE,BASE,CAP+8,1,None),('break-in-control',CAP+4,BASE,CAP,0,None),('mixed-alias',BASE,BASE|0x20000000,CAP,1,None),('uncached',BASE|0x20000000,BASE|0x20000000,CAP|0x20000000,8,None),('subheap',BASE+128,BASE+64,CAP-64,8,None),('upper-below-break',BASE+64,BASE,BASE+32,0,None),('lower-below-provider',BASE,BASE-8,CAP,0,None),('lazy-success',0,0,0,8,(BASE,BASE,CAP)),('lazy-failure',0,0,0,8,None),('extension-preferred-growth',BASE,BASE,CAP,4608,None),('preferred-near-end-fails',CAP-4496,BASE,CAP,4608,None),('minimum-near-end-fits',CAP-4496,BASE,CAP,4496,None),('minimum-one-byte-short',CAP-4495,BASE,CAP,4496,None)]
rows=[]
for name,br,lo,up,inc,lazy in cases:
 actual=run(br,lo,up,inc&MASK,lazy);expected=oracle(br,lo,up,inc&MASK,lazy)
 assert actual[:3]==expected,(name,actual,expected)
 rows.append((name,hex(actual[0]),hex(actual[1]),actual[2]))
rng=random.Random(4480)
for _ in range(20000):
 alias=rng.choice([0x80000000,0xa0000000]);lo=alias|(0x53ae0+rng.randrange(0,64));up=alias|(0x57ad8-rng.randrange(0,64));br=rng.randrange(lo,up+1)
 inc=rng.choice([rng.randrange(-20000,20001),rng.randrange(0,2**32)])&MASK
 assert run(br,lo,up,inc)[:3]==oracle(br,lo,up,inc)
wrapper='''addu t7 ra zero
jal 0x9d081090
nop
lui t0 0x8005
sw zero 0x7ad8 t0
sw zero 0x7adc t0
addu ra t7 zero
jr ra
nop'''
wops,_=parse(wrapper,0x9d001240)
print('guard words',len(words),'end',hex(START+4*len(words)))
print('named cases',json.dumps(rows))
print('random valid-state cases 20000 PASS; saved registers/frame and reservation canaries checked')
for start,seq in [(0x9d001240,wops),(START,ops)]:
 for i,t in enumerate(seq):
  pc=start+4*i;print(f'{pc:08X} {enc(t,pc):08X} '+ ' '.join(t))

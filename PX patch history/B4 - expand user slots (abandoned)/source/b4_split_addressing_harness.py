"""Relocatable instruction design tested in the existing read-only harness.
Synthetic helper PCs are test labels, NOT cleared firmware placement.
"""
import sys,json
from pathlib import Path
if '--entry-hook' not in sys.argv:sys.argv.append('--entry-hook')
import b4_control_integration_harness as H
from b4_split_raw_inspect import word
R=H.RI
SYN=0x9f000000
CODE={};LIST=[];ENT={}
def assemble(name,lines):
 base=SYN+len(ENT)*0x1000;ENT[name]=base;labels={};pc=base
 for line in lines:
  if line.endswith(':'):labels[line[:-1]]=pc
  else:pc+=4
 pc=base
 for line in lines:
  if line.endswith(':'):continue
  op,*a=line.split();val=lambda x:labels[x] if x in labels else int(x,0)
  if op=='nop':w=0
  elif op in ('addu','subu','and','or'):w=R[a[1]]<<21|R[a[2]]<<16|R[a[0]]<<11|{'addu':33,'subu':35,'and':36,'or':37}[op]
  elif op in ('sll','srl'):w=R[a[1]]<<16|R[a[0]]<<11|val(a[2])<<6|{'sll':0,'srl':2}[op]
  elif op=='lui':w=15<<26|R[a[0]]<<16|val(a[1])
  elif op in ('addiu','sltiu','andi','ori','xori'):w={'addiu':9,'sltiu':11,'andi':12,'ori':13,'xori':14}[op]<<26|R[a[1]]<<21|R[a[0]]<<16|(val(a[2])&65535)
  elif op in ('lw','sw'):w={'lw':35,'sw':43}[op]<<26|R[a[2]]<<21|R[a[0]]<<16|(val(a[1])&65535)
  elif op in ('beq','bne'):
   delta=(val(a[2])-pc-4)//4;assert -32768<=delta<=32767
   w={'beq':4,'bne':5}[op]<<26|R[a[0]]<<21|R[a[1]]<<16|(delta&65535)
   assert pc+4+H.signed((w&65535)| (0xffff0000 if w&32768 else 0))*4==val(a[2])
  elif op in ('j','jal'):
   target=val(a[0]);assert (target&0xf0000000)==((pc+4)&0xf0000000)
   w={'j':2,'jal':3}[op]<<26|(target>>2&0x3ffffff)
   assert ((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)==target
  elif op=='jr':w=R[a[0]]<<21|8
  else:raise ValueError(line)
  assert pc not in CODE;CODE[pc]=w;LIST.append(f'{pc:08X} {w:08X} {line}');pc+=4
 return base

def resolver(kind='row',private=False,g='a0',c='a1',p='v0',t='v1'):
 # Only p/t clobbered; caller inputs and all t-registers preserved.
 z=[]
 if kind=='row':z += [f'sltiu {p} {c} 17',f'beq {p} zero bad','nop']
 z += [f'sltiu {p} {g} 97',f'beq {p} zero bad','nop',f'lui {p} 0x8005',f'lw {t} 0x7adc {p}',f'andi {t} {t} 8',f'{"beq" if private else "bne"} {t} zero bad','nop',f'sltiu {t} {g} 65',f'bne {t} zero stock','nop']
 if not private:z += [f'lw {t} 0x7adc {p}',f'andi {t} {t} 6',f'xori {t} {t} 6',f'bne {t} zero bad','nop']
 z += [f'lw {p} 0x7ad8 {p}',f'beq {p} zero bad','nop']
 if kind=='row':z += [f'sll {t} {g} 4',f'addu {t} {t} {g}',f'addiu {t} {t} -1105',f'addu {t} {t} {c}',f'sll {t} {t} 3']
 else:z += [f'addiu {t} {g} -65',f'sll {t} {t} 2',f'addiu {t} {t} 0x1100']
 z += [f'addu {p} {p} {t}','j finish','nop','stock:']
 z += [f'lui {p} {"0x8003" if kind=="row" else "0x8004"}',f'addiu {p} {p} {"0x7e90" if kind=="row" else "-0x5ee8"}']
 if kind=='row':z += [f'sll {t} {g} 4',f'addu {t} {t} {g}',f'addu {t} {t} {c}',f'sll {t} {t} 3']
 else:z += [f'sll {t} {g} 2']
 return z+[f'addu {p} {p} {t}','finish:']
def read_helper(name,kind,offset,fail):
 assemble(name,resolver(kind)+[f'lw v0 {offset} v0','addiu v1 zero 1','jr ra','nop','bad:',f'addiu v0 zero {fail}','addu v1 zero zero','jr ra','nop'])
read_helper('count','row',0,1);read_helper('index','row',4,-1);read_helper('size','size',0,0)
for name,kind in [('row_public','row'),('row_private','row'),('size_private','size')]:
 assemble(name,resolver(kind,private='private' in name)+['addiu v1 zero 1','jr ra','nop','bad:','addu v0 zero zero','addu v1 zero zero','jr ra','nop'])
for name,kind,private in [('count_write','row',True),('size_write','size',True),('size_write_public','size',False)]:
 stores=['sw a2 0 v0','sw a3 4 v0'] if kind=='row' else ['sw a1 0 v0']
 assemble(name,resolver(kind,private)+stores+['addiu v0 zero 1','addiu v1 zero 1','jr ra','nop','bad:','addu v0 zero zero','addu v1 zero zero','jr ra','nop'])
assemble('availability',resolver(c='zero')+['addu a2 v0 zero','addu v0 zero zero','addiu a1 zero 17','sum:','lw a0 0 a2','addiu a0 a0 -1','addiu a2 a2 8','addiu a1 a1 -1','bne a1 zero sum','addu v0 v0 a0','addiu v1 zero 1','jr ra','nop','bad:','addu v0 zero zero','addu v1 zero zero','jr ra','nop'])
# Selected-name direct reader: rejoin stock sentinel branch before serial I/O.
assemble('selected_index',resolver(g='s1',c='s4')+['lw s3 4 v0','j 0x9d041194','nop','bad:','addiu s3 zero -1','j 0x9d041194','nop'])
assemble('shared_index',resolver()+['lw s1 4 v0','j 0x9d041ec0','nop','bad:','addiu s1 zero -1','j 0x9d041ec0','nop'])
# Import window starts BEFORE original s4 shift; preserve value v0.
assemble('import_size',resolver('size',False,g='s4',p='v1',t='a1')+['sw v0 0 v1','lui a0 0x402c','addiu a0 a0 1','j 0x9d01b8f8','nop','bad:','j 0x9d01b6b0','nop'])
# Renderer returns to formatter setup with ordinary a0=size; no new call/frame.
assemble('render_size',resolver('size',g='s3',p='a0',t='v1')+['lw a0 0 a0','j 0x9d034290','nop','bad:','addu a0 zero zero','j 0x9d034290','nop'])
# Whole size initializer, unchanged frame/saved registers. Query status is NOT inferred.
assemble('size_initialize',[
 'addiu sp sp -32','sw ra 28 sp','sw s2 24 sp','sw s1 20 sp','sw s0 16 sp',
 'lui v0 0x8005','lw v1 0x7adc v0','andi v1 v1 8','beq v1 zero init_bad','nop',
 'addiu s2 zero 65','lw v0 0x7ad8 v0','beq v0 zero init_stock','nop','addiu s2 zero 97','init_stock:',
 'lui v0 0x8004','sw zero -0x5ee8 v0','addiu s0 zero 1','init_loop:','addu a1 s0 zero',
 'jal 0x9d079744','addu a0 zero zero','addu a1 v0 zero','addu a0 s0 zero',
 f'jal {ENT["size_write"]:#x}','nop','beq v0 zero init_bad','nop','addiu s0 s0 1',
 'bne s0 s2 init_loop','nop','addiu v0 zero 1','j init_done','nop',
 'init_bad:','addu v0 zero zero','init_done:','lw ra 28 sp','lw s2 24 sp','lw s1 20 sp','lw s0 16 sp','jr ra','addiu sp sp 32'])
# Count-loader tail: preserve original stock loading and initialize extra rows.
assemble('count_defaults_tail',[
 'lui t0 0x8005','lw t1 0x7adc t0','andi t1 t1 8','beq t1 zero tail_done','nop',
 'lw t0 0x7ad8 t0','beq t0 zero tail_done','nop','addiu t1 t0 0x1100',
 'addiu t2 zero 1','addiu t3 zero -1','tail_loop:','sw t2 0 t0','sw t3 4 t0',
 'addiu t0 t0 8','bne t0 t1 tail_loop','nop','tail_done:',
 'addiu v0 zero 1','lw ra 28 sp','lw s2 24 sp','j 0x9d04101c','nop'])
assemble('count_entry_gate',[
 'lui v0 0x8005','lw v1 0x7adc v0','andi v1 v1 8','beq v1 zero entry_bad','nop',
 'addiu sp sp -32','sw ra 28 sp','j 0x9d040ee0','nop','entry_bad:',
 'addu v0 zero zero','jr ra','nop'])
# Stock replacement hooks: all original words retained in manifest for review.
HOOKS={}
for a,name in [(0x9d0792e0,'count'),(0x9d079300,'availability'),(0x9d041178,'selected_index'),(0x9d041ea0,'shared_index'),(0x9d01b8dc,'import_size'),(0x9d034280,'render_size'),(0x9d079a08,'size_initialize'),(0x9d041014,'count_defaults_tail'),(0x9d040ed8,'count_entry_gate')]:
 # Synthetic tests use a full-width jump handler: physical helper locations remain unresolved.
 HOOKS[a]=name
class Machine(H.Machine):
 def word(self,pc):
  if pc in CODE:return CODE[pc]
  if pc in HOOKS:return 2<<26|(ENT[HOOKS[pc]]>>2&0x3ffffff)
  if pc-4 in HOOKS:return 0
  return super().word(pc)
 def execute(self,pc,w):
  count=len(self.control_writes)
  result=super().execute(pc,w)
  if pc in CODE:assert len(self.control_writes)==count,'split helper wrote control reservation'
  return result
def oracle(g,c,flags,p,private=False,size=False):
 if not 0<=g<=96 or (not size and not 0<=c<=16):return 0
 if bool(flags&8)!=private:return 0
 if g<=64:return 0x8003a118+4*g if size else 0x80037e90+8*(17*g+c)
 if not p or (not private and flags&6!=6):return 0
 return p+0x1100+4*(g-65) if size else p+8*(17*(g-65)+c)
def run():
 m=Machine();m.invoke(0x9d081090);E=m.invoke(0x9d07eb84,4480);assert E
 for g in range(97):
  for c in range(17):
   a=0x80037e90+8*(17*g+c) if g<65 else E+8*(17*(g-65)+c)
   m.write(a,4,2+c);m.write(a+4,4,g*100+c)
  a=0x8003a118+4*g if g<65 else E+0x1100+4*(g-65);m.write(a,4,g*123)
 cases=0
 for flags in [0,1,7,9,15]:
  for root in [0,E]:
   m.write(H.CAP,4,root);m.write(H.CAP+4,4,flags)
   for g in [64,65,96,97]:
    for c in [0,16,17]:
     for private in [False,True]:
      m.r[5]=c;expected=oracle(g,c,flags,root,private)
      got=m.invoke(ENT['row_private' if private else 'row_public'],g)
      assert got==expected and m.r[3]==int(bool(expected))
     a=oracle(g,c,flags,root)
     m.r[5]=c;assert m.invoke(0x9d0792e0,g)==(2+c if a else 1);assert m.r[3]==int(bool(a))
     m.r[5]=c;assert m.invoke(ENT['index'],g)==(g*100+c if a else H.MASK)
     # Reject writes without mutating ANY RAM except normal saved-register stack (none here).
     m.r[5]=c;m.r[6]=99;m.r[7]=H.MASK;before=bytes(m.ram);dest=oracle(g,c,flags,root,True)
     assert m.invoke(ENT['count_write'],g)==int(bool(dest))
     if dest:
      assert m.read(dest,4)==99 and m.read(dest+4,4)==H.MASK
      m.write(dest,4,2+c);m.write(dest+4,4,g*100+c)
     assert bytes(m.ram)==before
     # Actual selected/shared hook windows, stopping before existing sentinel branch.
     m.r[17]=g;m.r[20]=c
     m.invoke(0x9d041178,stop=0x9d041194,check=False,seed=False)
     assert m.r[19]==(g*100+c if a else H.MASK)
     m.r[5]=c;m.invoke(0x9d041ea0,g,stop=0x9d041ec0,check=False,seed=False)
     assert m.r[17]==(g*100+c if a else H.MASK)
     cases+=1
    a=oracle(g,0,flags,root,size=True)
    assert m.invoke(ENT['size'],g)==(g*123 if a else 0)
    assert m.r[3]==int(bool(a))
    m.r[5]=12345;before=bytes(m.ram);dest=oracle(g,0,flags,root,True,True)
    assert m.invoke(ENT['size_write'],g)==int(bool(dest))
    if dest:assert m.read(dest,4)==12345;m.write(dest,4,g*123)
    assert bytes(m.ram)==before
    # Import/direct render instruction windows retain original caller group registers.
    dest=oracle(g,0,flags,root,size=True);before=bytes(m.ram)
    m.r[20]=g;m.r[2]=12345
    m.invoke(0x9d01b8dc,stop=0x9d01b8f8 if dest else 0x9d01b6b0,check=False,seed=False)
    if dest:
     assert m.read(dest,4)==12345 and m.r[4]==0x402c0001
     m.write(dest,4,g*123)
    assert bytes(m.ram)==before
    m.r[19]=g;m.invoke(0x9d034280,stop=0x9d034290,check=False,seed=False)
    assert m.r[4]==(g*123 if dest else 0)
    assert m.invoke(0x9d079300,g)==(sum(1+c for c in range(17)) if oracle(g,0,flags,root) else 0)
 for flags in [1,7,9]:
  m.write(H.CAP,4,E);m.write(H.CAP+4,4,flags);m.r[5]=16
  for i in range(8,16):m.r[i]=0x45670000+i
  temps=m.r[8:16].copy()
  m.invoke(0x9d0792e0,65)
  assert m.r[4]==65 and m.r[5]==16 and m.r[8:16]==temps
 # Neither signed-invalid indices nor an index sentinel is treated as an address.
 m.write(H.CAP+4,4,7);m.r[5]=0
 assert m.invoke(0x9d0792e0,H.MASK)==1
 m.r[5]=H.MASK;assert m.invoke(0x9d0792e0,65)==1
 # Real instrument limiter: unavailable count must clamp to instrument zero, not 0xffff.
 for flags in [1,7,9]:
  m.write(H.CAP,4,E);m.write(H.CAP+4,4,flags)
  m.write(0x800004b0,2,65);m.write(0x800004b4,2,0)
  m.r[5]=0x23;m.r[6]=999
  expected=1 if flags==7 else 0
  assert m.invoke(0x9d04d4fc,0)==expected
 m.write(H.CAP,4,E);m.write(H.CAP+4,4,9)
 m.invoke(0x9d079a08);assert m.r[2]==1 and m.size_queries==96
 for g in [0,64,65,96]:
  dest=oracle(g,0,9,E,True,True);assert m.read(dest,4)==g*4096
 extended_queries=m.size_queries
 m.write(H.CAP,4,0);m.write(H.CAP+4,4,9);start=m.size_queries
 assert m.invoke(0x9d079a08)==1 and m.size_queries-start==64
 m.write(H.CAP,4,E)
 m.write(H.CAP+4,4,7);n=m.size_queries
 assert m.invoke(0x9d079a08)==0 and m.size_queries==n
 m.write(H.CAP+4,4,1);before=bytes(m.ram);reads=m.serial_reads
 assert m.invoke(0x9d040ed8)==0 and m.serial_reads==reads and bytes(m.ram)==before
 # Stock count reload instructions retained; only external serial fixture stubbed.
 m.write(H.CAP+4,4,9);ext=bytes(m.ram[m.phys(E):m.phys(E)+4480])
 assert m.invoke(0x9d040ed8)==1;assert m.read(0x80037e90+64*136,4)==1
 assert bytes(m.ram[m.phys(E)+0x1100:m.phys(E)+4480])==ext[0x1100:]
 for g in [65,96]:
  for c in [0,16]:
   d=oracle(g,c,9,E,True);assert m.read(d,4)==1 and m.read(d+4,4)==H.MASK
 for g in range(65,97):
  for c in range(17):
   m.r[5]=c;m.r[6]=2+c;m.r[7]=g*100+c
   assert m.invoke(ENT['count_write'],g)==1
   d=oracle(g,c,9,E,True);assert m.read(d,4)==2+c and m.read(d+4,4)==g*100+c
 m.write(H.CAP+4,4,7)
 d=oracle(65,0,7,E);m.write(d+4,4,H.MASK);m.r[5]=0
 assert m.invoke(ENT['index'],65)==H.MASK and m.r[3]==1
 m.write(H.CAP+4,4,9)
 assert m.ctrl()==[E,9]
 return {'boundary_rows':cases,'states':[0,1,7,9,15],'groups':[64,65,96,97],'categories':[0,16,17],
 'extension':hex(E),'size_initialization_queries':extended_queries,'stock_size_queries':64,'stock_count_reload_preserved':True,
 'instruction_words':len(CODE),'placement':'synthetic only; no physical helper placement assigned',
 'limits':'direct name windows stop before serial I/O; extension population exercised via private writers, not a new serial metadata parser'}
if __name__=='__main__':
 result=run()
 import hashlib
 result['stock_sha256']=hashlib.sha256((H.ROOT/'stock_pic_2.2.2.0.0.bin').read_bytes()).hexdigest()
 assert result['stock_sha256']==H.SHA
 Path('b4_split_addressing_instructions.txt').write_text('\n'.join(LIST)+'\n')
 Path('b4_split_addressing_hooks.json').write_text(json.dumps({hex(a):{'helper':n,'synthetic_entry':hex(ENT[n]),'stock_words':[f'{word(a):08X}',f'{word(a+4):08X}'],'test_hook_words':[f'{(2<<26|(ENT[n]>>2&0x3ffffff)):08X}','00000000']} for a,n in HOOKS.items()},indent=2)+'\n')
 print(json.dumps(result,indent=2))

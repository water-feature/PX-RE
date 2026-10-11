# SPDX-License-Identifier: GPL-2.0-or-later
"""Compact transition-only routing entirely within established owned ranges.
Scratch fragments and interpreter overlays only; no firmware image writes.
"""
from pathlib import Path
import struct, json, subprocess, os
from setter_harness import CPU, PARAM

ROOT=Path(__file__).resolve().parent
scope={}
src=(ROOT.parent/'b11_pic_tools/measure_corrected.py').read_text()
exec(compile(src.split('out=Path(__file__).parent')[0],'<encoder>','exec'),scope)
R=scope['R']; old_encode=scope['encode']
sections=[
 (0x9d02a74c,0x9d02a794,'''entry:
lhu v1,0x20,a0
lhu v0,6,a0
bne v0,zero,inst2
addiu v0,zero,1
sh v0,0x74,a0
beql v1,v0,0x9d02ebe8
lhu a0,0x44,a0
addiu a2,zero,0x24
normalize:
lw v0,8,s1
slt a3,zero,v0
sll a3,a3,1
addiu a3,a3,-1
lhu a0,0x44,s0
jal 0x9d04d300
addu a1,a2,zero
addu s4,v0,zero
beq zero,zero,snapshot
addu t0,v0,a3
'''),
 (0x9d02d428,0x9d02d464,'''inst2:
sh v0,0x76,a0
beql v1,v0,0x9d02eae8
lhu a0,0x44,a0
beq zero,zero,normalize
addiu a2,zero,0x65
helper_tail:
sltiu t1,a2,1
movz t1,zero,t0
j 0x9d04d4fc
addu a2,a2,t1
snapshot:
lhu s5,0xd6e,a1
beq zero,zero,invoke
movn s5,s4,a0
selector:
lhu v0,6,s0
beq v0,zero,0x9d02a794
nop
'''),
 (0x9d02dd08,0x9d02dd2c,'''adjust:
lw t0,0x2c,sp
lui t1,0x9d02
ori t1,t1,0xdf10
bne t0,t1,0x9d04d4fc
sll t0,a0,2
addu t0,t0,sp
lw t0,0x24,t0
beq zero,zero,helper_tail
xor t0,t0,s3
'''),
 (0x9d02def8,0x9d02df1c,'''invoke:
sltiu v0,t0,17
beq v0,zero,selector
addu a3,t0,zero
lhu a1,0x44,s0
jal 0x9d04dacc
addu a0,zero,zero
beq zero,zero,selector
nop
nop
''')]

labels={};instructions=[]
for start,end,source in sections:
 p=start
 for line in source.strip().splitlines():
  if line.endswith(':'):labels[line[:-1]]=p
  else:instructions.append((p,line));p+=4
 assert p==end
scope['labels']=labels
def encode(p,line):
 if line.startswith('j '):return (2<<26)|((int(line[2:],0)>>2)&0x3ffffff)
 if line.startswith('ori '):
  t,s,n=line[4:].split(',');return (13<<26)|(R[s]<<21)|(R[t]<<16)|int(n,0)
 if line.startswith(('movz ','xor ')):
  op,args=line.split(' ');d,s,t=map(R.__getitem__,args.split(','));return (s<<21)|(t<<16)|(d<<11)|{'movz':10,'xor':38}[op]
 return old_encode(p,line)
image={p:encode(p,line) for p,line in instructions}
helper_entry=labels['adjust']
for site in (0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624):image[site]=(3<<26)|((helper_entry>>2)&0x3ffffff)

out=ROOT/'compact';out.mkdir(exist_ok=True)
(out/'listing.txt').write_text('\n'.join(f'{p:08x} {encode(p,line):08x} {line}' for p,line in instructions)+'\n')
for start,end,_ in sections:(out/f'fragment_{start:08x}.bin').write_bytes(b''.join(struct.pack('<I',image[p]) for p in range(start,end,4)))
# Independently assemble the complete layout, including absolute guard branches.
external={0x9d02ebe8:'group1',0x9d02eae8:'group2',0x9d02a794:'refresh1',0x9d02d464:'refresh2',0x9d04d4fc:'clamp'}
asm=['.set noreorder','.set noat','.text']
for start,end,source in sorted(sections+[(addr,addr+4,name+':\nnop\n') for addr,name in external.items()]):
 asm.append(f'.org {start-0x9d000000}')
 for line in source.strip().splitlines():
  if line.endswith(':') or line=='nop':asm.append(line);continue
  op,args=line.split(' ',1);a=args.split(',')
  if op in ('beq','bne','beql'):
   dest=external.get(int(a[2],0),a[2]) if a[2].startswith('0x') else a[2]
   asm.append(f'{op} ${a[0]},${a[1]},{dest}')
  elif op in ('lhu','lw','sh','sw'):asm.append(f'{op} ${a[0]},{a[1]}(${a[2]})')
  elif op in ('j','jal'):asm.append(line)
  else:asm.append(op+' '+','.join('$'+v if v in R else v for v in a))
assembly='\n'.join(asm)+'\n'
(out/'candidate.s').write_text(assembly)
(out/'candidate.rs').write_text('#![feature(no_core, rustc_attrs, asm_experimental_arch)]\n#![no_core]\n#![no_main]\n#[rustc_builtin_macro]\nmacro_rules! global_asm { () => {} }\nglobal_asm!('+json.dumps(assembly)+');\n')
result=subprocess.run(['rustc','--target','mipsel-unknown-none','--emit=obj','-o',str(out/'candidate.o'),str(out/'candidate.rs')],env=dict(os.environ,RUSTC_BOOTSTRAP='1'),capture_output=True)
assert result.returncode==0,result.stderr.decode()
elf=(out/'candidate.o').read_bytes();shoff=struct.unpack_from('<I',elf,32)[0];shsize,shnum,shstr=struct.unpack_from('<HHH',elf,46)
headers=[struct.unpack_from('<10I',elf,shoff+i*shsize) for i in range(shnum)];st=headers[shstr];names=elf[st[4]:st[4]+st[5]]
textsec=next(h for h in headers if names[h[0]:].split(b'\0')[0]==b'.text');machine=elf[textsec[4]:textsec[4]+textsec[5]]
for p,line in instructions:assert struct.unpack_from('<I',machine,p-0x9d000000)[0]==encode(p,line)
assert not any(h[1] in (4,9) and h[5] for h in headers)

def run(inst,edit,old,counts,selected,direction,group_mode=False,groups=(0,32)):
 c=CPU(image);ui=0x80050000;event=0x80051000;category=(0x24,0x65)[inst]
 c.r[4]=c.r[16]=ui;c.r[5]=c.r[17]=event
 c.store(ui+6,2,inst);c.store(ui+0x20,2,int(group_mode));c.store(ui+0x44,2,edit);c.store(event+8,4,direction&0xffffffff)
 for bank in (0,1):
  base=PARAM+bank*0xd6e;group=groups[bank]
  c.store(base+category*2,2,old[bank]);c.store(base+(category-2)*2,2,group);c.store(base+(category-1)*2,2,selected[bank])
  c.store(base+(0x11 if inst==0 else 0x52)*2,2,1)
  c.store(0x80052e18+2*(60+bank),2,selected[bank])
  for cat in range(17):c.store(0x80037e90+8*(17*group+cat),4,counts[bank])
 c.store(0x80006ffe,2,1);sp=c.r[29]
 stops={0x9d02a794,0x9d02d464,0x9d02ebe8,0x9d02eae8}
 stop=c.run(0x9d02a74c,stops)
 if group_mode:
  assert stop==(0x9d02ebe8,0x9d02eae8)[inst];return c
 assert stop==(0x9d02a794,0x9d02d464)[inst]
 current=old[0 if edit in (0,2) else 1]
 delta=1 if direction>0 else -1;unclamped=current+delta
 boundary=not 0<=unclamped<=16
 active=() if boundary else ((0,1) if edit==2 else (edit,))
 assert [c.load(PARAM+b*0xd6e+category*2,2) for b in (0,1)]==[unclamped if b in active else old[b] for b in (0,1)]
 assert [c.load(PARAM+b*0xd6e+(category-1)*2,2) for b in (0,1)]==[min(max(selected[b],1) if old[b]!=unclamped else selected[b],counts[b]-1) if b in active else selected[b] for b in (0,1)]
 assert c.r[29]==sp
 if boundary:assert not ({0x9d04fa6c,0x9d04dacc}&set(c.trace)),'boundary must bypass setter entirely'
 return c

if __name__=='__main__':
 cases=0
 for inst in (0,1):
  for edit in (0,1,2):
   for a in range(17):
    for b in (0,1,8,15,16):
     for counts in ((1,1),(2,1),(1,2),(17,4)):
      for selected in ((0,0),(1,1),(255,255)):
       for direction in (-1,0,1):run(inst,edit,(a,b),counts,selected,direction);cases+=1
   run(inst,edit,(2,12),(2,1),(0,0),1,True);cases+=1
 summary={'encoding':'PASS: LLVM matches 51 words; zero relocations','actual_routing_and_setter_cases':cases,'owned_replacement_bytes':204,'unplaced_fragment_bytes':0,'total_fragments_bytes':204,'active_fragment_bytes':200,'helper_allocated_bytes':52,'helper_contiguous_active_bytes':48,'setter_call_replacements_bytes':16,'firmware_modified':False,'implementation_approval_required':True,'reason':'All fragments within the four established owned ranges; hardware validation follows an approved implementation'}
 (out/'results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
from capstone import *
import re,json
b=Path('pic.bin').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN);md.detail=True
regs={};hits=[]
for off in range(0x1a860,len(b)-3,4):
 xs=list(md.disasm(b[off:off+4],0x9d000000+off))
 if not xs:regs={};continue
 i=xs[0];op=[s.strip() for s in i.op_str.split(',')];value=None
 try:
  if i.mnemonic=='lui':value=int(op[1],0)<<16
  elif i.mnemonic in ['addiu','addi','ori'] and op[1] in regs:
   v=regs[op[1]][0]; n=int(op[2],0); value=(v+n)&0xffffffff if i.mnemonic!='ori' else v|n
  elif i.mnemonic=='move' and op[1] in regs:value=regs[op[1]][0]
  elif i.mnemonic in ['lw','sw','lh','lhu','sh','lb','lbu','sb']:
   m=re.fullmatch(r'(-?0x[0-9a-f]+|-?\d+)?\((\$\w+)\)',op[1]);base=m[2]
   if base in regs:
    addr=(regs[base][0]+int(m[1] or '0',0))&0xffffffff
    if 0x8003a118<=addr<0x8003c000 or 0x80053adc<=addr<0x80080000:hits.append({'pc':hex(i.address),'instruction':i.mnemonic+' '+i.op_str,'address':hex(addr),'kind':'memory'})
  if value is not None and (0x8003a118<=value<0x8003c000 or 0x80053adc<=value<0x80080000):hits.append({'pc':hex(i.address),'instruction':i.mnemonic+' '+i.op_str,'address':hex(value),'kind':'constant'})
 except (ValueError,TypeError,IndexError):pass
 if op and op[0].startswith('$') and i.mnemonic not in ['sw','sh','sb','swl','swr','jr','j','jal','jalr','bal','beq','bne','beqz','bnez','beql','bnel','blez','bgtz','bltz','bgez','mtc0','mtc1','mult','multu','div','divu']:regs.pop(op[0],None)
 if value is not None:regs[op[0]]=(value,i.address)
 regs={k:v for k,v in regs.items() if i.address-v[1]<64}
 if i.mnemonic in ['jr','j','jal','jalr','bal']:regs={}
Path('branch4/pic_address_candidates.json').write_text(json.dumps(hits,indent=2)+'\n')
for h in hits[:50]:print(h)
print('total',len(hits))

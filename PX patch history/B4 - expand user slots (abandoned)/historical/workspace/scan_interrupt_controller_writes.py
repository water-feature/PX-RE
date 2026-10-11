# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
from capstone import *
import json,re
b=Path('pic.bin').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN);regs={'$zero':0};hits=[]
for off in range(0x1000,len(b)-3,4):
 xs=list(md.disasm(b[off:off+4],0x9d000000+off))
 if not xs:regs={'$zero':0};continue
 i=xs[0];ops=[s.strip() for s in i.op_str.split(',')];value=None
 try:
  if i.mnemonic=='lui':value=int(ops[1],0)<<16
  elif i.mnemonic in ['addiu','ori','andi'] and ops[1] in regs:
   v=regs[ops[1]];n=int(ops[2],0);value=(v+n)&0xffffffff if i.mnemonic=='addiu' else (v|n if i.mnemonic=='ori' else v&n)
  elif i.mnemonic=='move' and ops[1] in regs:value=regs[ops[1]]
  elif i.mnemonic=='sw':
   m=re.fullmatch(r'(-?0x[0-9a-f]+|-?\d+)?\((\$\w+)\)',ops[1])
   if m and m[2] in regs:
    addr=(regs[m[2]]+int(m[1] or '0',0))&0xffffffff
    if 0xbf810000<=addr<0xbf811000:hits.append({'pc':hex(i.address),'address':hex(addr),'value':hex(regs[ops[0]]) if ops[0] in regs else None,'instruction':i.mnemonic+' '+i.op_str,'classification':'constructed MMIO address candidate; device-specific register identity not asserted'})
 except (ValueError,IndexError):pass
 if ops and ops[0].startswith('$') and i.mnemonic not in ['sw','sh','sb','swl','swr','jr','j','jal','jalr','beq','bne','beql','bnel','beqz','bnez','bgtz','blez','bgez','bltz','mtc0','mtc1','mult','multu','div','divu']:regs.pop(ops[0],None)
 if value is not None:regs[ops[0]]=value
 regs['$zero']=0
 if i.mnemonic in ['j','jr','jal','jalr','bal']:regs={'$zero':0}
Path('branch4/interrupt_controller_write_candidates.json').write_text(json.dumps(hits,indent=2)+'\n')
print('MMIO write candidates:',len(hits),'known literals:',sum(h['value'] is not None for h in hits))

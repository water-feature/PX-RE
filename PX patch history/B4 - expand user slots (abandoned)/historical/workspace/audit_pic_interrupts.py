from pathlib import Path
import json,struct
from capstone import *
b=Path('pic.bin').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
def word(pc):return struct.unpack_from('<I',b,pc-0x9d000000)[0]
def decode(pc):
 w=word(pc)
 if w&0xffe007ff in [0x41400000,0x41c00000]:
  return ('rdpgpr' if (w>>21)&31==10 else 'wrpgpr')+f' ${((w>>11)&31)}, ${((w>>16)&31)}'
 xs=list(md.disasm(struct.pack('<I',w),pc));return xs[0].mnemonic+' '+xs[0].op_str if xs else 'UNDECODED '+hex(w)
rows=[]
for off in range(0x200,0x258,8):
 pc=0x9d000000+off;w=word(pc);assert w>>26==2
 entry=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2);end=entry
 while word(end)!=0x42000018:
  end+=4;assert end-entry<0x4000
 end+=4
 instructions=[{'pc':hex(a),'word':hex(word(a)),'decode':decode(a)} for a in range(entry,end,4)]
 frames=[];priorities=[];statuswrites=[];directcalls=[];indirectcalls=[];unknown=[]
 for r in instructions:
  a=int(r['pc'],16);w=int(r['word'],16);op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31
  if op==9 and rs==29 and rt==29 and w&0x8000:frames.append((w&0xffff)-65536)
  if op==13 and rs==27 and rt==27:priorities.append({'pc':r['pc'],'literal':hex(w&0xffff),'IPL':(w&0xffff)>>10})
  if op==16 and rs==4 and rd==12 and w&7==0:statuswrites.append(r['pc'])
  if op==3:directcalls.append({'pc':r['pc'],'target':hex(((a+4)&0xf0000000)|((w&0x3ffffff)<<2))})
  if op==0 and w&63==9:indirectcalls.append(r)
  if r['decode'].startswith('UNDECODED'):unknown.append(r)
 assert word(entry)==0x415de800
 assert word(end-12)==0x41dde800 # before restored Status and eret
 rows.append({'stub':hex(pc),'entry':hex(entry),'exclusive_end':hex(end),'frame_allocations':frames,'IPL_literals':priorities,'status_writes':statuswrites,'direct_calls':directcalls,'indirect_calls':indirectcalls,'remaining_undecoded_words':unknown,'entry_decode':decode(entry),'exit_transfer_pc':hex(end-12)})
Path('branch4/pic_interrupt_audit.json').write_text(json.dumps(rows,indent=2)+'\n')
Path('branch4/pic_interrupts_completed.dis').write_text('\n'.join(f'{a:08x}: {decode(a)}' for r in rows for a in range(int(r['entry'],16),int(r['exclusive_end'],16),4))+'\n')
for r in rows:print(r['entry'],r['frame_allocations'],r['IPL_literals'],'calls',len(r['direct_calls']),'indirect',len(r['indirect_calls']),'undecoded',len(r['remaining_undecoded_words']))

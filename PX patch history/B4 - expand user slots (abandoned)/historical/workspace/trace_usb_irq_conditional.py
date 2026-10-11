from pathlib import Path
import struct,json
b=Path('pic.bin').read_bytes();roots=[r for r in json.load(open('branch4/pic_interrupt_audit.json')) if r['entry']=='0x9d0526ec'];results=[]
resolved={int(r['pc'],16):[int(t,16) for t in r['targets']] for r in json.load(open('branch4/resolved_irq_jump_tables.json'))}
resolved.update({0x9d056570:[0x9d07b860,0x9d07b8fc],0x9d0565cc:[0x9d07b860,0x9d07b8fc],0x9d07b8c8:[0x9d06bda0],0x9d07b964:[0x9d06bda0],0x9d06bdbc:[0x9d06be10,0x9d06bf0c]})
def valid(a):return 0x9d000000<=a<0x9d000000+len(b)-3 and a%4==0
def word(a):return struct.unpack_from('<I',b,a-0x9d000000)[0]
for root in roots:
 todo=[int(root['entry'],16)];seen=set();unknown=[];calls=[];frames=[];status=[]
 while todo:
  pc=todo.pop()
  if pc in seen or not valid(pc):continue
  seen.add(pc);w=word(pc);op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31;fun=w&63
  if op==9 and rs==29 and rt==29 and w&0x8000:frames.append({'pc':hex(pc),'bytes':65536-(w&0xffff)})
  if op==16 and rs==4 and rd==12 and w&7==0:status.append(hex(pc))
  if w==0x42000018:continue
  if op in [2,3]:
   seen.add(pc+4);target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2);todo.append(target)
   if op==3:calls.append({'pc':hex(pc),'target':hex(target)});todo.append(pc+8)
   continue
  if op==0 and fun in [8,9]:
   seen.add(pc+4)
   if pc in resolved:todo.extend(resolved[pc])
   elif rs!=31:unknown.append({'pc':hex(pc),'word':hex(w),'kind':'indirect call' if fun==9 else 'indirect jump'})
   if fun==9:todo.append(pc+8)
   continue
  branch=op in [1,4,5,6,7,20,21,22,23] or (op in [16,17] and rs==8)
  if branch:
   seen.add(pc+4);imm=w&0xffff;imm=imm-65536 if imm&0x8000 else imm;todo.extend([pc+8,pc+4+4*imm]);continue
  todo.append(pc+4)
  if len(seen)>100000:raise RuntimeError('Reachability limit exceeded')
 results.append({'entry':root['entry'],'candidate_reachable_words':len(seen),'direct_calls':calls,'unresolved_indirect_edges':unknown,'negative_sp_sites':frames,'unique_negative_sp_bytes':sum(x['bytes'] for x in frames),'status_writes':status,'assumptions':'Observed transfer request callbacks and parent registration only; event dispatch restricted to proven emitted events15/16. Writer set not exhaustive.', 'limitations':'Raw MIPS32 control-flow closure; unresolved indirect jumps are stopping points, delay-slot effects not inventoried. Cycles/repeated activation not bounded. Not full stack analysis.'})
Path('branch4/usb_irq_conditional_reachability.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:print(r['entry'],r['candidate_reachable_words'],'words',len(r['unresolved_indirect_edges']),'open edges',r['unique_negative_sp_bytes'],'unique frame bytes')

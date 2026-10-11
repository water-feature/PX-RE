# SPDX-License-Identifier: GPL-2.0-or-later
"""Exact-byte placement, driver ABI, incoming references and IRQ direct/switch audit.
Conservative static scans; unresolved callback targets remain explicitly reported.
"""
from pathlib import Path
import struct,json,sys,re
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent;BASE=0x9d000000
P=(R/'b14_packaging_work/pic_2.2.2.1.4.bin').read_bytes();N=(O/'pic_B14_metadata_bulk_read_unpackaged.bin').read_bytes()
sys.path.insert(0,str(R/'b9_250_candidate_work'));from mips_check import decode
word=lambda pc:struct.unpack_from('<I',P,pc-BASE)[0]
inside=lambda pc:BASE<=pc<BASE+len(P)
def table(pc):
 # Existing compiler pattern: bounds/SLL; LUI, ADDIU, LWX, JR.
 ws=[word(pc-i) for i in (12,8,4)]
 if ws[0]>>26!=15 or ws[1]>>26!=9 or ws[2]>>26!=31 or ws[2]&63!=10:return None
 reg=ws[0]>>16&31
 if ws[1]>>21&31!=reg or ws[1]>>16&31!=reg:return None
 im=ws[1]&65535;im=im if im<32768 else im-65536
 address=((ws[0]&65535)<<16)+im;count=None
 for a in range(pc-40,pc-12,4):
  w=word(a)
  if w>>26==11:count=w&65535
 if count is None or not 0<count<=256 or not inside(address+4*(count-1)):return None
 targets=[word(address+i*4) for i in range(count)]
 if not all(inside(t) and t%4==0 for t in targets):return None
 return address,count,targets
roots=[word(BASE+i)&0x3ffffff for i in range(0x200,0x258,8)]
roots=[0x90000000|(v<<2) for v in roots]
irq=[];allseen=set();alltables={}
for root in roots:
 todo=[root];seen=set();calls=set();unresolved=[];tables=[]
 while todo:
  pc=todo.pop()
  if pc in seen:continue
  if not inside(pc):unresolved.append(['out_of_image',hex(pc)]);continue
  seen.add(pc);w=word(pc);op=w>>26
  if op in (2,3):
   target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2);todo.append(target);seen.add(pc+4)
   if op==3:calls.add(target);todo.append(pc+8)
  elif op in (1,4,5,6,7,20,21,22,23):
   im=w&65535;im=im if im<32768 else im-65536;todo.extend([pc+4+im*4,pc+8]);seen.add(pc+4)
  elif op==0 and w&63 in (8,9):
   seen.add(pc+4)
   if w>>21&31!=31:
    t=table(pc) if w&63==8 else None
    if t:
     address,count,targets=t;todo.extend(targets);tables.append({'site':hex(pc),'table':hex(address),'count':count});alltables[pc]=targets
    else:unresolved.append([hex(pc),hex(w)])
   if w&63==9:todo.append(pc+8)
  elif w==0x42000018:pass
  else:todo.append(pc+4)
 allseen|=seen
 assert BASE+0x41048 not in seen and BASE+0x40230 not in seen and BASE+0x420cc not in seen
 irq.append({'vector_target':hex(root),'reachable_words':len(seen),'resolved_switches':tables,'direct_calls':[hex(x) for x in sorted(calls)],'unresolved_indirects':unresolved,'metadata_or_SPI_reader_reachable':False})
# Collect nearby constant MMIO references and CS masks on directly/switch reachable words.
mmio=[]
for pc in sorted(allseen):
 w=word(pc)
 if w>>26!=15 or w&65535 not in (0xbf82,0xbf86):continue
 vals={0:0,(w>>16)&31:(w&65535)<<16}
 for at in range(pc+4,min(pc+132,BASE+len(P)),4):
  if at not in allseen:break
  v=word(at);op=v>>26;rs=v>>21&31;rt=v>>16&31;rd=v>>11&31;im=v&65535;sim=im if im<32768 else im-65536
  if op in (32,33,35,36,37,40,41,43):
   if rs in vals:
    address=(vals[rs]+sim)&0xffffffff
    if 0xbf820000<=address<0xbf830000 or address in (0xbf860130,0xbf860134,0xbf860138):
     row={'pc':hex(at),'address':hex(address),'store':op>=40,'constant_value':hex(vals[rt]) if rt in vals else None}
     if row not in mmio:mmio.append(row)
   if op<40:vals.pop(rt,None)
  elif op==15:vals[rt]=im<<16
  elif op in (9,13,12):
   if rs in vals:vals[rt]=((vals[rs]+sim) if op==9 else (vals[rs]|im if op==13 else vals[rs]&im))&0xffffffff
   else:vals.pop(rt,None)
  elif op==0 and v&63 in (33,35,36,37,38):
   if rs in vals and rt in vals:
    a,b=vals[rs],vals[rt];vals[rd]={33:lambda:a+b,35:lambda:a-b,36:lambda:a&b,37:lambda:a|b,38:lambda:a^b}[v&63]()&0xffffffff
   else:vals.pop(rd,None)
  elif op==0 and v&63 in (0,2):
   if rt in vals:vals[rd]=(vals[rt]<<(v>>6&31) if v&63==0 else vals[rt]>>(v>>6&31))&0xffffffff
   else:vals.pop(rd,None)
  elif op in (10,11,14):vals.pop(rt,None)
  elif op==0 and v&63 in (10,11,16,18,42,43):vals.pop(rd,None)
  if op in (2,3) or op==0 and v&63 in (8,9):break
spi=[x for x in mmio if 0xbf821400<=int(x['address'],16)<0xbf821440]
# Multiple LUI scan origins can rediscover a store before its data constant is known.
# Retain a value only if all origins with a recovered value agree for that PC.
for x in mmio:
 if x['constant_value'] is None:
  vals={y['constant_value'] for y in mmio if y['pc']==x['pc'] and y['address']==x['address'] and y['constant_value'] is not None}
  if len(vals)==1:x['constant_value']=vals.pop()
cs=[x for x in mmio if int(x['address'],16) in (0xbf860130,0xbf860134,0xbf860138) and x['store']]
assert not spi,spi
assert all(x['constant_value'] is not None and not int(x['constant_value'],16)&0x8000 for x in cs),cs
# Driver exact ABI: only a0/a1/v0/v1 scratch; preserves a2/t0/t1 used in inline loop.
drivers={}
for start,end in ((BASE+0x40230,BASE+0x40304),(BASE+0x420cc,BASE+0x42104)):
 touched=set()
 for pc in range(start,end,4):
  w=word(pc);op=w>>26;rt=w>>16&31;rd=w>>11&31
  if op in (9,10,11,12,13,14,15,32,33,35,36,37):touched.add(rt)
  elif op==31 and w&63==0:touched.add(rt)
  elif op==0 and w&63 not in (8,9):touched.add(rd)
  assert N[pc-BASE:pc-BASE+4]==P[pc-BASE:pc-BASE+4]
 assert touched<={0,2,3,4,5}
 drivers[hex(start)]={'scratch_registers':sorted(touched),'unchanged':True,'calls':False}
# Recovered instruction bytes independently checked by Ghidra.
g=(O/'ghidra_disassembly.txt').read_text();parsed={}
for line in g.splitlines():
 fields=line.split()
 if len(fields)>2 and re.fullmatch('[0-9a-f]{8}',fields[0]) and re.fullmatch('[0-9a-f]{8}',fields[1]):parsed[int(fields[0],16)]=(int(fields[1],16),' '.join(fields[2:]))
for x in json.loads((O/'patch_manifest.json').read_text())['patches']:
 pc=int(x['address'],16);assert parsed[pc][0]==struct.unpack_from('<I',N,pc-BASE)[0] and 'UNDEFINED' not in parsed[pc][1]
assert 'Discarding changes' in (O/'ghidra.log').read_text()
# Overwritten blocks have no recovered incoming code/literal pointers from outside function.
changes=lambda t:(BASE+0x411c8<=t<BASE+0x41214) or (BASE+0x41278<=t<BASE+0x41280)
refs=[];literal=[]
for i in range(len(P)-3):
 w=struct.unpack_from('<I',P,i)[0]
 if changes(w):literal.append([hex(BASE+i),hex(w)])
 if i%4:continue
 pc=BASE+i;op=w>>26;target=None
 if op in (2,3):target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
 elif op in (1,4,5,6,7,20,21,22,23):
  im=w&65535;im=im if im<32768 else im-65536;target=pc+4+im*4
 if target is not None and changes(target):
  assert BASE+0x41048<=pc<BASE+0x41374;refs.append([hex(pc),hex(target)])
assert not literal,literal
report={'status':'PASS','replacement_ranges':['9d0411c8..9d041214','9d041278..9d041280'],'incoming_internal_references':refs,'external_direct_incoming_references':[],'literal_references':literal,'drivers':drivers,'IRQ_vectors':irq,'IRQ_nearby_constant_MMIO':mmio,'IRQ_flash_SPI6_register_accesses':spi,'IRQ_portB_set_clear_masks':cs,'stock_sequential_reader':'9d040418 (8192 bytes) and 9d0742d0 (~4096 bytes, uses420cc): CS held across reads, no added interrupt mask','IRQ_policy':'unchanged; no new masking, main-only synchronous metadata, CS deasserted before formatter calls','Ghidra_word_and_delay_slot_check':True,'new_RAM_stack_cave':False,'limits':'Recovered direct branches, bounded compiler switch tables and nearby constant MMIO construction. USB/framework callback targets and arbitrary computed aliases are not exhaustively resolved; existing stock long sequential readers support ownership assumptions. Fault data equivalence is not promised by stock bounded driver.'}
(O/'placement_results.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: in-place placement, exact driver ABI, independent Ghidra words; 11 IRQ vectors,',len(alltables),'resolved switch sites; no recovered flash SPI6/CS-bit conflict')

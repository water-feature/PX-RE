# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded MIPS assembler, decoded-byte B7 validation and deterministic packaging."""
from pathlib import Path
import sys,struct,hashlib,json
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import b7_combined_instruction_model as model
OUT=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
base=model.IMAGE
assert sha((ROOT/'PxUpdate_V2.2.2.0.7.bin').read_bytes())=='2fe41c83415c1d85efd7848a31511157162528ec4a83d08045be7e8bcee2e753'
assert not (ROOT/'PxUpdate_V2.2.2.0.8.bin').exists(), 'Revision .8 already exists: stop for review'
r=model.R
# Explicit encodings, with immediate/target range checks. Planning tuples are
# assembly input only: execution below never consults BLOCKS or OVERLAY.
def assemble(pc,row):
 op,*a=row
 if op=='nop': return 0
 if op=='move': op,a='addu',[a[0],a[1],'zero']
 if op=='li': op,a='addiu',[a[0],'zero',a[1]]
 if op in ('j','jal'):
  target=a[0];assert target%4==0 and target>>28==(pc+4)>>28
  return ({'j':2,'jal':3}[op]<<26)|((target>>2)&0x3ffffff)
 if op=='jr': return r[a[0]]<<21|8
 if op in ('beq','bne'):
  disp=(a[2]-pc-4)//4;assert a[2]%4==0 and -32768<=disp<=32767
  return {'beq':4,'bne':5}[op]<<26|r[a[0]]<<21|r[a[1]]<<16|(disp&65535)
 if op=='sll': return r[a[1]]<<16|r[a[0]]<<11|a[2]<<6
 if op in ('addu','subu','sltu','movn'):
  return r[a[1]]<<21|r[a[2]]<<16|r[a[0]]<<11|{'addu':33,'subu':35,'sltu':43,'movn':11}[op]
 if op in ('addiu','sltiu','andi'):
  assert (-32768<=a[2]<=32767) if op!='andi' else (0<=a[2]<=65535)
  return {'addiu':9,'sltiu':11,'andi':12}[op]<<26|r[a[1]]<<21|r[a[0]]<<16|(a[2]&65535)
 if op in ('lw','lhu','sw','sh'):
  assert -32768<=a[1]<=32767
  return {'lw':35,'lhu':37,'sw':43,'sh':41}[op]<<26|r[a[2]]<<21|r[a[0]]<<16|(a[1]&65535)
 raise AssertionError(row)
pic=bytearray(base);changes={}
def put(addr,word,reason):
 off=addr-model.BASE;old=struct.unpack_from('<I',pic,off)[0]
 struct.pack_into('<I',pic,off,word)
 changes[f'{addr:08X}']={'old':f'{old:08X}','new':f'{word:08X}','reason':reason}
source=[]
for pc,row in sorted(model.BLOCKS.items()):
 assert base[pc-model.BASE:pc-model.BASE+4]==b'\xff'*4
 put(pc,assemble(pc,row),'B7 helper')
 source.append(f'{pc:08X}: {row!r}')
for pc,row in sorted(model.OVERLAY.items()): put(pc,assemble(pc,row),'B7 hook/gate')
for pc,word in [(0x9D0258B4,0x24842240),(0x9D051BC4,0x24842240),(0x9D052FEC,0x24020004)]: put(pc,word,'PIC 2.2.4 version')
(OUT/'b7_assembly_input.txt').write_text('\n'.join(source)+'\n')
# Independent raw decoder retained from existing model; bind its IMAGE only
# during decode, leaving descriptor summaries tied to the exact baseline.
def raw_decode(pc,image):
 old=model.IMAGE
 try:
  model.IMAGE=image
  return model.decode(pc)
 finally: model.IMAGE=old
class DecodedMachine(model.Machine):
 def instruction(self,pc): return raw_decode(pc,pic if self.design else base)
model.Machine=DecodedMachine
report=model.run()
report.pop('symbolic_instructions');report.pop('symbolic_inserted_bytes')
report['decoded_candidate_instructions']=len(model.BLOCKS)
report['helper_bytes']=len(model.BLOCKS)*4
report['limitations']=['External descriptor/output/UI calls retain the established contract summaries; transport and hardware are not simulated.','PIC installation, audio and display repaint require hardware checks.']
# Decode every emitted instruction independently; check delayed control flow.
listing=[]
for pc in sorted(set(model.BLOCKS)|set(model.OVERLAY)):
 row=raw_decode(pc,pic)
 listing.append(f'{pc:08X} {struct.unpack_from("<I",pic,pc-model.BASE)[0]:08X} {row!r}')
 if row[0] in ('j','jal','jr','beq','bne'):
  delay=raw_decode(pc+4,pic)
  assert delay[0] not in ('j','jal','jr','beq','bne','beql','bnel')
for pc in model.GATES: assert raw_decode(pc+4,pic)==('nop',)
assert pic[0x1200:0x1220]==base[0x1200:0x1220]
assert pic[0x295B0:0x295B8]==base[0x295B0:0x295B8]
assert pic[0x1480:0x1A84C]==base[0x1480:0x1A84C]
assert pic[0x1394:0x1480]==b'\xff'*(0x1480-0x1394)
assert len(pic)==len(base)==0x81960
allowed=set()
for addr in changes: allowed.update(range(int(addr,16)-model.BASE,int(addr,16)-model.BASE+4))
assert all(i in allowed for i,(a,b) in enumerate(zip(base,pic)) if a!=b)
# The actual setter frame preserves +10 across stock callees. Adversarial
# volatile clobbers plus recursive Center/custom calls in all cases above test
# nested returns, original-request preservation and callee-saved registers.
# Extra unrelated controls cover the normalization guard's entire descriptor range.
unrelated=0
for osc in (0,1):
 for sel in (0,1,2):
  for id in (11,17):
   for flag in (0,1):
    args=([(100,400,250,1),(600,900,750,1)],osc,flag,0)
    old=DecodedMachine(*args,design=False);new=DecodedMachine(*args)
    old.edit(sel,id+osc*0x41,20);new.edit(sel,id+osc*0x41,20)
    assert old.m==new.m or all(old.read(old.slot(p,k),2)==new.read(new.slot(p,k),2) for p in (0,1) for k in range(0x6B7))
    assert old.events==new.events
    unrelated+=1
report['unrelated_control_equivalence_cases']=unrelated
# Exact .7 record parser. PIC trailer is inherited 0x3030, deliberately not
# replaced by a payload word sum: established QNX type-3 parser ignores it.
package=bytearray((ROOT/'PxUpdate_V2.2.2.0.7.bin').read_bytes())
records=[];pos=1
assert package[0]==0xF0 and package[-1]==0xF7
for typ in (1,2,3):
 header=bytes(package[pos:pos+12]);assert header[0]==typ and header[1]==0x7B and header[7]==0x7A
 n=int.from_bytes(header[8:12],'big');start=pos+12;end=start+n
 records.append((pos,start,end));pos=end+2
assert pos==len(package)-1
app_h,app_s,app_e=records[0];fpga_h,fpga_s,fpga_e=records[1];pic_h,pic_s,pic_e=records[2]
old_app=bytes(package[app_s:app_e]);app=bytearray(old_app)
for off in (0x1F4E3,0x250EF): assert app[off]==7;app[off]=8
assert [i for i,(a,b) in enumerate(zip(old_app,app)) if a!=b]==[0x1F4E3,0x250EF]
package[app_h+2:app_h+7]=bytes([2,2,2,0,8])
package[pic_h+2:pic_h+7]=bytes([2,2,4,0,0])
package[app_s:app_e]=app;package[pic_s:pic_e]=pic
wordsum=lambda b:sum(struct.unpack('<'+'H'*(len(b)//2),b))&65535
package[app_e:app_e+2]=struct.pack('<H',wordsum(app))
assert package[fpga_h:fpga_e+2]==(ROOT/'PxUpdate_V2.2.2.0.7.bin').read_bytes()[fpga_h:fpga_e+2]
assert package[pic_e:pic_e+2]==b'00'
assert len(package)==3151848
# Both actual PIC report delay-slot immediates must agree with independent
# container bytes and the formatter argument; no package-only version claim.
for off in (0x258B4,0x51BC4):
 w=struct.unpack_from('<I',pic,off)[0]
 assert w>>16==0x2484
 packed=w&65535
 components=[(packed>>shift)&15 for shift in (12,8,4,0)]+[0]
 assert components==list(package[pic_h+2:pic_h+7])
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,0x52FEC)[0])).hexdigest()=='98ff8498f1947f9ac317462fe8d8bfdbbf4d9183c5a24590ccce0eeac32d1d66'
report['version_verification']={'application_header':[2,2,2,0,8],'PIC_header':[2,2,4,0,0],'PIC_reports_match_header':True,'M_formatter':'2.2.4','DSP_reply_and_updater_revision_offsets':['0x1F4E3','0x250EF'],'PIC_trailer':'3030 (inherited, ignored by type-3 parser)','application_checksum':f'{wordsum(app):04X}','FPGA_byte_identical':True,'QNX_only_two_version_bytes_changed':True}
report['placement']={'payload_size':len(pic),'helpers_start':'0x9D001220','helpers_exclusive_end':'0x9D001394','data_boundary':'0x9D001480','B3_preserved':True,'all_changes_accounted':True}
report['hashes']={'baseline_package':sha((ROOT/'PxUpdate_V2.2.2.0.7.bin').read_bytes()),'candidate_package':sha(package),'PIC':sha(pic),'QNX':sha(app),'FPGA':sha(package[fpga_s:fpga_e])}
(OUT/'b7_candidate_decoded.txt').write_text('\n'.join(listing)+'\n')
(OUT/'b7_patch_manifest.json').write_text(json.dumps(changes,indent=2)+'\n')
(OUT/'b7_validation_results.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'pic_2.2.2.0.8.bin').write_bytes(pic)
(OUT/'voice_2.2.2.0.8_qnx.elf').write_bytes(app)
(ROOT/'PxUpdate_V2.2.2.0.8.bin').write_bytes(package)
print(json.dumps(report,indent=2))

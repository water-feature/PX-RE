# SPDX-License-Identifier: GPL-2.0-or-later
"""Package saved/validated .1.12; exact .1.11 records, FPGA unchanged."""
from pathlib import Path
import sys,struct,json,hashlib
O=Path(__file__).resolve().parent;R=O.parents[1]
sys.path[:0]=[str(R/'b15_candidate_work'),str(R)]
from build_candidate_1_8 import parse,serialize,sum16,write_ranges
BASE=R/'b15_candidate_work/lfo_endpoint_investigation/completion_fix'
REV=bytes([2,2,2,1,12]);sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 validation=json.loads((O/'validation.json').read_text());integration=json.loads((O/'integration.json').read_text());assert validation['status']==integration['status']=='PASS'
 old=(BASE/'PxUpdate_V2.2.2.1.11_B5_completion_fade_candidate.bin').read_bytes();assert sha(old)=='29aff5a6cbf6d603ae86f23525454bbbcbe568c3930d65c2064ce827080c86a8'
 base=parse(old);assert serialize(base)==old
 app=(O/'voice_2.2.2.1.12_qnx.elf').read_bytes();pic=(O/'pic_2.2.2.1.12.bin').read_bytes()
 assert sha(app)==validation['QNX_sha256']==integration['QNX_sha256'] and sha(pic)==validation['PIC_sha256']==integration['PIC_sha256']
 assert sha(base[0][1])==integration['baseline_QNX_sha256']
 assert base[0][1]==(BASE/'voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf').read_bytes()
 assert base[2][1]==(BASE/'pic_2.2.2.1.11_B5_completion_fade_candidate.bin').read_bytes()
 assert all(h[2:7]==bytes([2,2,2,1,11]) for h,p,t,_ in (base[0],base[2]))
 rows=[]
 for i,p in [(0,app),(1,base[1][1]),(2,pic)]:
  h,_,t,_=base[i]
  if i!=1:h=h[:2]+REV+h[7:8]+len(p).to_bytes(4,'big')
  if i==0:t=struct.pack('<H',sum16(p))
  rows.append((h,p,t,0))
 package=serialize(rows);ex=parse(package)
 assert len(package)==len(old)==3187784 and serialize(ex)==package
 assert ex[0][1]==app and ex[2][1]==pic and ex[1]==base[1] and ex[2][2]==b'00'
 assert all(int.from_bytes(t,'little')==sum16(p) for h,p,t,_ in ex[:2])
 # Five-component application report is bit-packed, PIC fields use report thunks.
 reply=struct.unpack_from('<I',app,0x1f4e3)[0];packed=reply&0xffff
 assert reply==0x4013921c and [packed>>14,(packed>>11)&7,(packed>>8)&7,(packed>>4)&15,packed&15]==list(REV)
 assert app[0x250ef]==12 and ex[0][0][2:7]==ex[2][0][2:7]==REV
 import validate_pic_emission as v
 m=v.m
 for site,target in [(0x258c0,0x9d075c1c),(0x51bc8,0x9d075b18)]:
  c=m.CPU(pic);c.run(m.BASE+site,{target});assert c.g('a0')==0x402a000c and c.g('ra')==m.BASE+site+8
 for off in (0x258b4,0x51bc4):
  c=m.CPU(pic);c.s('a0',0x40290000);c.fetch_simple(m.BASE+off);assert c.g('a0')==0x40292221
 assert pic[0x52fe4:0x52ff8]==base[2][1][0x52fe4:0x52ff8] # inherited three-field M formatter
 # Execute actual updater gate instruction bytes, including baseline acceptance.
 source=(R/'b7_candidate_work/validate_version_gates.py').read_text();chunk=source[source.index('def gate('):source.index('\napp_cases=')]
 ns=dict(app=app,pic=pic,struct=struct);exec(chunk,ns);gate=ns['gate'];cases=0
 for incoming in [list(REV),[2,2,2,1,11],[2,2,2,1,10]]:
  assert (not bool(gate('app',incoming).get(0x373c,0)))==(incoming==list(REV))
  assert bool(gate('pic',list(REV),incoming).get(0x3744,0))==(incoming==list(REV));cases+=2
 for i in range(5):
  incoming=list(REV);incoming[i]^=1
  assert gate('app',incoming).get(0x373c,0) and not gate('pic',incoming,list(REV)).get(0x3744,0);cases+=2
 ns['app']=base[0][1];ns['pic']=base[2][1]
 assert gate('app',list(REV)).get(0x373c,0) and not gate('pic',list(REV),[2,2,2,1,11]).get(0x3744,0);cases+=2
 # Actual PIC receiver block-checksum arithmetic and comparison instructions.
 blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)];c=m.CPU(pic)
 for block in blocks:
  c.write(m.GP-0x7f20,0,4)
  pcs=range(0x9d044484,0x9d04449c,4) if len(block)==4096 else range(0x9d04466c,0x9d044684,4)
  for low,high in zip(block[::2],block[1::2]):
   c.write(m.GP-0x7f1c,low,4);c.s('v0',high)
   for pc in pcs:c.simple(m.decode(pic,pc))
  expected=sum16(block);assert c.read(m.GP-0x7f20,2)==expected
  for incoming in (expected,expected^1):
   c.s('v0',incoming&255);c.s('a1',incoming>>8);c.s('v1',expected)
   for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):c.simple(m.decode(pic,pc))
   assert (c.g('v0')==c.g('v1'))==(incoming==expected)
 # Every container difference must correspond to an independently validated
 # component interval, application checksum or applicable record revision.
 allowed=[(ex[0][3]+x['start'],ex[0][3]+x['end']) for x in integration['allowed_QNX_ranges']]
 allowed += [(ex[2][3]+n,ex[2][3]+n+1) for n in (0x1394,0x13a0)]
 allowed += [(ex[i][3]-10,ex[i][3]-5) for i in (0,2)]
 allowed += [(ex[0][3]+len(app),ex[0][3]+len(app)+2)]
 changed=[i for i,(x,y) in enumerate(zip(old,package)) if x!=y]
 assert all(sum(lo<=i<hi for lo,hi in allowed)==1 for i in changed)
 target=R/'PxUpdate_V2.2.2.1.12.bin'
 if target.exists():assert target.read_bytes()==package,'Refuse different existing updater'
 else:target.write_bytes(package)
 saved=target.read_bytes();assert saved==package;actual=parse(saved)
 assert actual[0][1]==app and actual[2][1]==pic and actual[1]==base[1]
 (O/'reextracted_qnx.elf').write_bytes(actual[0][1]);(O/'reextracted_pic.bin').write_bytes(actual[2][1])
 report=dict(status='PASS',version=list(REV),baseline='2.2.2.1.11',package=str(target),package_bytes=len(saved),package_sha256=sha(saved),QNX_sha256=sha(actual[0][1]),PIC_sha256=sha(actual[2][1]),FPGA_sha256=sha(actual[1][1]),FPGA_entire_record_unchanged=True,PIC_only_two_revision_bytes=True,reextracted_components_match_emitted_validation=True,all_package_differences_accounted=True,package_differing_bytes=len(changed),application_checksum_hex=ex[0][2].hex(),FPGA_checksum_hex=ex[1][2].hex(),PIC_trailer_hex=ex[2][2].hex(),version_gate_cases=cases,PIC_checksum_blocks=len(blocks),checksum_accept_reject_cases=2*len(blocks),hardware='NOT VERIFIED',flashed=False)
 report['diffs']={'package':write_ranges(O/'package_diff.tsv',old,saved,'package'),'QNX':write_ranges(O/'packaged_QNX_diff.tsv',base[0][1],app,'QNX',actual[0][3]),'PIC':write_ranges(O/'packaged_PIC_diff.tsv',base[2][1],pic,'PIC',actual[2][3],0x9d000000)}
 (O/'package_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

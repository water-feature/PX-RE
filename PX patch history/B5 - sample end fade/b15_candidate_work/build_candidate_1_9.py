"""Package the reviewed QNX LFO endpoint fix over retained B15 .1.8; no flashing."""
from pathlib import Path
import hashlib,json,struct,sys
from build_candidate_1_8 import parse,serialize,sum16,write_ranges
O=Path(__file__).resolve().parent;R=O.parent;REV=bytes([2,2,2,1,9])
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 old=(O/'PxUpdate_V2.2.2.1.8_B15_candidate.bin').read_bytes()
 assert sha(old)=='200a2d66625f840e0de93ca83518d025aa6de6cb47b7032bfc304384f9922535'
 baseline=parse(old);assert serialize(baseline)==old
 fixed=(O/'lfo_endpoint_investigation/voice_B15_LFO_endpoint_fix_UNPACKAGED.elf').read_bytes()
 evidence=json.loads((O/'lfo_endpoint_investigation/results.json').read_text())
 assert evidence['status']=='PASS' and all(t['exit']==0 for t in evidence['tests'])
 assert sha(fixed)==evidence['output_sha256']=='216180e934aadbc67700e6b683fdf839c2d47ce4e9c188b3584563a13bb66cad'
 assert sha(baseline[0][1])==evidence['input_sha256']
 pic=bytearray(baseline[2][1]);app=bytearray(fixed)
 for off in (0x1394,0x13a0):
  assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,off)[0])).hexdigest()=='2f0dba6b3a9cfe043aa66c790e12ae85e3d1545e814c2a4f394594cedbd4a182'
  struct.pack_into('<I',pic,off,0x24840009)
 assert app[0x1f4e3]==0x18 and app[0x250ef]==8
 app[0x1f4e3],app[0x250ef]=0x19,9
 assert [i for i,(a,b) in enumerate(zip(app,fixed)) if a!=b]==[0x1f4e3,0x250ef]
 assert [i for i,(a,b) in enumerate(zip(pic,baseline[2][1])) if a!=b]==[0x1394,0x13a0]
 rows=[]
 for i,payload in ((0,bytes(app)),(1,baseline[1][1]),(2,bytes(pic))):
  h,_,t,_=baseline[i]
  if i!=1:h=h[:2]+REV+h[7:8]+len(payload).to_bytes(4,'big')
  if i==0:t=struct.pack('<H',sum16(payload))
  rows.append((h,payload,t,0))
 package=serialize(rows);extracted=parse(package)
 assert len(package)==len(old)==3187784
 assert extracted[0][1]==app and extracted[2][1]==pic and extracted[1]==baseline[1]
 assert all(int.from_bytes(t,'little')==sum16(p) for h,p,t,_ in extracted[:2])
 assert extracted[2][2]==b'00'
 # Verify packaged ELF load/unwind mappings and inherited FDE bytes.
 sys.path.insert(0,str(R));from b5_elf_placement_check import ExactElf,decode_index
 a=ExactElf(baseline[0][1]);b=ExactElf(bytes(app))
 ah=next(p for p in a.phdr if p['type']==0x6474e550);bh=next(p for p in b.phdr if p['type']==0x6474e550)
 _,ap=decode_index(a.read(ah['va'],ah['filesz']),ah['va']);_,bp=decode_index(b.read(bh['va'],bh['filesz']),bh['va'])
 assert len(bp)==len(ap)+1
 for pc,fde in ap:assert (pc,fde) in bp and a.read(fde,a.fde(fde)['length']+4)==b.read(fde,a.fde(fde)['length']+4)
 for pc,fde in bp:assert b.fde(fde)['pc']==pc
 assert b.read(0xf15dc,5)==fixed[0xf15dc:0xf15e1]
 assert b.read(0xf3c10,44)==fixed[0xf3c10:0xf3c3c]
 # Bounded updater version/thunk/checksum execution, same interpreter as .1.8.
 import validate_pic_emission as v
 m=v.m
 for site,target_pc in ((0x258c0,0x9d075c1c),(0x51bc8,0x9d075b18)):
  c=m.CPU(pic);c.run(m.BASE+site,{target_pc});assert c.g('a0')==0x402a0009 and c.g('ra')==m.BASE+site+8
 for off in (0x258b4,0x51bc4):
  c=m.CPU(pic);c.s('a0',0x40290000);c.fetch_simple(m.BASE+off);assert c.g('a0')==0x40292221
 assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',app,0x1f4e3)[0])).hexdigest()=='d211547c397a1f8f4200c32409ff2468aead39e533b0af944f1863e33034836c'
 source=(R/'b7_candidate_work/validate_version_gates.py').read_text();ns={'app':app,'pic':pic,'struct':struct}
 exec(source[source.index('def gate('):source.index('\napp_cases=')],ns);gate=ns['gate'];cases=0
 for incoming in (list(REV),[2,2,2,1,8],[2,2,2,1,7]):
  assert (not bool(gate('app',incoming).get(0x373c,0)))==(incoming==list(REV))
  assert bool(gate('pic',list(REV),incoming).get(0x3744,0))==(incoming==list(REV));cases+=2
 for i in range(5):
  incoming=list(REV);incoming[i]^=1
  assert gate('app',incoming).get(0x373c,0) and not gate('pic',incoming,list(REV)).get(0x3744,0);cases+=2
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
 names={'package':'PxUpdate_V2.2.2.1.9_B15_LFO_fade_candidate.bin','PIC':'pic_2.2.2.1.9_B15_LFO_fade_candidate.bin','QNX':'voice_2.2.2.1.9_B15_LFO_fade_candidate_qnx.elf'}
 for kind,payload in (('package',package),('PIC',pic),('QNX',app)):
  p=O/names[kind]
  if p.exists():assert p.read_bytes()==payload,'refuse different existing artifact'
  else:p.write_bytes(payload)
 reread=parse((O/names['package']).read_bytes());assert reread==extracted
 ph=[struct.unpack_from('<IIQQQQQQ',app,b.phoff+i*b.phentsize) for i in range(b.phnum)]
 diffs={'PIC':write_ranges(O/'candidate_1_9_pic_diff.tsv',baseline[2][1],pic,'PIC',extracted[2][3],0x9d000000),
        'QNX':write_ranges(O/'candidate_1_9_qnx_diff.tsv',baseline[0][1],app,'QNX',extracted[0][3],ph=ph),
        'package':write_ranges(O/'candidate_1_9_package_diff.tsv',old,package,'container')}
 report={'status':'PASS_PACKAGE_BYTES_MODELED_UPDATER_CHECKS','version':list(REV),'files':names,'hashes':{k:sha((O/n).read_bytes()) for k,n in names.items()},'package_bytes':len(package),'QNX_bytes':len(app),'PIC_bytes':len(pic),'baseline_version':'2.2.2.1.8','diffs_vs_1_8':diffs,'FPGA_record_unchanged':True,'PIC_only_version_metadata_changed':True,'metadata_delta_from_fixed_QNX':['0x1f4e3','0x250ef'],'all_inherited_fdes_unchanged':len(ap),'new_fde_count':1,'version_gate_cases':cases,'PIC_checksum_blocks':len(blocks),'checksum_accept_reject_cases':2*len(blocks),'fade_ms':5,'behavioral_regression_evidence':'lfo_endpoint_investigation/results.json','hardware':'NOT VERIFIED','flashed':False,'limits':'Actual core/dispatch host tests with modeled reader/Load; QNX runtime and target acoustics not executed; previous B15 checklist remains open.'}
 (O/'candidate_1_9_results.json').write_text(json.dumps(report,indent=2)+'\n')
 (O/'candidate_1_9_SHA256SUMS').write_text(''.join(f'{sha((O/n).read_bytes())}  {n}\n' for n in list(names.values())+['build_candidate_1_9.py','candidate_1_9_results.json','candidate_1_9_pic_diff.tsv','candidate_1_9_qnx_diff.tsv','candidate_1_9_package_diff.tsv']))
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()

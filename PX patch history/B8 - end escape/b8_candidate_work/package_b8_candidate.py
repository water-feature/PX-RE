#!/usr/bin/env python3
"""Package validated combined candidate; exclusively creates distinct outputs."""
import json,sys,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'b5_packaging_work'))
from package_b5_test import records,checksum
from verify_b8_package import verify
sha=lambda b:hashlib.sha256(b).hexdigest()
BASE_SHA='41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587'
ELF_SHA='85b76594924f1a8b7deffec1d81f79feb848edf6c631d0eb2b6c24f49aa393f1'
BASE_ELF_SHA='07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35'
VERSION=(2,2,2,0,6)
def compose(base,elf):
 if sha(base)!=BASE_SHA or sha(elf)!=ELF_SHA:raise ValueError('pinned packaging input hash mismatch')
 rr=records(base);r=rr[0]
 if sha(r['payload'])!=BASE_ELF_SHA:raise ValueError('pinned tested B5 ELF mismatch')
 h=bytearray(r['header']);h[2:7]=bytes(VERSION);h[8:12]=len(elf).to_bytes(4,'big')
 return b'\xf0'+h+elf+checksum(elf).to_bytes(2,'little')+base[r['end']:]
def main():
 m=json.loads((ROOT/'b8_candidate_manifest.json').read_text());h=json.loads((ROOT/'b8_integration_validation.json').read_text());v=json.loads((ROOT/'b8_candidate_validation.json').read_text())
 if m['status']!='validated_structural_host_candidate' or m['candidate_sha256']!=ELF_SHA or h['host_exit']!=0 or not all(c['passed'] for c in v['checks']):raise ValueError('validation gate failed')
 for n,d in m['source_sha256'].items():
  if sha((ROOT/n).read_bytes())!=d:raise ValueError('candidate source checkpoint mismatch '+n)
 for n,d in h['test_sources'].items():
  if sha((ROOT/n).read_bytes())!=d:raise ValueError('host test checkpoint mismatch '+n)
 paths=[ROOT/n for n in ['PxUpdate_V2.2.2.0.6.bin','b8_packaged_qnx.elf','b8_packaging_manifest.json','b8_packaging_validation.json']]
 for p in paths:
  if p.exists():raise FileExistsError('refuse to overwrite '+str(p))
 baseline=ROOT.parent/'b5_packaging_work/voice_b5_2.2.2.0.5.bin';candidate=ROOT/m['candidate_file'];base=baseline.read_bytes();elf=candidate.read_bytes();out=compose(base,elf);report=verify(base,out,elf)
 negative=[]
 for label,bb,ee in [('modified base',base[:-1]+b'\0',elf),('truncated base',base[:-1],elf),('modified ELF',base,elf[:-1]+bytes([elf[-1]^1])),('truncated ELF',base,elf[:-1])]:
  try:compose(bb,ee)
  except ValueError:negative.append(label)
  else:raise ValueError('guard accepted '+label)
 for label,offset in [('wrong revision',7),('bad application checksum',report['records'][0]['trailer_offset']),('modified PIC',report['records'][2]['payload_offset'])]:
  bad=bytearray(out);bad[offset]^=1
  try:verify(base,bytes(bad),elf)
  except ValueError:negative.append(label)
  else:raise ValueError('verifier accepted '+label)
 with paths[0].open('xb') as f:f.write(out)
 saved=paths[0].read_bytes();report=verify(base,saved,elf);q=report['records'][0]
 extracted=saved[q['payload_offset']:q['trailer_offset']]
 with paths[1].open('xb') as f:f.write(extracted)
 if paths[1].read_bytes()!=elf or compose(base,elf)!=saved:raise ValueError('saved package roundtrip mismatch')
 paths[3].write_text(json.dumps(report,indent=2)+'\n')
 manifest={'status':'packaged_offline_validated_hardware_pending','file':paths[0].name,'sha256':sha(saved),'bytes':len(saved),'candidate_sha256':sha(elf),'candidate_bytes':len(elf),'base_file':str(baseline.relative_to(ROOT.parent)),'base_sha256':sha(base),'base_bytes':len(base),'revision':list(VERSION),'application_checksum':report['records'][0]['stored_checksum'],'growth_bytes':len(saved)-len(base),'negative_rejections':negative,'fpga_pic_complete_records_unchanged':True,'deterministic_repack':True,'saved_extraction_sha256':sha(extracted),'flashed':False,'hardware_validated':False,'screen_and_compiled_update_gate_revision':'2.2.2.0.2 inherited unchanged; package identity is header/file .6','source_sha256':{n:sha((ROOT/n).read_bytes()) for n in ['package_b8_candidate.py','verify_b8_package.py']}}
 paths[2].write_text(json.dumps(manifest,indent=2)+'\n')
 if baseline.read_bytes()!=base or candidate.read_bytes()!=elf:raise ValueError('inputs changed during packaging')
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import sys,struct,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;sys.path.insert(0,str(R/'b15_candidate_work'))
from build_candidate_1_8 import parse,serialize,sum16,write_ranges
REV=bytes([2,2,2,1,10]);sha=lambda b:hashlib.sha256(b).hexdigest()
checks=json.loads((O/'validation_results.json').read_text());assert checks['status']=='PASS_EMITTED_TARGETED_HOST_CHECKS'
old=(R/'b15_candidate_work/PxUpdate_V2.2.2.1.9_B15_LFO_fade_candidate.bin').read_bytes();assert sha(old)=='fe1858e1da01aeae69e41799dfbdfb1471f90b0c19d34687663533438f52a2da'
base=parse(old);assert serialize(base)==old
pic=bytearray((O/'pic_2.2.2.1.10_B14_sample_acceleration_candidate.bin').read_bytes());manifest=json.loads((O/'patch_manifest.json').read_text());assert sha(pic)==manifest['candidate_sha256']
assert sha(base[2][1])==manifest['baseline_sha256']
app=bytearray(base[0][1]);assert app[0x1f4e3]==0x19 and app[0x250ef]==9
app[0x1f4e3],app[0x250ef]=0x1a,10
assert [i for i,(a,b) in enumerate(zip(app,base[0][1])) if a!=b]==[0x1f4e3,0x250ef]
rows=[]
for i,p in ((0,bytes(app)),(1,base[1][1]),(2,bytes(pic))):
 h,_,t,_=base[i]
 if i!=1:h=h[:2]+REV+h[7:8]+len(p).to_bytes(4,'big')
 if i==0:t=struct.pack('<H',sum16(p))
 rows.append((h,p,t,0))
package=serialize(rows);ex=parse(package)
assert len(package)==len(old)==3187784 and ex[1]==base[1] and ex[2][2]==b'00'
assert all(int.from_bytes(t,'little')==sum16(p) for h,p,t,_ in ex[:2])
assert ex[0][1]==app and ex[2][1]==pic
# Reuse established .1.9 bounded actual updater/version/checksum checks unchanged.
source=(R/'b15_candidate_work/build_candidate_1_9.py').read_text()
chunk=source[source.index(' # Bounded updater'):source.index(' names=')]
chunk=chunk.replace('0x402a0009','0x402a000a').replace('0x40139219','0x4013921a').replace('[2,2,2,1,8],[2,2,2,1,7]', '[2,2,2,1,9],[2,2,2,1,8],[2,2,2,1,7]')
chunk=chunk.replace(sha(struct.pack('<I',0x40139219)),sha(struct.pack('<I',0x4013921a)))
exec('\n'.join(line[1:] if line.startswith(' ') else line for line in chunk.splitlines()))
name='PxUpdate_V2.2.2.1.10_B14_sample_acceleration_candidate.bin'
files={name:package,'voice_2.2.2.1.10_B14_sample_acceleration_candidate_qnx.elf':app}
for n,b in files.items():
 p=O/n
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
assert parse((O/name).read_bytes())==ex
report=dict(status='PASS_PACKAGE_BYTES_MODELED_UPDATER_CHECKS',version=list(REV),package=name,sha256=sha(package),package_bytes=len(package),PIC_bytes=len(pic),QNX_behavior_unchanged_from_1_9=True,FPGA_record_unchanged=True,version_gate_cases=cases,checksum_blocks=len(blocks),checksum_accept_reject_cases=2*len(blocks),validation=checks,hardware='NOT VERIFIED',flashed=False)
report['diffs']={kind:write_ranges(O/(kind+'_diff.tsv'),a,b,kind,offset,va) for kind,a,b,offset,va in [('PIC',base[2][1],pic,ex[2][3],0x9d000000),('QNX',base[0][1],app,ex[0][3],None),('package',old,package,None,None)]}
(O/'package_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

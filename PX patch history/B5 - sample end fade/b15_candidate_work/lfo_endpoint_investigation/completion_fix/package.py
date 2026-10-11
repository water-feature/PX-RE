from pathlib import Path
import sys,struct,json,hashlib
O=Path(__file__).resolve().parent;R=O.parents[2];sys.path[:0]=[str(R/'b15_candidate_work'),str(R)]
from build_candidate_1_8 import parse,serialize,sum16,write_ranges
sha=lambda b:hashlib.sha256(b).hexdigest();REV=bytes([2,2,2,1,11])
checks=json.loads((O/'validation_results.json').read_text());build=json.loads((O/'build_results.json').read_text());assert checks['status']==build['status']=='PASS'
old=(R/'b14_sample_acceleration_work/PxUpdate_V2.2.2.1.10_B14_sample_acceleration_candidate.bin').read_bytes();assert sha(old)=='6ab00ccd1f9461ffcf5927b54b317d7644c85a3a129dff6115f8cd0cd6a6a6e3'
base=parse(old);assert serialize(base)==old and sha(base[0][1])==build['baseline_sha256']
app=bytearray((O/'fixed_qnx.elf').read_bytes());assert sha(app)==build['candidate_sha256']==checks['tests'][1]['sha256']
app[0x1f4e3],app[0x250ef]=0x1b,11
pic=bytearray(base[2][1])
for off in (0x1394,0x13a0):
 assert struct.unpack_from('<I',pic,off)[0]==0x2484000a;struct.pack_into('<I',pic,off,0x2484000b)
assert [i for i,(a,b) in enumerate(zip(pic,base[2][1])) if a!=b]==[0x1394,0x13a0]
rows=[]
for i,p in [(0,app),(1,base[1][1]),(2,pic)]:
 h,_,t,_=base[i]
 if i!=1:h=h[:2]+REV+h[7:8]+len(p).to_bytes(4,'big')
 if i==0:t=struct.pack('<H',sum16(p))
 rows.append((h,bytes(p),t,0))
package=serialize(rows);ex=parse(package)
assert len(package)==len(old)==3187784 and ex[1]==base[1] and ex[2][2]==b'00'
assert all(int.from_bytes(t,'little')==sum16(p) for h,p,t,_ in ex[:2])
assert ex[0][1]==app and ex[2][1]==pic
fixed=(O/'fixed_qnx.elf').read_bytes();assert [i for i,(a,b) in enumerate(zip(app,fixed)) if a!=b]==[0x1f4e3,0x250ef]
source=(R/'b15_candidate_work/build_candidate_1_9.py').read_text();chunk=source[source.index(' # Bounded updater'):source.index(' names=')]
chunk=chunk.replace('0x402a0009','0x402a000b').replace('0x40139219','0x4013921b').replace('[2,2,2,1,8],[2,2,2,1,7]','[2,2,2,1,10],[2,2,2,1,9]')
exec('\n'.join(line[1:] if line.startswith(' ') else line for line in chunk.splitlines()))
files={'PxUpdate_V2.2.2.1.11_B5_completion_fade_candidate.bin':package,'pic_2.2.2.1.11_B5_completion_fade_candidate.bin':pic,'voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf':app}
for n,b in files.items():
 p=O/n
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
assert parse((O/next(iter(files))).read_bytes())==ex
report=dict(status='PASS_PACKAGE_BYTES_MODELED_UPDATER_CHECKS',version=list(REV),baseline='2.2.2.1.10',package_bytes=len(package),hashes={n:sha(b) for n,b in files.items()},FPGA_record_unchanged=True,PIC_encoder_acceleration_identical=True,PIC_only_version_metadata_changed=True,QNX_packaged_matches_validated_except_version=True,version_gate_cases=cases,checksum_blocks=len(blocks),checksum_accept_reject_cases=len(blocks)*2,fade_ms=5,hardware='NOT VERIFIED',flashed=False)
report['diffs']={kind:write_ranges(O/(kind+'_diff.tsv'),a,b,kind,offset,va) for kind,a,b,offset,va in [('PIC',base[2][1],pic,ex[2][3],0x9d000000),('QNX',base[0][1],app,ex[0][3],None),('package',old,package,None,None)]}
(O/'package_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

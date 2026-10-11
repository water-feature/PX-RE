"""Integrate reviewed stateless producer hook over exact .1.11. No packaging."""
from pathlib import Path
import sys,json,struct,hashlib
O=Path(__file__).resolve().parent;D=O.parent;R=D.parent
sys.path[:0]=[str(R),str(R/'b15_candidate_work')]
from b5_elf_placement_check import ExactElf,decode_index,encode_index
from build_candidate_1_8 import write_ranges
BASE=R/'b15_candidate_work/lfo_endpoint_investigation/completion_fix'
sha=lambda b:hashlib.sha256(b).hexdigest()
QNX=O/'voice_2.2.2.1.12_qnx.elf';PIC=O/'pic_2.2.2.1.12.bin'
def save(p,b):
 if p.exists():assert p.read_bytes()==b,'Refuse different existing artifact: '+str(p)
 else:p.write_bytes(b)
def main():
 # Pin to artifacts from the completed review, not a fresh compiler emission.
 recorded=dict((line.split('  ',1)[1],line.split('  ',1)[0]) for line in (D/'SHA256SUMS').read_text().splitlines())
 for n in ['design_payload.bin','design_frames.bin','measurement.json','design_probe.c','design_thunk.s','design_validation.json']:
  assert sha((D/n).read_bytes())==recorded[n],n
 m=json.loads((D/'measurement.json').read_text());assert m['status']==json.loads((D/'design_validation.json').read_text())['status']=='PASS'
 old=(BASE/'voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf').read_bytes();assert sha(old)==m['baseline_sha256']=='45ee5d94dddb785f0ffa6e3514d42f05671811a669c5f638414d0cd668d66640'
 e=ExactElf(old);out=bytearray(old);allowed=[]
 def put(off,value,reason):
  assert off+len(value)<=len(out);out[off:off+len(value)]=value
  allowed.append(dict(start=off,end=off+len(value),reason=reason))
 assert e.read(0x1a87b,12).hex()=='4183c501488385e0fdffff70'
 assert m['hook']=='e9e8680e0090909090909090'
 assert (m['code_base'],m['code_end'],m['frame_base'],m['frame_end'])==(0x100f60,0x1012bb,0x1024e8,0x1025a4)
 # Exact current B15 sections prove the inherited reservation boundary.
 for name,end in [('.b15_text',0x100f51),('.b15_eh_frame',0x1024e8)]:
  s=e.sections[e.section_names.index(name)];assert s[3]+s[5]==end
 assert m['code_end']<=0x102000 and m['frame_end']<=0x103000
 for lo,hi,n in [(m['code_base'],m['code_end'],'design_payload.bin'),(m['frame_base'],m['frame_end'],'design_frames.bin')]:
  assert e.read(lo,hi-lo)==b'\0'*(hi-lo);payload=(D/n).read_bytes();assert len(payload)==hi-lo
  put(lo,payload,'reviewed '+n)
 put(0x1a87b,bytes.fromhex(m['hook']),'single producer hook; full displaced window')
 h=next(p for p in e.phdr if p['type']==0x6474e550);frame,pairs=decode_index(e.read(h['va'],h['filesz']),h['va'])
 assert h['va']==h['offset']==0x103000 and h['filesz']==h['memsz']==0x1c14 and len(pairs)==897
 new=sorted(pairs+[tuple(p) for p in m['new_FDEs']]);header=encode_index(new,h['va'],frame)
 assert len(header)==0x1c24 and h['va']+len(header)<=0x105000
 put(h['offset'],header,'unwind index: 897 inherited plus two reviewed FDEs')
 i=e.phdr.index(h);put(e.phoff+i*e.phentsize+32,struct.pack('<QQ',len(header),len(header)),'GNU_EH_FRAME file/memory sizes')
 for name,end in [('.b15_text',m['code_end']),('.b15_eh_frame',m['frame_end']),('.eh_frame_hdr',h['va']+len(header))]:
  i=e.section_names.index(name);put(e.shoff+i*e.shentsize+32,struct.pack('<Q',end-e.sections[i][3]),name+' section size')
 assert struct.unpack_from('<I',old,0x1f4e3)[0]==0x4013921b and old[0x250ef]==11
 put(0x1f4e3,b'\x1c','application packed version report: .1.12')
 put(0x250ef,b'\x0c','application updater fifth-field compare: 12')
 changed=[i for i,(a,b) in enumerate(zip(old,out)) if a!=b]
 assert len(out)==len(old) and all(sum(x['start']<=i<x['end'] for x in allowed)==1 for i in changed)
 x=ExactElf(bytes(out));_,xp=decode_index(x.read(h['va'],len(header)),h['va']);assert xp==new
 for pc,f in pairs:assert x.read(f,e.fde(f)['length']+4)==e.read(f,e.fde(f)['length']+4)
 for pc,f in xp:assert x.fde(f)['pc']==pc
 assert all(x.phdr[i]==e.phdr[i] for i in range(e.phnum) if i!=e.phdr.index(h))
 pic0=(BASE/'pic_2.2.2.1.11_B5_completion_fade_candidate.bin').read_bytes();assert sha(pic0)=='2ffb52bec4e399c0cfcc8bd00d27774e22c4b9ea6843afbd4a271a55ce191325'
 pic=bytearray(pic0)
 for off in (0x1394,0x13a0):
  assert struct.unpack_from('<I',pic,off)[0]==0x2484000b;struct.pack_into('<I',pic,off,0x2484000c)
 assert [i for i,(a,b) in enumerate(zip(pic0,pic)) if a!=b]==[0x1394,0x13a0]
 save(QNX,out);save(PIC,pic)
 ph=[struct.unpack_from('<IIQQQQQQ',out,x.phoff+i*x.phentsize) for i in range(x.phnum)]
 report=dict(status='PASS',baseline='2.2.2.1.11',version='2.2.2.1.12',baseline_QNX_sha256=sha(old),QNX_sha256=sha(out),PIC_sha256=sha(pic),QNX_bytes=len(out),PIC_bytes=len(pic),QNX_differing_bytes=len(changed),PIC_differing_bytes=2,allowed_QNX_ranges=allowed,reviewed_code_bytes=859,reviewed_frame_bytes=188,index_growth=16,hook_bytes=12,inherited_FDEs_unchanged=897,total_FDEs=899,image_growth=0,hardware='NOT VERIFIED')
 report['diffs']={'QNX':write_ranges(O/'QNX_diff.tsv',old,out,'QNX',ph=ph),'PIC':write_ranges(O/'PIC_diff.tsv',pic0,pic,'PIC',virtual_base=0x9d000000)}
 (O/'integration.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('allowed_QNX_ranges','diffs')},indent=2))
if __name__=='__main__':main()

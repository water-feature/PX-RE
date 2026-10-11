"""Package the validated .15 image over the exact .12 container."""
from pathlib import Path
import struct as S,json,hashlib
O=Path(__file__).resolve().parent;R=O.parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
REV=bytes([2,2,2,1,15])
def parse(b):
 assert b[:1]==b'\xf0' and b[-1:]==b'\xf7'
 rows=[];off=1
 for i in range(3):
  h=b[off:off+12];n=int.from_bytes(h[8:12],'big');p=b[off+12:off+12+n];t=b[off+12+n:off+14+n]
  assert len(h)==12 and len(p)==n and h[0]==i+1 and h[1]==0x7b and h[7]==0x7a and len(t)==2
  rows.append((h,p,t));off+=n+14
 assert off==len(b)-1
 return rows
def serialize(rows):return b'\xf0'+b''.join(h+p+t for h,p,t in rows)+b'\xf7'
def sum16(b):
 assert len(b)%2==0
 return sum(S.unpack('<'+str(len(b)//2)+'H',b))&65535
def main():
 v=json.loads((O/'validation.json').read_text());assert v['status']=='PASS'
 old=(R/'PxUpdate_V2.2.2.1.12.bin').read_bytes()
 assert sha(old)=='9d0860d06469519a1f80feef2a2143e4a2a343605821f28f193c985398943139'
 base=parse(old);assert serialize(base)==old
 d=R/'b7_lfo_center_investigation/implementation_1_12'
 assert base[0][1]==(d/'voice_2.2.2.1.12_qnx.elf').read_bytes()
 assert base[2][1]==(d/'pic_2.2.2.1.12.bin').read_bytes()
 assert all(base[i][0][2:7]==bytes([2,2,2,1,12]) for i in [0,2])
 app=(O/'voice_2.2.2.1.15_qnx.elf').read_bytes();assert sha(app)==v['QNX_sha256']
 pic=bytearray(base[2][1])
 for off in [0x1394,0x13a0]:
  assert hashlib.sha256(S.pack('<I',S.unpack_from('<I',pic,off)[0])).hexdigest()=='fbf69dbe6517255b0f433dcab0aabf21058364579e2976ab066cbe260773140a';S.pack_into('<I',pic,off,0x2484000f)
 assert [i for i,(a,b) in enumerate(zip(base[2][1],pic)) if a!=b]==[0x1394,0x13a0]
 assert hashlib.sha256(S.pack('<I',S.unpack_from('<I',app,0x1f4e3)[0])).hexdigest()=='7c2065036356b0a1304f121c0d1e8f0444413dd11302da2d440028937a8e0619' and app[0x250ef]==15
 rows=[]
 for i,payload in [(0,app),(1,base[1][1]),(2,bytes(pic))]:
  h,_,tail=base[i]
  if i!=1:h=h[:2]+REV+h[7:8]+len(payload).to_bytes(4,'big')
  if i==0:tail=S.pack('<H',sum16(payload))
  rows.append((h,payload,tail))
 result=serialize(rows);assert len(result)==len(old)
 path=R/'PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin'
 if path.exists():assert path.read_bytes()==result,'Refuse replacing a different candidate'
 else:path.write_bytes(result)
 ex=parse(path.read_bytes());assert serialize(ex)==result and ex==rows
 assert ex[1]==base[1] and ex[2][2]==base[2][2]==b'00'
 for i in [0,1]:assert int.from_bytes(ex[i][2],'little')==sum16(ex[i][1])
 for i in [0,2]:assert ex[i][0][2:7]==REV
 emission=json.loads((O/'emission.json').read_text())
 allowed=[(13+lo,13+hi) for lo,hi,_ in emission['allowed_ranges']]
 allowed += [(13+len(app),15+len(app))]
 record_offsets=[1,1+14+len(app),1+28+len(app)+len(base[1][1])]
 allowed += [(record_offsets[i]+2,record_offsets[i]+7) for i in [0,2]]
 allowed += [(record_offsets[2]+12+off,record_offsets[2]+13+off) for off in [0x1394,0x13a0]]
 changed=[i for i,(a,b) in enumerate(zip(old,result)) if a!=b]
 assert all(any(lo<=i<hi for lo,hi in allowed) for i in changed)
 (O/'reextracted_qnx.elf').write_bytes(ex[0][1]);(O/'reextracted_pic.bin').write_bytes(ex[2][1])
 assert (O/'reextracted_qnx.elf').read_bytes()==app
 assert (O/'reextracted_pic.bin').read_bytes()==bytes(pic)
 files={'../../'+path.name:sha(result),'reextracted_qnx.elf':sha(app),'reextracted_pic.bin':sha(pic)}
 report=dict(status='PASS',version='2.2.2.1.15',baseline='exact 2.2.2.1.12',package=str(path),bytes=len(result),package_sha256=sha(result),QNX_sha256=sha(app),PIC_sha256=sha(pic),FPGA_sha256=sha(ex[1][1]),application_checksum=ex[0][2].hex(),FPGA_checksum=ex[1][2].hex(),PIC_legacy_trailer=ex[2][2].hex(),PIC_only_two_revision_bytes=True,FPGA_entire_record_unchanged=True,reextraction_identical=True,flashed=False)
 report.update(all_package_differences_accounted=True,package_differing_bytes=len(changed))
 (O/'package_results.json').write_text(json.dumps(report,indent=2)+'\n')
 (O/'SHA256SUMS').write_text(''.join(f'{value}  {name}\n' for name,value in files.items()))
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()

# SPDX-License-Identifier: GPL-2.0-or-later
"""Independently parse a saved update and compare all payloads to tested files."""
from pathlib import Path
import argparse,hashlib,json,struct
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('package',type=Path,nargs='?',default=ROOT/'candidate_update.bin');args=ap.parse_args()
data=args.package.read_bytes();baseline=(ROOT.parent.parent/'upload/PxUpdate_V2.2.2.1.2.bin').read_bytes()
assert data[0]==0xf0 and data[-1]==0xf7;assert len(data)==len(baseline)==3151848
pos=1;records=[]
for typ,name,rev in [(1,'qnx',[2,2,2,1,3]),(2,'fpga',[0,0,0,1,0]),(3,'pic',[2,2,2,1,2])]:
 start=pos;assert data[pos]==typ and data[pos+1]==0x7b and data[pos+7]==0x7a
 revision=list(data[pos+2:pos+7]);assert revision==rev
 length=int.from_bytes(data[pos+8:pos+12],'big');pos+=12;payload=data[pos:pos+length];assert len(payload)==length;pos+=length
 trailer=data[pos:pos+2];assert len(trailer)==2;pos+=2
 if typ in (1,2):
  checksum=0
  for i in range(0,len(payload)-1,2):checksum=(checksum+payload[i]+256*payload[i+1])&0xffff
  assert trailer==checksum.to_bytes(2,'little')
 else:assert trailer==bytes([0x30,0x30])
 expected=(ROOT/('candidate_qnx.elf' if typ==1 else 'baseline_'+name+'.bin')).read_bytes();assert payload==expected
 if typ!=1:assert data[start:pos]==baseline[start:pos]
 out=ROOT/('reextracted_'+name+('.elf' if typ==1 else '.bin'));out.write_bytes(payload)
 records.append({'type':typ,'component':name,'revision':revision,'bytes':length,'sha256':hashlib.sha256(payload).hexdigest(),'trailer':trailer.hex(),'full_record_preserved':typ!=1})
assert pos==len(data)-1
qnx=(ROOT/'reextracted_qnx.elf').read_bytes()
assert qnx[0x250e2]==1 and qnx[0x250ef]==3
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',qnx,0x1f4e3)[0])).hexdigest()=='b1ae5aaffaea01df2e07e8e6425951612a8dbc42ecb887c8238e2dff52979fb0'
assert qnx[0x3527c]==0xe8 and 0x35281+struct.unpack_from('<i',qnx,0x3527d)[0]==0xf9240
receipt=json.loads((ROOT/'package_build_manifest.json').read_text());allowed=receipt['allowed_qnx_difference_spans']
original=(ROOT/'baseline_qnx.elf').read_bytes()
assert all(any(a<=i<z for a,z in allowed) for i,(a,b) in enumerate(zip(original,qnx)) if a!=b)
changes=[i for i,(a,b) in enumerate(zip(baseline,data)) if a!=b]
assert len(changes)==461
assert all(i==7 or 13+len(qnx)<=i<15+len(qnx) or any(13+a<=i<13+z for a,z in allowed) for i in changes)
assert hashlib.sha256(data).hexdigest()==receipt['candidate_package_sha256']
print(json.dumps({'package':str(args.package),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'records':records,'all_changed_bytes_accounted_for':True,'format_and_checksums':'pass','reextracted_payloads_match':'pass','version_operands':'pass','hardware_tested':False},indent=2))

#!/usr/bin/env python3
"""Stock-pinned voice-fade baseline -> combined offline candidate."""
from pathlib import Path
import hashlib,json,struct,sys
source,destination=map(Path,sys.argv[1:])
raw=source.read_bytes()
assert len(raw)==3099064
assert hashlib.sha256(raw).hexdigest()=='f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898'
if destination.exists():raise SystemExit('Refusing to overwrite an existing output')
pos=1;records=[]
assert raw[0]==0xf0
while raw[pos]!=0xf7:
 start=pos;kind=raw[pos];assert raw[pos+1]==0x7b
 version=list(raw[pos+2:pos+7]);assert raw[pos+7]==0x7a
 length=int.from_bytes(raw[pos+8:pos+12],'big');payload=pos+12
 records.append({'kind':kind,'header':start,'version':version,'payload':payload,'length':length,'trailer':payload+length})
 pos=payload+length+2
assert pos==len(raw)-1 and [r['kind'] for r in records]==[1,2,3]
assert [r['length'] for r in records]==[986520,1581716,530784]
assert records[2]['payload']==0x273055 and records[2]['version']==[2,2,2,0,0]
def checksum(data):return sum(data[i]+(data[i+1]<<8) for i in range(0,len(data),2))&65535
for r in records[:2]:assert checksum(raw[r['payload']:r['payload']+r['length']])==int.from_bytes(raw[r['trailer']:r['trailer']+2],'little')
assert raw[-3:]==b'00\xf7'
pic_offset=records[2]['payload'];patched=bytearray(raw)
changes={0x295b0:(0x0f417b93,0x0b400480),
 0x1200:(0xffffffff,0x90a30005),0x1204:(0xffffffff,0x386300f0),
 0x1208:(0xffffffff,0x10600003),0x120c:(0xffffffff,0x00001021),
 0x1210:(0xffffffff,0x0f417b93),0x1214:(0xffffffff,0x90a40004),
 0x1218:(0xffffffff,0x0b40a56e),0x121c:(0xffffffff,0),
 0x258b4:(0x24842220,0x24842221),0x51bc4:(0x24842220,0x24842221)}
for offset,(old,new) in changes.items():
 assert struct.unpack_from('<I',raw,pic_offset+offset)[0]==old
 struct.pack_into('<I',patched,pic_offset+offset,new)
pic_version_offset=records[2]['header']+5
assert raw[pic_version_offset]==0
patched[pic_version_offset]=1
allowed={pic_version_offset}
for offset in changes:allowed.update(range(pic_offset+offset,pic_offset+offset+4))
diff=[i for i,(a,b) in enumerate(zip(raw,patched)) if a!=b]
assert set(diff)<=allowed and len(diff)==39
assert patched[:records[2]['header']]==raw[:records[2]['header']]
assert patched[-3:]==raw[-3:]
pic=patched[pic_offset:pic_offset+530784]
assert hashlib.sha256(pic).hexdigest()=='2f746346fa1e592795fd243a9866a8019e69c2d97ab3d674204bb7f5022ef0cc'
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_bytes(patched)
manifest={'file_name':destination.name,'file_bytes':len(patched),'sha256':hashlib.sha256(patched).hexdigest(),
 'baseline_voice_fade_sha256':hashlib.sha256(raw).hexdigest(),
 'app_header_version':[2,2,2,0,1],'app_checksum':'0xF14B','pic_header_and_reported_version':[2,2,2,1,0],
 'pic_payload_sha256':hashlib.sha256(pic).hexdigest(),'pic_container_trailer':'0x3030 (preserved; consumed without validation by inspected type3 parser)',
 'changed_bytes_relative_to_voice_fade':len(diff),'changed_raw_offsets':[hex(i) for i in diff],
 'pic_instruction_changes':{hex(0x9d000000+o):{'old':hex(a),'new':hex(b)} for o,(a,b) in changes.items()},
 'qnx_and_fpga_records_identical':True,'hardware_tested':False,
 'scope':'offline candidate; receiver queue/serial-flash programming and unseen internal copier not hardware validated'}
destination.with_name('manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k not in ['changed_raw_offsets','pic_instruction_changes']},indent=2))

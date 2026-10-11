"""Independent delivered-byte, metadata and receiver-checksum verification."""
from pathlib import Path
import hashlib,struct,json,sys
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));import b7_combined_instruction_model as m
sha=lambda b:hashlib.sha256(b).hexdigest()
def parse(b):
 assert b[0]==0xf0 and b[-1]==0xf7
 p=1;rows=[]
 for typ in (1,2,3):
  h=b[p:p+12];assert h[:2]==bytes((typ,0x7b)) and h[7]==0x7a
  n=int.from_bytes(h[8:12],'big');rows.append({'header':h,'payload':b[p+12:p+12+n],'trailer':b[p+12+n:p+14+n],'header_offset':p,'payload_offset':p+12,'length':n});p+=14+n
 assert p==len(b)-1
 return rows
base=(ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes();assert sha(base)=='c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f'
path=Path(sys.argv[1]) if len(sys.argv)>1 else OUT/'package_pending_validation.bin'
new=path.read_bytes();o,n=parse(base),parse(new);assert len(new)==len(base)==3151848
assert n[1]==o[1]
for i in (0,1):assert int.from_bytes(n[i]['trailer'],'little')==sum(struct.unpack('<'+'H'*(len(n[i]['payload'])//2),n[i]['payload']))&65535
assert n[2]['trailer']==o[2]['trailer']==b'00'
assert all(n[i]['length']==o[i]['length'] for i in range(3))
for i in (0,2):
 assert list(n[i]['header'][2:7])==[2,2,2,0,9]
 expected_header=bytearray(o[i]['header']);expected_header[2:7]=bytes((2,2,2,0,9))
 assert n[i]['header']==bytes(expected_header)
app,pic=n[0]['payload'],n[2]['payload']
assert app==(OUT/'voice_2.2.2.0.9_qnx.elf').read_bytes() and pic==(OUT/'pic_2.2.2.0.9.bin').read_bytes()
assert [i for i,(a,b) in enumerate(zip(o[0]['payload'],app)) if a!=b]==[0x1f4e3,0x250ef]
manifest=json.loads((OUT/'b6_patch_manifest.json').read_text());allowed=set()
for a,item in manifest['PIC'].items():
 off=int(a,16)-m.BASE
 assert o[2]['payload'][off:off+4].hex()==item['old_bytes'] and pic[off:off+4].hex()==item['new_bytes']
 allowed.update(range(off,off+4))
assert all(i in allowed for i,(a,b) in enumerate(zip(o[2]['payload'],pic)) if a!=b)
assert pic[0x1200:0x1224]==o[2]['payload'][0x1200:0x1224]
assert pic[0x1228:0x1394]==o[2]['payload'][0x1228:0x1394]
assert pic[0x1480:0x1a84c]==o[2]['payload'][0x1480:0x1a84c]
# Reuse actual x86 gate decoder, with candidate arrays bound independently.
s=(ROOT/'b7_candidate_work/validate_version_gates.py').read_text();start=s.index('def gate(');end=s.index('\napp_cases=');ns={'app':app,'pic':pic,'struct':struct}
exec(s[start:end],ns);gate=ns['gate']
app_cases=[]
for incoming in ([2,2,2,0,x] for x in (0,7,8,9)):
 skip=not bool(gate('app',incoming).get(0x373c,0));assert skip==(incoming==[2,2,2,0,9]);app_cases.append({'incoming':incoming,'skip':skip})
pic_cases=[]
for installed in ([2,2,4,0,0],[2,2,2,0,8],[2,2,2,0,9]):
 skip=bool(gate('pic',[2,2,2,0,9],installed).get(0x3744,0));assert skip==(installed==[2,2,2,0,9]);pic_cases.append({'installed':installed,'skip':skip})
for i in range(5):
 incoming=[2,2,2,0,9];incoming[i]^=1;assert not gate('pic',incoming,[2,2,2,0,9]).get(0x3744,0)
assert app[0x1f4dd:0x1f4e3]==bytes.fromhex('c78540f9ffff')
reply=struct.unpack_from('<I',app,0x1f4e3)[0];assert reply==0x40139209
assert [(reply&65535)>>14,(reply>>11)&7,(reply>>8)&7,(reply>>4)&15,reply&15]==[2,2,2,0,9]
for off in (0x258b4,0x51bc4):assert struct.unpack_from('<I',pic,off)[0]==0x24842220
assert struct.unpack_from('<I',pic,0x52fec)[0]==0x24020002
# Inspect actual two fifth-field report thunks and inherited LUI slots.
for site,thunk,target in [(0x258c0,0x1394,0x9d075c1c),(0x51bc8,0x13a0,0x9d075b18)]:
 assert struct.unpack_from('<I',pic,site)[0]==(3<<26)|(((m.BASE+thunk)>>2)&0x3ffffff)
 assert struct.unpack_from('<I',pic,site+4)[0]==0x3c04402a
 assert struct.unpack_from('<III',pic,thunk)==(0x24840009,(2<<26)|((target>>2)&0x3ffffff),0)
m.IMAGE=pic;machine=m.Machine([(0,999,499,0)]*2,0,0,0);machine.set('gp',0x80007ff0);gp=machine.get('gp')
blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)]
assert len(blocks)==130 and len(blocks[-1])==2400
for b in blocks:
 machine.write(gp-0x7f20,0,4)
 pcs=range(0x9d044484,0x9d04449c,4) if len(b)==4096 else range(0x9d04466c,0x9d044684,4)
 for low,high in zip(b[::2],b[1::2]):
  machine.write(gp-0x7f1c,low,4);machine.set('v0',high)
  for pc in pcs:machine.simple(m.decode(pc))
 expected=sum(struct.unpack('<'+'H'*(len(b)//2),b))&65535;assert machine.read(gp-0x7f20,2)==expected
 for incoming in (expected,expected^1):
  machine.set('v0',incoming&255);machine.set('a1',incoming>>8);machine.set('v1',expected)
  for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):machine.simple(m.decode(pc))
  assert m.decode(0x9d0444fc)==('beq','v0','v1',0x9d0446e8)
  assert (machine.get('v0')==machine.get('v1'))==(incoming==expected)
  machine.simple(m.decode(0x9d044500))
# Whole-package contiguous old/new-byte manifest, including checksums/headers.
runs=[];i=0
while i<len(base):
 if base[i]==new[i]:i+=1;continue
 a=i
 while i<len(base) and base[i]!=new[i]:i+=1
 runs.append({'offset':hex(a),'old':base[a:i].hex(),'new':new[a:i].hex()})
(OUT/'b6_package_byte_manifest.json').write_text(json.dumps(runs,indent=2)+'\n')
for idx,name in [(0,'reextracted_qnx.elf'),(2,'reextracted_pic.bin')]:
 (OUT/name).write_bytes(n[idx]['payload'])
 assert (OUT/name).read_bytes()==n[idx]['payload']
result={'status':'PASS','file':path.name,'package_sha256':sha(new),'package_bytes':len(new),'baseline_sha256':sha(base),'PIC_sha256':sha(pic),'QNX_sha256':sha(app),'record_lengths':[r['length'] for r in n],'application_checksum':n[0]['trailer'].hex(),'FPGA_checksum':n[1]['trailer'].hex(),'PIC_trailer':n[2]['trailer'].hex(),'revision':[2,2,2,0,9],'PIC_and_application_headers_reports_gates_match':True,'application_gate_cases':app_cases,'PIC_gate_cases':pic_cases,'all_five_PIC_fields_compared':True,'QNX_version_only_changes':True,'FPGA_record_unchanged':True,'all_inherited_PIC_bytes_preserved_except_approved_hook_and_versions':True,'transport_checksum_blocks':130,'valid_corrupt_checksum_comparisons':260,'reextraction_matches_candidates':True,'hardware_tested':False,'flashed':False,'limitations':'External engine/MIDI calls summarized; full USB/updater installation and hardware/audio not emulated.'}
(OUT/'b6_packaged_validation_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

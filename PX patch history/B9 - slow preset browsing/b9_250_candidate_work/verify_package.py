"""Independent reread/re-extraction/checksum/update-gate and every-byte audit.
Does not publish until validation completes. No builder parser/assembler imported.
"""
from pathlib import Path
import hashlib,struct,json,sys
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT));from mips_check import CPU,GP,BASE,decode
sha=lambda b:hashlib.sha256(b).hexdigest()
REV=[2,2,2,1,2];NAME='PxUpdate_V2.2.2.1.2.bin'
def parse(b):
 assert b[:1]==b'\xf0' and b[-1:]==b'\xf7'
 p=1;rows=[]
 while p<len(b)-1:
  h=b[p:p+12];assert len(h)==12 and h[1]==0x7b and h[7]==0x7a
  length=struct.unpack_from('>I',h,8)[0];end=p+12+length
  assert end+2<len(b)
  rows.append({'type':h[0],'header':h,'revision':list(h[2:7]),'payload':b[p+12:end],'trailer':b[end:end+2],'header_offset':p,'payload_offset':p+12,'trailer_offset':end,'length':length})
  p=end+2
 assert p==len(b)-1 and [r['type'] for r in rows]==[1,2,3]
 return rows
old=(ROOT/'PxUpdate_V2.2.2.0.9.bin').read_bytes();assert sha(old)=='438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d'
path=Path(sys.argv[1]) if len(sys.argv)>1 else OUT/'package_pending_validation.bin'
new=path.read_bytes();a,b=parse(old),parse(new)
assert len(new)==len(old)==3151848
assert [r['length'] for r in b]==[1039304,1581716,530784]
assert b[1]==a[1] # includes offsets/header/payload/trailer
for idx in (0,1):
 calculated=sum(struct.unpack('<'+'H'*(b[idx]['length']//2),b[idx]['payload']))&65535
 assert b[idx]['trailer']==struct.pack('<H',calculated)
assert b[2]['trailer']==a[2]['trailer']==bytes.fromhex('3030')
for idx in (0,2):
 h=bytearray(a[idx]['header']);h[2:7]=bytes(REV);assert b[idx]['header']==h and b[idx]['revision']==REV
pic,app=b[2]['payload'],b[0]['payload'];pic0,app0=a[2]['payload'],a[0]['payload']
assert pic==(OUT/'pic_2.2.2.1.2.bin').read_bytes() and app==(OUT/'voice_2.2.2.1.2_qnx.elf').read_bytes()
assert [i for i,(x,y) in enumerate(zip(app0,app)) if x!=y]==[0x1f4e3,0x250e2,0x250ef]
# Literal expected hook + metadata and allowlisted PIC byte regions, independent of manifest.
assert struct.unpack_from('<I',pic,0x23550)[0]==0x0b400361
assert struct.unpack_from('<I',pic,0x235e4)[0]==0x0b400364
assert pic[0x235e8:0x235ec]==pic0[0x235e8:0x235ec]==bytes.fromhex('21807002')
assert pic[0x23554:0x23558]==pic0[0x23554:0x23558]==bytes.fromhex('f4010224')
assert pic0[0xd84:0xe00]==b'\xff'*124 and pic[0xdf4:0xe00]==b'\xff'*12
for off in (0x258b4,0x51bc4):assert struct.unpack_from('<I',pic,off)[0]==0x24842221
for off in (0x1394,0x13a0):assert struct.unpack_from('<I',pic,off)[0]==0x24840002
allowed=set(range(0xd84,0xdf4))|set(range(0x23550,0x23554))|set(range(0x235e4,0x235e8))
for off in (0x258b4,0x51bc4,0x1394,0x13a0):allowed.update(range(off,off+4))
picdiff=[i for i,(x,y) in enumerate(zip(pic0,pic)) if x!=y]
assert set(picdiff)<=allowed
# Inherited B6/B7/B3, vector/startup/DINIT/display/application ranges unchanged.
protected=[(0,0xd84),(0xdf4,0x1394),(0x1398,0x13a0),(0x13a4,0x23550),(0x23554,0x235e4),(0x235e8,0x258b4),(0x258b8,0x51bc4),(0x51bc8,len(pic))]
assert all(pic[x:z]==pic0[x:z] for x,z in protected)
assert struct.unpack_from('<II',pic,0x1224)==struct.unpack_from('<II',pic0,0x1224)
assert pic[0xc00:0xd84]==pic0[0xc00:0xd84]
assert pic[0x1200:0x1224]==pic0[0x1200:0x1224] and pic[0x295b0:0x295b8]==pic0[0x295b0:0x295b8]
assert pic[0x52fe4:0x52ff8]==pic0[0x52fe4:0x52ff8]
for site,thunk,target in [(0x258c0,0x1394,0x9d075c1c),(0x51bc8,0x13a0,0x9d075b18)]:
 assert pic[site:site+8]==pic0[site:site+8]
 assert struct.unpack_from('<III',pic,thunk)==(0x24840002,(2<<26)|((target>>2)&0x3ffffff),0)
 # Execute actual version JAL, inherited LUI slot, thunk ADDIU/J + NOP.
 m=CPU(pic);m.run(BASE+site,{target});assert m.g('a0')==0x402a0002 and m.g('ra')==BASE+site+8
for off in (0x258b4,0x51bc4):
 m=CPU(pic);m.s('a0',0x40290000);m.fetch_simple(BASE+off);assert m.g('a0')==0x40292221
assert struct.unpack_from('<I',pic,0x52fec)[0]==0x24020002 # M:2.2.2, established three-field convention.
assert app[0x1f4dd:0x1f4e3]==bytes.fromhex('c78540f9ffff')
reply=struct.unpack_from('<I',app,0x1f4e3)[0];assert reply==0x40139212
assert [(reply&65535)>>14,(reply>>11)&7,(reply>>8)&7,(reply>>4)&15,reply&15]==REV
# Independent existing actual-x86 decoder, no top-level validator/build code executed.
s=(ROOT/'b7_candidate_work/validate_version_gates.py').read_text();start=s.index('def gate(');end=s.index('\napp_cases=')
ns={'app':app,'pic':pic,'struct':struct};exec(s[start:end],ns);gate=ns['gate']
gates=[]
for compiled,image in [('B6 .9',app0),('B9 .1.1',app)]:
 ns['app']=image
 for incoming in ([2,2,2,0,9],REV,[2,2,2,1,1],[2,2,2,1,0],[2,2,2,0,0]):
  compiledrev=[2,2,2,0,9] if compiled=='B6 .9' else REV
  skip=not bool(gate('app',incoming).get(0x373c,0));assert skip==(incoming==compiledrev)
  gates.append({'kind':'application','compiled':compiled,'incoming':incoming,'skip':skip})
ns['app']=app
for installed in ([2,2,2,0,9],REV,[2,2,2,1,1],[2,2,2,1,0],[2,2,2,0,0]):
 skip=bool(gate('pic',REV,installed).get(0x3744,0));assert skip==(installed==REV)
 gates.append({'kind':'PIC','installed':installed,'incoming':REV,'skip':skip})
for i in range(5):
 incoming=REV.copy();incoming[i]^=1
 assert gate('app',incoming).get(0x373c,0) and not gate('pic',incoming,REV).get(0x3744,0)
# Exact candidate transport checksum arithmetic and received-checksum comparison.
m=CPU(pic);blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)];assert len(blocks)==130 and len(blocks[-1])==2400
for block in blocks:
 m.write(GP-0x7f20,0,4)
 pcs=range(0x9d044484,0x9d04449c,4) if len(block)==4096 else range(0x9d04466c,0x9d044684,4)
 for low,high in zip(block[::2],block[1::2]):
  m.write(GP-0x7f1c,low,4);m.s('v0',high)
  for pc in pcs:m.simple(decode(pic,pc))
 expected=sum(struct.unpack('<'+'H'*(len(block)//2),block))&65535
 assert m.read(GP-0x7f20,2)==expected
 for incoming in (expected,expected^1):
  m.s('v0',incoming&255);m.s('a1',incoming>>8);m.s('v1',expected)
  for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):m.simple(decode(pic,pc))
  assert decode(pic,0x9d0444fc)==('beq','v0','v1',0x9d0446e8)
  assert (m.g('v0')==m.g('v1'))==(incoming==expected)
  m.simple(decode(pic,0x9d044500))
# Every package difference must belong to approved payload/header/checksum edits.
package_allowed=set()
for idx in (0,2):package_allowed.update(range(b[idx]['header_offset']+2,b[idx]['header_offset']+7))
package_allowed.update(b[2]['payload_offset']+i for i in allowed)
package_allowed.update(b[0]['payload_offset']+i for i in (0x1f4e3,0x250e2,0x250ef))
package_allowed.update(range(b[0]['trailer_offset'],b[0]['trailer_offset']+2))
diffs=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y];assert set(diffs)<=package_allowed
runs=[];i=0
while i<len(old):
 if old[i]==new[i]:i+=1;continue
 lo=i
 while i<len(old) and old[i]!=new[i]:i+=1
 runs.append({'offset':hex(lo),'old_bytes':old[lo:i].hex(),'new_bytes':new[lo:i].hex()})
(OUT/'b9_package_byte_manifest.json').write_text(json.dumps(runs,indent=2)+'\n')
for idx,name in [(0,'reextracted_qnx.elf'),(1,'reextracted_fpga.bin'),(2,'reextracted_pic.bin')]:
 (OUT/name).write_bytes(b[idx]['payload']);assert (OUT/name).read_bytes()==b[idx]['payload']
manifest=json.loads((OUT/'b9_patch_manifest.json').read_text())
assert sha(new)==manifest['candidate_package_sha256'] and sha(pic)==manifest['candidate_PIC_sha256'] and sha(app)==manifest['candidate_QNX_sha256']
inst=json.loads((OUT/'b9_instruction_validation.json').read_text());assert inst['status']=='PASS'
result={'status':'PASS','source_package':str(path),'published_filename':NAME,'revision':REV,'package_sha256':sha(new),'package_bytes':len(new),'baseline_package_sha256':sha(old),'PIC_sha256':sha(pic),'QNX_sha256':sha(app),'FPGA_sha256':sha(b[1]['payload']),'record_lengths':[r['length'] for r in b],'application_checksum':hex(int.from_bytes(b[0]['trailer'],'little')),'FPGA_checksum':hex(int.from_bytes(b[1]['trailer'],'little')),'PIC_inherited_container_trailer':b[2]['trailer'].hex(),'changed_PIC_bytes':len(picdiff),'changed_QNX_bytes':3,'changed_package_bytes':len(diffs),'FPGA_record_unchanged':True,'no_payload_or_package_growth':True,'M_display':'2.2.2','DSP_display':'2.2.2.1.2','PIC_report':'2.2.2.1.2','actual_updater_gate_cases':gates,'all_five_version_components_compared':True,'PIC_transport_blocks':130,'valid_corrupt_checksum_comparisons':260,'every_changed_byte_accounted':True,'reextraction_matches_candidates':True,'B6_and_inherited_ranges_preserved':True,'hardware_tested':False,'flashed':False,'limits':'Offline format/actual-gate/transport arithmetic verification; USB media recognition, installation, display delivery, sound and physical stack behavior require hardware.'}
(OUT/'b9_packaged_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

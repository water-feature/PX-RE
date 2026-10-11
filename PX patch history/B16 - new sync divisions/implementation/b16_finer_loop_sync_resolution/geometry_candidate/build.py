"""B16 geometry-only .2.2 from exact pinned .2.1; no hardware actions."""
from pathlib import Path
import struct,sys,json,hashlib,runpy
D=Path(__file__).resolve().parent;B=D.parent;R=B.parent;O=B/'in_place_candidate';BASE=0x9d000000
sys.path.insert(0,str(B/'offline_candidate'));v=runpy.run_path(str(B/'offline_candidate/validate.py'));helpers=runpy.run_path(str(B/'offline_candidate/build.py'))
sha=lambda x:hashlib.sha256(x).hexdigest();parse=helpers['parsepkg'];changes=helpers['changes'];checksum=lambda x:sum(int.from_bytes(x[i:i+2],'little') for i in range(0,len(x),2))&65535
from validate_geometry import validate
NAME='PxUpdate_V2.2.2.2.2_B16_geometry_candidate.bin';REV=bytes([2,2,2,2,2]);OLD=bytes([2,2,2,2,1])
def put(name,data):
 with (D/name).open('xb') as f:f.write(data)
def diff(name,a,z,base=0):
 ds=changes(a,z);put(name,('offset\taddress\told\tnew\n'+''.join(f'{i:#x}\t{base+i:#x}\t{a[i]:02x}\t{z[i]:02x}\n' for i in ds)).encode());return ds
pic=(O/'pic_2.2.2.2.1_B16_in_place.bin').read_bytes();qnx=(O/'voice_2.2.2.2.1_B16_in_place_qnx.elf').read_bytes();pkg=(O/'PxUpdate_V2.2.2.2.1_B16_in_place_candidate.bin').read_bytes()
pins={'PIC':'b7d59c09d57e2b9c18146e51b517404a8deba5cfcc5291d8a17f88904fe53e59','QNX':'34b775ebff3af113ffa12592e71f51136037a64fdb50a6810c11b62c008b5fa2','package':'0d41efe3fcd93d16161e92ae4b9389d7d0917006a06920b7f2c8b8660e419e74'}
assert [sha(x) for x in (pic,qnx,pkg)]==list(pins.values())
rows=parse(pkg);assert rows[0][1]==qnx and rows[2][1]==pic
wordsource=(B/'geometry_review/proposed_words.tsv').read_text();verification=(B/'geometry_review/PROPOSED_ASSEMBLY_CHECK.txt').read_text();assert 'PASS: 33 exact assembly matches' in verification
words={int(a,16):int(w,16) for a,w,*_ in (line.split('\t') for line in wordsource.splitlines())};assert len(words)==33
for a,w in words.items():assert f'{a:08x}\t{w:08x}\t' in verification
put('emitted_words.tsv',wordsource.encode());put('INDEPENDENT_WORD_VERIFICATION.txt',verification.encode())
out=bytearray(pic)
for a,w in words.items():struct.pack_into('<I',out,a-BASE,w)
functional_pic=bytes(out);scope=set(range(0x3b0a0,0x3b104))|set(range(0x3b55c,0x3b57c));assert set(changes(pic,out))<=scope
pd=diff('PIC_geometry_diff.tsv',pic,out,BASE)
# Established fifth-component version procedure, tracked separately.
for off in (0x1394,0x13a0):assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',out,off)[0])).hexdigest()=='43c9216e9b9aa559a72fb2004d7cbc68a7c33dac592e2fc4106773e82d6ac63a';struct.pack_into('<I',out,off,0x24840002)
app=bytearray(qnx);assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',app,0x1f4e3)[0])).hexdigest()=='4a0aefa53435f484d5226e276f88b606a75f151dd1a996eca61e534783315686';struct.pack_into('<I',app,0x1f4e3,0x40139222)
assert hashlib.sha256(app[0x250e9:0x250f0]).hexdigest()=='769897966c9cc4178ab1bd456723be37a4812f95c84db19e15087e0deb3cb2e6';app[0x250ef]=2
assert set(changes(functional_pic,out))=={0x1394,0x13a0};assert set(changes(qnx,app))=={0x1f4e3,0x250ef}
diff('PIC_version_diff.tsv',functional_pic,out,BASE);diff('QNX_version_diff.tsv',qnx,app,0x100000)
assert set(changes(pic,out))<=scope|{0x1394,0x13a0}
assert out[0xe00:0x1000]==pic[0xe00:0x1000] and out[:0x1000]==pic[:0x1000]
assert out[0x3b57c:0x3b5b0]==pic[0x3b57c:0x3b5b0]
for a,w in words.items():assert struct.unpack_from('<I',out,a-BASE)[0]==w
# Both actual report thunks, compiled QNX report and update gates.
reports=[]
for site,target in ((0x258c0,BASE+0x75c1c),(0x51bc8,BASE+0x75b18)):
 c=v['CPU'](out);c.run(BASE+site,target);assert c.r[4]==0x402a0002 and c.r[31]==BASE+site+8;reports.append({'site':hex(BASE+site),'wire_word':hex(c.r[4])})
reply=struct.unpack_from('<I',app,0x1f4e3)[0];packed=reply&65535;decoded=[packed>>14,packed>>11&7,packed>>8&7,packed>>4&15,packed&15];assert decoded==list(REV)
src=(R/'b7_candidate_work/validate_version_gates.py').read_text();gn={'app':app,'struct':struct};exec(src[src.index('def gate('):src.index('\napp_cases=')],gn)
versions=[list(OLD),list(REV),[2,2,2,2,0],[2,2,2,2,3],[2,2,2,1,15]]
for i in range(5):
 z=list(REV);z[i]^=1
 if z not in versions:versions.append(z)
for incoming in versions:assert (not bool(gn['gate']('app',incoming).get(0x373c,0)))==(incoming==list(REV))
for installed in versions:assert bool(gn['gate']('pic',list(REV),installed).get(0x3744,0))==(installed==list(REV))
# Test actual emitted bytes, never the word overlay.
geometry=validate(bytes(out));put('geometry_results.json',(json.dumps(geometry,indent=2)+'\n').encode())
# Receiver checksum arithmetic including the new geometry/version bytes.
blocks=[out[i:i+4096] for i in range(0,len(out),4096)];c=v['CPU'](out);gp=0x80007ff0;c.r[28]=gp
for block in blocks:
 c.write(gp-0x7f20,4,0);pcs=range(BASE+0x44484,BASE+0x4449c,4) if len(block)==4096 else range(BASE+0x4466c,BASE+0x44684,4)
 for low,high in zip(block[::2],block[1::2]):
  c.write(gp-0x7f1c,4,low);c.r[2]=high
  for pc in pcs:c.plain(c.read(pc,4))
 expected=checksum(block);assert c.read(gp-0x7f20,2)==expected
 for incoming in (expected,expected^1):
  c.r[2]=incoming&255;c.r[5]=incoming>>8;c.r[3]=expected
  for pc in (BASE+0x444f0,BASE+0x444f4,BASE+0x444f8):c.plain(c.read(pc,4))
  assert (c.r[2]==c.r[3])==(incoming==expected)
# Package remains same layout, three same-length records; FPGA record untouched.
pieces=[]
for i,payload in enumerate((app,rows[1][1],out)):
 h=bytearray(rows[i][0]);assert len(payload)==len(rows[i][1])
 if i in (0,2):assert h[2:7]==OLD;h[2:7]=REV
 trailer=struct.pack('<H',checksum(payload)) if i==0 else rows[i][2];pieces.append(bytes(h)+payload+trailer)
package=b'\xf0'+b''.join(pieces)+b'\xf7';assert len(package)==len(pkg)==3187784
put('package_pending_validation.bin',package);saved=(D/'package_pending_validation.bin').read_bytes();ex=parse(saved)
assert ex[0][1]==app and ex[2][1]==out and ex[1]==rows[1]
for i in (0,1):assert ex[i][2]==struct.pack('<H',checksum(ex[i][1]))
assert ex[2][2]==rows[2][2]==b'00'
for i in range(3):assert ex[i][3:]==rows[i][3:]
for i in (0,2):assert ex[i][0][2:7]==REV
allowed={ex[0][4]+o for o in (0x1f4e3,0x250ef)}|{ex[2][4]+o for o in changes(pic,out)}|{ex[i][3]+6 for i in (0,2)}|{ex[0][5],ex[0][5]+1}
assert set(changes(pkg,saved))<=allowed
pkgdiff=diff('package_vs_2_2_2_2_1_diff.tsv',pkg,saved);diff('PIC_all_diff.tsv',pic,out,BASE)
# Saved components and final file must re-read identically before declaring PASS.
put('pic_2.2.2.2.2_B16_geometry.bin',out);put('voice_2.2.2.2.2_B16_geometry_qnx.elf',app)
assert (D/'pic_2.2.2.2.2_B16_geometry.bin').read_bytes()==ex[2][1]
assert (D/'voice_2.2.2.2.2_B16_geometry_qnx.elf').read_bytes()==ex[0][1]
assert [sha((O/n).read_bytes()) for n in ('pic_2.2.2.2.1_B16_in_place.bin','voice_2.2.2.2.1_B16_in_place_qnx.elf','PxUpdate_V2.2.2.2.1_B16_in_place_candidate.bin')]==list(pins.values())
put(NAME,saved);assert (D/NAME).read_bytes()==saved
result={'status':'PASS: offline validation; hardware pending; B16 not complete','version':decoded,'package':NAME,'package_bytes':len(saved),'package_sha256':sha(saved),'PIC_sha256':sha(out),'QNX_sha256':sha(app),'FPGA_sha256':sha(ex[1][1]),'source_2_2_2_2_1_sha256':pins,'independent_instruction_verification':'33 words match prior Ghidra12.1.4 independent assembly/disassembly, targets and delay slots','PIC_geometry_changed_bytes':len(pd),'PIC_geometry_instruction_bytes':132,'PIC_version_changed_bytes':2,'QNX_version_changed_bytes':2,'QNX_functional_changed_bytes':0,'package_total_changed_bytes':len(pkgdiff),'PIC_report_paths':reports,'QNX_report_word':hex(reply),'version_gate_cases':2*len(versions),'geometry':geometry,'PIC_transport_checksum_blocks':len(blocks),'valid_corrupt_checksum_cases':len(blocks)*2,'application_checksum':hex(checksum(app)),'FPGA_record_unchanged':True,'package_layout_unchanged':True,'outside_geometry_and_version_bytes_unchanged':True,'audio_mapping_and_QNX_unwind_bytes_unchanged':True,'rejected_region_and_existing_allocations_unchanged':True,'source_candidate_unchanged':True,'hardware_geometry':'NOT VERIFIED on .2.2; .2.1 sonic PASS / graphical FAIL','B16_complete':False,'recovery_independence':'NOT VERIFIED','flashed':False}
put('validation_results.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result,indent=2))

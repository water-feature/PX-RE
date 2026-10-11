# SPDX-License-Identifier: GPL-2.0-or-later
"""Fresh in-place B16 build, gated on independent and scoped validation.
Reads exact .2.0 inputs. Reuses QNX source/established metadata logic, never old candidate binaries.
"""
from pathlib import Path
import sys,runpy,struct,json,subprocess,hashlib,shutil
D=Path(__file__).resolve().parent;B=D.parent;R=B.parent;O=B/'offline_candidate';N=B/'in_place_candidate'
sys.path.insert(0,str(O));b=runpy.run_path(str(O/'build.py'));v=runpy.run_path(str(O/'validate.py'))
sha=b['sha'];elf=b['elf'];changes=b['changes'];parse=b['parsepkg'];BASE=b['BASE']
assert json.loads((D/'preflight_results.json').read_text())['status']=='PASS'
assert json.loads((D/'dependency_results.json').read_text())['status']=='PASS'
assert 'PASS: 51 exact assembly matches' in (D/'GHIDRA_WORD_VERIFICATION.txt').read_text()
N.mkdir(exist_ok=False)
def put(name,data):
 with (N/name).open('xb') as f:f.write(data)
def diff(name,a,z,base=0):
 ds=changes(a,z);put(name,('offset\taddress\told\tnew\n'+''.join(f'{i:#x}\t{base+i:#x}\t{a[i]:02x}\t{z[i]:02x}\n' for i in ds)).encode());return ds
pic=b['PIC'].read_bytes();qnx=b['QNX'].read_bytes();pkg=b['PKG'].read_bytes()
assert sha(pic)==b['PICHASH'] and sha(qnx)==b['QNXHASH'] and sha(pkg)=='89d794880697c18da66356a2fd8cb90b7302d2250574ea4664bdbc496945bc6f'
rows=parse(pkg);assert rows[0][1]==qnx and rows[2][1]==pic
out=bytearray(pic)
for line in (D/'expected_words.tsv').read_text().splitlines():
 a,w,*_=line.split('\t');struct.pack_into('<I',out,int(a,16)-BASE,int(w,16))
out[0x62074:0x6209c]=b'1/32 Step\0' + b'1/64 Step\0'+bytes([156,144,132,120,108,96,84,76,64,56,48,40,32,24,12,0,232,242])+b'\0\0'
for off in (0x475f4,0x47900):assert struct.unpack_from('<H',pic,off)[0]==15;struct.pack_into('<H',out,off,17)
pallowed=set(range(0x4fa74,0x4fb10))|set(range(0x60278,0x60298))|set(range(0x62074,0x620ac))|{0x475f4,0x47900}
assert set(changes(pic,out))<=pallowed
functional_pic=bytes(out)
# Rebuild established QNX helper directly from exact baseline and original source.
for name in ('qnx_helper.s','native_mapper_test.cpp','native_wrapper.s'):shutil.copyfile(O/name,N/name)
src=(O/'build.py').read_text();chunk=src[src.index(' # Assemble x86_64 ELF object'):src.index(" put('voice_2.2.2.2.0_B16_offline_qnx.elf'")]
chunk='\n'.join(line[1:] if line.startswith(' ') else line for line in chunk.splitlines())
ns=dict(b);ns.update(D=N,qnx=qnx,elf=elf,changes=changes,struct=struct,subprocess=subprocess);exec(compile(chunk,'established_QNX_rebuild','exec'),ns)
qo=ns['qo'];functional_qnx=bytes(qo)
put('QNX_rebuild_logic.py',chunk.encode());put('qnx_helper_linked.bin',ns['helper'])
pdiff=diff('PIC_functional_diff.tsv',pic,out,BASE);qdiff=diff('QNX_functional_diff.tsv',qnx,qo,0x100000)
# Established version metadata, tracked separately from functional edits.
for off in (0x1394,0x13a0):assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',out,off)[0])).hexdigest()=='074cd098f2055c6cd2700aaa7190e54b789e6099eccbdf0c96b40abfd604c1c2';struct.pack_into('<I',out,off,0x24840001)
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',qo,0x1f4e3)[0])).hexdigest()=='74da53a4fe7f2418ee58d06afd878968fa2393e8049d8daff09ac74a500329d5';struct.pack_into('<I',qo,0x1f4e3,0x40139221)
assert hashlib.sha256(qo[0x250e9:0x250f0]).hexdigest()=='65fa555819be40547acf6fc4b5eea2a06e4f2c6f7d0a56daf86bbba97e7f483e';qo[0x250ef]=1
assert set(changes(functional_pic,out))=={0x1394,0x13a0};assert set(changes(functional_qnx,qo))=={0x1f4e3,0x250ef}
diff('PIC_version_diff.tsv',functional_pic,out,BASE);diff('QNX_version_diff.tsv',functional_qnx,qo,0x100000)
# Verify version reports by execution and compiled update-gate behavior.
reports=[]
for site,target in ((0x258c0,BASE+0x75c1c),(0x51bc8,BASE+0x75b18)):
 c=v['CPU'](out);c.run(BASE+site,target);assert c.r[4]==0x402a0001 and c.r[31]==BASE+site+8;reports.append({'site':hex(BASE+site),'wire_word':hex(c.r[4])})
packed=struct.unpack_from('<I',qo,0x1f4e3)[0]&65535;rev=[packed>>14,packed>>11&7,packed>>8&7,packed>>4&15,packed&15];assert rev==[2,2,2,2,1]
gatesrc=(R/'b7_candidate_work/validate_version_gates.py').read_text();gn={'app':qo,'struct':struct};exec(gatesrc[gatesrc.index('def gate('):gatesrc.index('\napp_cases=')],gn)
versions=[[2,2,2,2,0],rev,[2,2,2,1,15],[2,2,2,2,2]]
for i in range(5):
 z=rev.copy();z[i]^=1
 if z not in versions:versions.append(z)
for incoming in versions:assert (not bool(gn['gate']('app',incoming).get(0x373c,0)))==(incoming==rev)
for installed in versions:assert bool(gn['gate']('pic',rev,installed).get(0x3744,0))==(installed==rev)
# Exact scope preserves every existing patch except this identified original Sync editor body.
assert set(changes(pic,out))<=pallowed|{0x1394,0x13a0}
assert set(changes(qnx,qo))<=ns['qallowed']|{0x1f4e3,0x250ef}
assert out[:0x1000]==pic[:0x1000] and out[0xe00:0x1000]==pic[0xe00:0x1000]
assert out[0x620ac:0x620b4]==pic[0x620ac:0x620b4]
# Actual emitted instructions/data must equal the preflight memory overlays.
for line in (D/'expected_words.tsv').read_text().splitlines():
 a,w,*_=line.split('\t');assert struct.unpack_from('<I',out,int(a,16)-BASE)[0]==int(w,16)
# PIC receiver checksum arithmetic: all actual blocks, valid and corrupted checksums.
checksum=lambda data:sum(int.from_bytes(data[i:i+2],'little') for i in range(0,len(data),2))&65535
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
# All indexed FDEs and full inherited load extents.
_,_,ph,*_=elf(qo);_,_,oph,*_=elf(qnx);assert [x for x in ph if x[0]==1]==[x for x in oph if x[0]==1]
assert qo[0x10300c:0x104c74]==qnx[0x10300c:0x104c74]
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',qo,0x103008)[0])).hexdigest()=='2d83588e4594e714e920350edff9fd9ae6dd86dd03b2bd04f8c9368490c2f6b5'
entries=[struct.unpack_from('<ii',qo,0x10300c+i*8) for i in range(910)];assert [e[0] for e in entries]==sorted(set(e[0] for e in entries))
for initial,relative in entries:
 f=0x103000+relative;n,delta,pc,span=struct.unpack_from('<IIiI',qo,f);assert n>=12 and f+n+4<=len(qo) and f+8+pc==0x103000+initial;assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',qo,f+4-delta+4)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
assert entries[-1]==(0x101700-0x103000,0x10277c-0x103000)
f=0x10277c;n=struct.unpack_from('<I',qo,f)[0];oldn=struct.unpack_from('<I',qo,0x95338)[0]
assert v['row_at'](qo,qo[0x95338+17:0x95338+4+oldn],0x195d0,0x1ae55)==v['row_at'](qo,qo[f+17:f+4+n],0x101700,0x101700)
put('pic_2.2.2.2.1_B16_in_place.bin',out);put('voice_2.2.2.2.1_B16_in_place_qnx.elf',qo)
subprocess.run(['clang++','-target','x86_64-apple-macos11','-std=c++17','-O2',str(N/'native_mapper_test.cpp'),str(N/'native_wrapper.s'),'-o',str(N/'native_mapper_test')],check=True)
native=json.loads(subprocess.run([str(N/'native_mapper_test'),str(b['QNX']),str(N/'voice_2.2.2.2.1_B16_in_place_qnx.elf')],check=True,capture_output=True,text=True).stdout);assert native['status']=='PASS';put('native_mapper_results.json',(json.dumps(native,indent=2)+'\n').encode())
# Fresh package assembly, re-extraction and checksum checks before final publication.
pieces=[]
for i,payload in enumerate((qo,rows[1][1],out)):
 h=bytearray(rows[i][0]);assert len(payload)==len(rows[i][1])
 if i in (0,2):assert h[2:7]==bytes([2,2,2,2,0]);h[2:7]=bytes(rev)
 trailer=struct.pack('<H',checksum(payload)) if i==0 else rows[i][2];pieces.append(bytes(h)+payload+trailer)
package=b'\xf0'+b''.join(pieces)+b'\xf7';assert len(package)==len(pkg)==3187784
put('package_pending_validation.bin',package);ex=parse((N/'package_pending_validation.bin').read_bytes())
assert ex[0][1]==qo and ex[2][1]==out and ex[1]==rows[1]
for i in (0,1):assert ex[i][2]==struct.pack('<H',checksum(ex[i][1]))
assert ex[2][2]==rows[2][2]==b'00'
for i in range(3):assert ex[i][3:]==rows[i][3:]
for i in (0,2):assert ex[i][0][2:7]==bytes(rev)
allowed={ex[0][4]+p for p in changes(qnx,qo)}|{ex[2][4]+p for p in changes(pic,out)}|{ex[i][3]+6 for i in (0,2)}|{ex[0][5],ex[0][5]+1}
assert set(changes(pkg,package))<=allowed
diff('PIC_all_diff.tsv',pic,out,BASE);diff('QNX_all_diff.tsv',qnx,qo,0x100000);pkgdiff=diff('package_vs_exact_baseline_diff.tsv',pkg,package)
# Confirm rejected candidate tree untouched, including old revision subtree.
preserved=json.loads((B/'safety_review/candidate_preservation.json').read_text())['before']
actual={str(p.relative_to(O)):sha(p.read_bytes()) for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts};assert actual==preserved
name='PxUpdate_V2.2.2.2.1_B16_in_place_candidate.bin';put(name,package)
result={'status':'PASS: offline validation; no flash approval','package':name,'version':rev,'baseline_PIC_sha256':sha(pic),'baseline_QNX_sha256':sha(qnx),'baseline_package_sha256':sha(pkg),'PIC_sha256':sha(out),'QNX_sha256':sha(qo),'FPGA_sha256':sha(ex[1][1]),'package_sha256':sha(package),'package_bytes':len(package),'PIC_functional_changed_bytes':len(pdiff),'QNX_functional_changed_bytes':len(qdiff),'PIC_version_changed_bytes':2,'QNX_version_changed_bytes':2,'package_total_changed_bytes':len(pkgdiff),'PIC_report_paths':reports,'version_gate_cases':len(versions)*2,'PIC_checksum_blocks':len(blocks),'valid_corrupt_checksum_cases':len(blocks)*2,'QNX_FDEs_checked':910,'original_FDEs_unchanged':909,'PT_LOAD_unchanged':True,'FPGA_record_unchanged':True,'package_layout_unchanged':True,'rejected_candidate_files_unchanged':len(actual),'rejected_PIC_region_unchanged':True,'PIC_display_spare_bytes_used':0,'PIC_editor_active_bytes':152,'PIC_editor_body_bytes':156,'PIC_display_used_bytes':88,'PIC_display_footprint_bytes':96,'native':native,'recovery_independence':'NOT VERIFIED; general uncertainty accepted by user','flashed':False}
put('integration_results.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result,indent=2))

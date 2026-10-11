from pathlib import Path
import hashlib,struct,json,sys
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
base=(ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes()
assert sha(base)=='c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f'
assert not (ROOT/'PxUpdate_V2.2.2.0.9.bin').exists()
def parse(b):
 assert b[0]==240 and b[-1]==247
 pos=1;out=[]
 for typ in (1,2,3):
  h=b[pos:pos+12];assert h[:2]==bytes((typ,123)) and h[7]==122
  n=int.from_bytes(h[8:12],'big');out.append((pos,pos+12,pos+12+n,h,b[pos+12:pos+12+n],b[pos+12+n:pos+14+n]));pos+=14+n
 assert pos==len(b)-1
 return out
rr=parse(base);pic0=rr[2][4];app0=rr[0][4]
assert pic0==(ROOT/'b7_candidate_work/pic_2.2.2.0.8.bin').read_bytes()
# Reuse only the established assembly/layout definitions; never execute tests/builders here.
s=(ROOT/'b6_investigation/assemble_layout.py').read_text();ns={'__file__':str(ROOT/'b6_investigation/assemble_layout.py')}
exec(s[:s.index('\n# This virtual address')],ns)
labels,rows,words=ns['layout'](0x9d000c00);assert len(words)==97
pic=bytearray(pic0);manifest={}
def put(a,w,why):
 off=a-0x9d000000;old=struct.unpack_from('<I',pic0,off)[0]
 struct.pack_into('<I',pic,off,w);manifest[f'{a:08X}']={'old':f'{old:08X}','new':f'{w:08X}','old_bytes':struct.pack('<I',old).hex(),'new_bytes':struct.pack('<I',w).hex(),'reason':why}
for a,w in words.items():
 assert pic0[a-0x9d000000:a-0x9d000000+4]==b'\xff'*4
 put(a,w,'B6 unchanged 388-byte helper')
put(0x9d001224,0x0b400300,'B6 hook; inherited delay slot preserved')
# All five PIC revision components match package/application .9.
for a in (0x9d0258b4,0x9d051bc4):
 assert struct.unpack_from('<I',pic0,a-0x9d000000)[0]==0x24842240
 put(a,0x24842220,'PIC revision first four fields 2.2.2.0')
for site,addr,target in [(0x9d0258c0,0x9d001394,0x9d075c1c),(0x9d051bc8,0x9d0013a0,0x9d075b18)]:
 assert struct.unpack_from('<I',pic0,site-0x9d000000)[0]==ns['assemble'](site,('jal',target))
 for a,row in [(addr,('addiu','a0','a0',9)),(addr+4,('j',target)),(addr+8,('nop',))]:
  assert pic0[a-0x9d000000:a-0x9d000000+4]==b'\xff'*4
  put(a,ns['assemble'](a,row),'PIC fifth revision field 9 report thunk')
 put(site,ns['assemble'](site,('jal',addr)),'PIC fifth revision field 9 report hook; LUI delay preserved')
assert struct.unpack_from('<I',pic0,0x52fec)[0]==0x24020004
put(0x9d052fec,0x24020002,'M formatter first three fields 2.2.2')
app=bytearray(app0)
for off in (0x1f4e3,0x250ef):assert app[off]==8;app[off]=9
package=bytearray(base)
for idx,payload in [(0,app),(2,pic)]:
 h,a,z,*_=rr[idx];package[h+2:h+7]=bytes((2,2,2,0,9));package[a:z]=payload
 if idx==0:package[z:z+2]=struct.pack('<H',sum(struct.unpack('<'+'H'*(len(app)//2),app))&65535)
assert package[rr[1][0]:rr[1][2]+2]==base[rr[1][0]:rr[1][2]+2]
assert package[rr[2][2]:rr[2][2]+2]==b'00'
allowed={i for a in manifest for i in range(int(a,16)-0x9d000000,int(a,16)-0x9d000000+4)}
diff=[i for i,(a,b) in enumerate(zip(pic0,pic)) if a!=b];assert set(diff)<=allowed
assert len(pic)==len(pic0)==0x81960 and len(package)==len(base)==3151848
assert [i for i,(a,b) in enumerate(zip(app0,app)) if a!=b]==[0x1f4e3,0x250ef]
(OUT/'pic_2.2.2.0.9.bin').write_bytes(pic);(OUT/'voice_2.2.2.0.9_qnx.elf').write_bytes(app)
# Unpublished package kept separately until candidate validation passes.
(OUT/'package_pending_validation.bin').write_bytes(package)
(OUT/'b6_patch_manifest.json').write_text(json.dumps({'PIC':manifest,'QNX':[{'offset':hex(i),'old':app0[i],'new':app[i],'reason':'version metadata'} for i in (0x1f4e3,0x250ef)],'record_revisions':{'application':[2,2,2,0,9],'PIC':[2,2,2,0,9]},'baseline_sha256':sha(base),'candidate_sha256':sha(package),'PIC_sha256':sha(pic),'QNX_sha256':sha(app),'changed_PIC_bytes':len(diff)},indent=2)+'\n')
assert (ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes()==base
print(json.dumps({'status':'built separately; validation pending','helper_bytes':388,'PIC_manifest_words':len(manifest),'PIC_changed_bytes':len(diff),'package_sha256':sha(package)},indent=2))

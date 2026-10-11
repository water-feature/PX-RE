from pathlib import Path
import struct,json,hashlib,sys
R=Path(__file__).resolve().parent.parent; O=Path(__file__).resolve().parent
sha=lambda x:hashlib.sha256(x).hexdigest()
name='PxUpdate_V2.2.2.1.7.bin'; rev=bytes([2,2,2,1,7])
old=(R/'PxUpdate_V2.2.2.1.6.bin').read_bytes()
assert sha(old)=='12ff4c8ad099010d5f9803c3418b2b7ea0ad7fa383d1d78823bfeca9c51e1618'
def parse(x):
 assert x[0]==240 and x[-1]==247
 p=1; rows=[]
 for t in (1,2,3):
  h=x[p:p+12]; assert h[0]==t and h[1]==123 and h[7]==122
  n=int.from_bytes(h[8:12],'big'); end=p+12+n
  rows.append((p,p+12,end,x[p+12:end],x[end:end+2])); p=end+2
 assert p==len(x)-1
 return rows
a=parse(old); raw=(R/'b14_stable_frame_candidate_work/pic_B14_stable_frame_unpackaged.bin').read_bytes()
assert sha(raw)=='853a74248983b260f95d845341efa2825152bb477d74e504b86a4d2a0cf6844d'
for f in ('validation_results.json','placement_results.json','evidence_results.json'):
 assert json.loads((R/'b14_stable_frame_candidate_work'/f).read_text())['status']=='PASS'
assert a[2][3]==(R/'b14_metadata_packaging_work/pic_2.2.2.1.6.bin').read_bytes()
pic=bytearray(raw); app=bytearray(a[0][3])
for off in (0x1394,0x13a0):
 assert struct.unpack_from('<I',pic,off)[0]==0x24840006
 struct.pack_into('<I',pic,off,0x24840007)
assert app[0x1f4e3]==0x16 and app[0x250ef]==6
app[0x1f4e3]=0x17; app[0x250ef]=7
new=bytearray(old)
for i,payload in ((0,app),(2,pic)):
 h,s,e,_,trailer=a[i];new[h+2:h+7]=rev;new[s:e]=payload
 if i==0:new[e:e+2]=struct.pack('<H',sum(struct.unpack('<'+'H'*(len(payload)//2),payload))&65535)
(O/'pic_2.2.2.1.7.bin').write_bytes(pic);(O/'voice_2.2.2.1.7_qnx.elf').write_bytes(app)
(O/'package_pending_validation.bin').write_bytes(new)
# Independent re-read and byte-level bounds verification.
b=parse((O/'package_pending_validation.bin').read_bytes()); assert len(new)==len(old)==3151848
assert b[1]==a[1] and b[2][4]==a[2][4]==b'00'
assert b[0][3]==app and b[2][3]==pic
for i in (0,1):assert int.from_bytes(b[i][4],'little')==sum(struct.unpack('<'+'H'*(len(b[i][3])//2),b[i][3]))&65535
assert [i for i,(x,y) in enumerate(zip(raw,pic)) if x!=y]==[0x1394,0x13a0]
assert [i for i,(x,y) in enumerate(zip(a[0][3],app)) if x!=y]==[0x1f4e3,0x250ef]
manifest=json.loads((R/'b14_stable_frame_candidate_work/patch_manifest.json').read_text())
allowed={i for lo,hi in manifest['allowed_ranges'] for i in range(lo,hi)}|{0x1394,0x13a0}
pdiff=[i for i,(x,y) in enumerate(zip(a[2][3],pic)) if x!=y]; assert set(pdiff)<=allowed
package_allowed={a[2][1]+i for i in allowed}|{a[0][1]+i for i in (0x1f4e3,0x250ef)}|set(range(a[0][2],a[0][2]+2))
for i in (0,2):package_allowed.update(range(a[i][0]+2,a[i][0]+7))
diff=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y];assert set(diff)<=package_allowed
# Execute inherited version thunks, actual updater gates and PIC checksum code.
sys.path.insert(0,str(R/'b9_250_candidate_work'));from mips_check import CPU,GP,BASE,decode
for site,target in ((0x258c0,0x9d075c1c),(0x51bc8,0x9d075b18)):
 m=CPU(pic);m.run(BASE+site,{target});assert m.g('a0')==0x402a0007 and m.g('ra')==BASE+site+8
for off in (0x258b4,0x51bc4):
 m=CPU(pic);m.s('a0',0x40290000);m.fetch_simple(BASE+off);assert m.g('a0')==0x40292221
assert struct.unpack_from('<I',app,0x1f4e3)[0]==0x40139217
s=(R/'b7_candidate_work/validate_version_gates.py').read_text();ns={'app':app,'pic':pic,'struct':struct};exec(s[s.index('def gate('):s.index('\napp_cases=')],ns)
gate=ns['gate']; cases=0
for image,compiled in ((a[0][3],[2,2,2,1,6]),(app,list(rev))):
 ns['app']=image
 for incoming in ([2,2,2,1,6],[2,2,2,1,5],list(rev),[2,2,2,0,9]):
  assert (not bool(gate('app',incoming).get(0x373c,0)))==(incoming==compiled);cases+=1
ns['app']=app
for installed in ([2,2,2,1,6],[2,2,2,1,5],list(rev),[2,2,2,0,9]):
 assert bool(gate('pic',list(rev),installed).get(0x3744,0))==(installed==list(rev));cases+=1
for i in range(5):
 incoming=list(rev);incoming[i]^=1
 assert gate('app',incoming).get(0x373c,0) and not gate('pic',incoming,list(rev)).get(0x3744,0);cases+=2
m=CPU(pic);blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)]
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
runs=[]
for i in diff:
 if runs and runs[-1]['offset']+len(bytes.fromhex(runs[-1]['old']))==i:
  runs[-1]['old']+=f'{old[i]:02x}';runs[-1]['new']+=f'{new[i]:02x}'
 else:runs.append({'offset':i,'old':f'{old[i]:02x}','new':f'{new[i]:02x}'})
(O/'binary_diff.json').write_text(json.dumps(runs,indent=2)+'\n')
report={'status':'PASS','filename':name,'revision':list(rev),'package_bytes':len(new),'package_sha256':sha(new),'baseline_package_sha256':sha(old),'PIC_sha256':sha(pic),'QNX_sha256':sha(app),'FPGA_sha256':sha(b[1][3]),'PIC_changed_bytes_vs_1_6':len(pdiff),'PIC_metadata_changed_bytes_vs_B14_raw':2,'QNX_metadata_changed_bytes':2,'package_changed_bytes':len(diff),'FPGA_entire_record_unchanged':True,'B9_and_unrelated_bytes_preserved':True,'B14_behavior_identical_to_validated_raw_candidate':True,'rejected_1_5_scheduler_excluded':True,'stable_frame_scheduler_candidate':True,'metadata_SPI_bytes_per_record':68,'application_checksum':b[0][4].hex(),'PIC_container_trailer':b[2][4].hex(),'actual_version_gate_cases':cases,'PIC_transport_blocks':len(blocks),'valid_and_corrupt_transport_comparisons':len(blocks)*2,'hardware_tested':False,'flashed':False}
(O/'packaged_validation.json').write_text(json.dumps(report,indent=2)+'\n')
# Publish only validated exact bytes; never overwrite another package.
dest=R/name
with dest.open('xb') as f:f.write(new)
assert dest.read_bytes()==new
print(json.dumps(report,indent=2))

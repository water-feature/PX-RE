"""Independent reread of delivered package and actual PIC checksum fragments."""
from pathlib import Path
import sys,struct,json,hashlib
P=Path(__file__).resolve().parent;ROOT=P.parent
sys.path.insert(0,str(ROOT));import b7_combined_instruction_model as m
new=(ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes();old=(ROOT/'PxUpdate_V2.2.2.0.7.bin').read_bytes()
def parse(b):
 assert b[0]==240 and b[-1]==247
 p=1;rows=[]
 for typ in (1,2,3):
  h=b[p:p+12];assert h[0:2]==bytes([typ,123]) and h[7]==122
  n=int.from_bytes(h[8:12],'big');rows.append((h,b[p+12:p+12+n],b[p+12+n:p+14+n]));p+=14+n
 assert p==len(b)-1
 return rows
n,o=parse(new),parse(old)
assert len(new)==len(old)
assert n[1]==o[1]
for i in (0,1): assert int.from_bytes(n[i][2],'little')==sum(struct.unpack('<'+'H'*(len(n[i][1])//2),n[i][1]))%65536
assert n[2][2]==o[2][2]==b'00'
pic=n[2][1];assert pic==(P/'pic_2.2.2.0.8.bin').read_bytes()
manifest=json.loads((P/'b7_patch_manifest.json').read_text());allowed=set()
for a,item in manifest.items():
 off=int(a,16)-m.BASE
 assert struct.unpack_from('<I',o[2][1],off)[0]==int(item['old'],16)
 assert struct.unpack_from('<I',pic,off)[0]==int(item['new'],16)
 allowed.update(range(off,off+4))
diff=[i for i,(a,b) in enumerate(zip(pic,o[2][1])) if a!=b];assert set(diff)<=allowed
assert pic[0x1200:0x1220]==o[2][1][0x1200:0x1220]
assert pic[0x1480:]==o[2][1][0x1480:] or all(i>=0x1480 and i in allowed for i in diff if i>=0x1480)
# Execute checksum arithmetic from the correct PIC receiver at 442A4.
# Full-word fragment 44484..44498 and final byte-pair 4466C..44680.
m.IMAGE=pic
machine=m.Machine([(0,999,499,0)]*2,0,0,0)
machine.set('gp',0x80007FF0);gp=machine.get('gp')
blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)]
assert len(blocks)==130 and len(blocks[-1])==2400
for index,b in enumerate(blocks):
 machine.write(gp-0x7F20,0,4)
 pcs=range(0x9D044484,0x9D04449C,4) if len(b)==4096 else range(0x9D04466C,0x9D044684,4)
 for low,high in zip(b[::2],b[1::2]):
  machine.write(gp-0x7F1C,low,4);machine.set('v0',high)
  for pc in pcs: machine.simple(m.decode(pc))
 expected=sum(struct.unpack('<'+'H'*(len(b)//2),b))&65535
 assert machine.read(gp-0x7F20,2)==expected
 # Execute the actual received-checksum construction, then inspect the actual
 # compare branch and its delay store, checking valid and corrupted sums.
 for incoming in (expected,expected^1):
  machine.set('v0',incoming&255);machine.set('a1',incoming>>8);machine.set('v1',expected)
  for pc in (0x9D0444F0,0x9D0444F4,0x9D0444F8): machine.simple(m.decode(pc))
  row=m.decode(0x9D0444FC);assert row==('beq','v0','v1',0x9D0446E8)
  assert (machine.get('v0')==machine.get('v1'))==(incoming==expected)
  machine.simple(m.decode(0x9D044500))
result={'status':'PASS','package_bytes':len(new),'PIC_changed_byte_count':len(diff),'accounted_patch_words':len(manifest),'PIC_payload_growth':0,'transport_checksum_blocks_decoded':len(blocks),'final_block_bytes':len(blocks[-1]),'valid_and_corrupt_block_checksum_comparisons':260,'application_checksum':n[0][2].hex(),'FPGA_checksum':n[1][2].hex(),'PIC_container_trailer':n[2][2].hex(),'package_sha256':hashlib.sha256(new).hexdigest(),'limitations':'Checksum arithmetic/compare fragments executed; USB, full updater transport and post-reset installation were not emulated.'}
(P/'b7_packaged_validation_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

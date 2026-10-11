from pathlib import Path
import struct,hashlib,json
ROOT=Path(__file__).resolve().parent
source=ROOT.parent.parent/'upload/PxUpdate_V2.2.2.1.2.bin'
baseline=source.read_bytes()
assert hashlib.sha256(baseline).hexdigest()=='3e844a73a9f29bf0f1dc24929c989e0cb3946c9a307cab948e6af4c0928b5029'
qnx=bytearray((ROOT/'b13_qnx_preserved_revision.elf').read_bytes())
assert qnx[0x1f4e3]==0x12 and qnx[0x250e2]==1 and qnx[0x250ef]==2
qnx[0x1f4e3]=0x13;qnx[0x250ef]=3
assert len(qnx)==1039304
(ROOT/'candidate_qnx.elf').write_bytes(qnx)
p=bytearray(baseline);p[13:13+len(qnx)]=qnx
assert p[7]==2;p[7]=3
checksum=sum(struct.unpack('<'+'H'*(len(qnx)//2),qnx))&65535
struct.pack_into('<H',p,13+len(qnx),checksum)
# Only the type-1 record is changed. Type-2 and type-3 records are exact copies.
assert p[1039319:]==baseline[1039319:]
allowed=[tuple(x) for x in json.loads((ROOT/'b13_qnx_preserved_revision.receipt.json').read_text())['allowed_difference_spans']]
allowed.extend([(0x1f4e3,0x1f4e4),(0x250ef,0x250f0)])
changes=[i for i,(a,b) in enumerate(zip(baseline,p)) if a!=b]
for i in changes:
 assert i==7 or 13+len(qnx)<=i<15+len(qnx) or any(13+a<=i<13+z for a,z in allowed),hex(i)
assert len(p)==len(baseline)
(ROOT/'candidate_update.bin').write_bytes(p)
manifest={'baseline_package_sha256':hashlib.sha256(baseline).hexdigest(),'output_version':[2,2,2,1,3],'PIC_version_preserved':[2,2,2,1,2],'candidate_qnx_sha256':hashlib.sha256(qnx).hexdigest(),'candidate_package_sha256':hashlib.sha256(p).hexdigest(),'package_bytes':len(p),'qnx_word_checksum':checksum,'changed_package_bytes':len(changes),'changed_qnx_bytes':sum(a!=b for a,b in zip((ROOT/'baseline_qnx.elf').read_bytes(),qnx)),'allowed_qnx_difference_spans':allowed,'scope':'B13 application plus two application revision operands. Complete PIC/FPGA records preserved.'}
(ROOT/'package_build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

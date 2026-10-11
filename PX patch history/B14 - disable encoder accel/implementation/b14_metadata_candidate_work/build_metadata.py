"""Unpackaged .1.4-based metadata-only candidate; no display/version/QNX edits."""
from pathlib import Path
import struct,json,hashlib,sys
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'b14_candidate_work'));from build_b14 import encode as old_encode,R as REG
BASE=0x9d000000;START=BASE+0x411c8
sha=lambda b:hashlib.sha256(b).hexdigest()
def enc(pc,row,labels):
 op,*a=row
 if op in ('lbu','sb','andi','ori'):
  dst,src,imm=a
  return {'lbu':36,'sb':40,'andi':12,'ori':13}[op]<<26|REG[src]<<21|REG[dst]<<16|(imm&65535)
 return old_encode(pc,row,labels)
def build():
 old=(R/'b14_packaging_work/pic_2.2.2.1.4.bin').read_bytes()
 assert sha(old)=='111334a1fc96a473efba6d3c4fdc2b0c227f4daf1453be107cd40cfb9e36feb0'
 # v1=record flash address, a2=record destination. Existing frame owns RA/s0..s6.
 # t1=slot must survive for the unchanged error-name formatter.
 rows=[('addu','a0','v1','zero'),('jal',BASE+0x40230),('addu','s5','a2','zero'),
       ('addiu','t0','zero',64),('jal',BASE+0x420cc),('addu','a0','zero','zero'),
       ('lw','v0','a1',0x1420),('sb','v0','a2',0),('addiu','t0','t0',-1),
       ('bne','t0','zero','byte'),('addiu','a2','a2',1),
       ('ori','v0','zero',0x8000),('lui','v1',0xbf86),('sw','v0','v1',0x138),
       ('addu','s6','s2','s0'),('sll','s6','s6',6),('lbu','v0','s5',45),
       ('j',BASE+0x41264),('nop',)]
 labels={'byte':START+4*4}
 assert len(rows)==19 and START+len(rows)*4==BASE+0x41214
 # Guard every replaced original word against independent exact-baseline dump.
 expected={}
 for line in (R/'b14_investigation/ui_exact_1_4.txt').read_text().splitlines():
  bits=line.split()
  if len(bits)>2 and len(bits[0])==8 and len(bits[1])==8:
   try:expected[int(bits[0],16)]=int(bits[1],16)
   except ValueError:pass
 new=bytearray(old);patches=[]
 def put(pc,row,why):
  off=pc-BASE;before=old[off:off+4]
  assert struct.unpack('<I',before)[0]==expected[pc]
  after=struct.pack('<I',enc(pc,row,labels));new[off:off+4]=after
  patches.append({'address':hex(pc),'offset':hex(off),'before':before.hex(),'after':after.hex(),'assembly':row,'reason':why})
 for i,row in enumerate(rows):put(START+i*4,row,'in-place bounded 64-byte sequential metadata read')
 put(BASE+0x41278,('j',BASE+0x412ac),'tail is already read; shared normal/error continuation exits')
 put(BASE+0x4127c,('nop',),'tail bypass delay slot')
 allowed=[(0x411c8,0x41214),(0x41278,0x41280)]
 diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
 assert len(new)==len(old)==530784 and all(any(lo<=i<hi for lo,hi in allowed) for i in diff)
 assert new[0x13ac:0x1480]==old[0x13ac:0x1480]==b'\xff'*212
 name='pic_B14_metadata_bulk_read_unpackaged.bin';(O/name).write_bytes(new)
 manifest={'baseline':'b14_packaging_work/pic_2.2.2.1.4.bin','baseline_sha256':sha(old),'candidate':name,'candidate_sha256':sha(new),'size':len(new),'allowed_ranges':allowed,'patches':patches,'changed_bytes':len(diff),'write_span_bytes':84,'replacement_words':21,'new_stack_bytes':0,'new_RAM_bytes':0,'code_cave':None,'revision_metadata':'inherited .1.4; no release assigned','display_scheduler':'identical to .1.4; rejected .1.5 excluded','QNX_changed':False,'packaged':False}
 (O/'patch_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (O/'assembly_input.json').write_text(json.dumps({'rows':rows,'labels':labels},indent=2)+'\n')
 (O/'binary_diff.txt').write_text('\n'.join(f"{x['address']} {x['before']} -> {x['after']} {x['assembly']}" for x in patches)+'\n')
 print(json.dumps({k:v for k,v in manifest.items() if k!='patches'},indent=2))
if __name__=='__main__':build()

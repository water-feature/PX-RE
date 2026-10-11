# SPDX-License-Identifier: GPL-2.0-or-later
"""PIC-only scheduler candidate based on tested .1.4. No updater or QNX edits."""
from pathlib import Path
import struct,json,hashlib,sys
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'b14_candidate_work'));from build_b14 import encode as old_encode,R as REG
BASE=0x9d000000;REQ=BASE+0x13ac;DONE=BASE+0x13e0
sha=lambda b:hashlib.sha256(b).hexdigest()
def enc(pc,row,labels):
 op,*a=row
 if op in ('lbu','lhu','sb','sh','andi'):
  dest,src,imm=a
  return {'lbu':36,'lhu':37,'sb':40,'sh':41,'andi':12}[op]<<26|REG[src]<<21|REG[dest]<<16|(imm&65535)
 return old_encode(pc,row,labels)
def build():
 old=(R/'b14_packaging_work/pic_2.2.2.1.4.bin').read_bytes()
 assert sha(old)=='111334a1fc96a473efba6d3c4fdc2b0c227f4daf1453be107cd40cfb9e36feb0'
 assert old[0x13ac:0x1480]==b'\xff'*212
 req=[('lhu','v0','gp',-0x7dec),('beq','v0','zero','start'),('lbu','v0','gp',-0x7fef),
      ('andi','v0','v0',1),('bne','v0','zero','start'),('nop',),
      ('addiu','v0','zero',2),('jr','ra'),('sb','v0','gp',-0x7fef),
      ('addiu','v0','zero',128),('sh','v0','gp',-0x7dec),('jr','ra'),('sb','zero','gp',-0x7fef)]
 done=[('lbu','v0','gp',-0x7fef),('andi','v0','v0',2),('beq','v0','zero','idle'),
       ('addiu','v0','zero',128),('sh','v0','gp',-0x7dec),('j',BASE+0x532fc),('sb','zero','gp',-0x7fef),
       ('j',BASE+0x532fc),('sb','s5','gp',-0x7fef)]
 labels={'start':REQ+9*4,'idle':DONE+7*4}
 assert REQ+len(req)*4==DONE and DONE+len(done)*4==BASE+0x1404
 new=bytearray(old);patches=[]
 def put(pc,w,reason):
  off=pc-BASE;before=old[off:off+4];after=struct.pack('<I',w);new[off:off+4]=after
  patches.append({'address':hex(pc),'offset':hex(off),'before':before.hex(),'after':after.hex(),'reason':reason})
 for pc,before,row,why in [
  (BASE+0x3ee54,0x1460ffc0,('bne','v1','zero',BASE+0x3ed24),'render remaining dirty fields in same frame'),
  (BASE+0x53b80,0x304200ff,('andi','v0','v0',1),'active/active-pending share low idle bit0'),
  (BASE+0x7e4a8,0xa3808011,('j',REQ),'request transfer without restarting active rows'),
  (BASE+0x7e4ac,0x24020080,('nop',),'request hook delay'),
  (BASE+0x53b9c,0xa3958011,('j',DONE),'on completion service pending follow-up'),
  (BASE+0x53ba0,0x0b414cbf,('nop',),'completion hook delay; helper replays original continuation')]:
  assert struct.unpack_from('<I',old,pc-BASE)[0]==before;put(pc,enc(pc,row,labels),why)
 for start,rows in ((REQ,req),(DONE,done)):
  for i,row in enumerate(rows):put(start+i*4,enc(start+i*4,row,labels),'display helper')
 allowed=[(0x13ac,0x1404),(0x3ee54,0x3ee58),(0x53b80,0x53b84),(0x53b9c,0x53ba4),(0x7e4a8,0x7e4b0)]
 diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
 assert len(new)==len(old)==530784 and all(any(lo<=i<hi for lo,hi in allowed) for i in diff)
 name='pic_B14_display_scheduler_unpackaged.bin';(O/name).write_bytes(new)
 manifest={'baseline':'b14_packaging_work/pic_2.2.2.1.4.bin','baseline_sha256':sha(old),'candidate':name,'candidate_sha256':sha(new),'size':len(new),'allowed_ranges':allowed,'patches':patches,'changed_bytes':len(diff),'write_span_bytes':sum(hi-lo for lo,hi in allowed),'helper_bytes':88,'state_byte':'GP-0x7fef / 80000001: 0 active, 1 idle, 2 active+pending','new_RAM_bytes':0,'new_stack_bytes':0,'revision_metadata':'inherited .1.4, experiment filename only','QNX_changed':False,'packaged':False}
 (O/'patch_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (O/'assembly_input.json').write_text(json.dumps({'request':req,'completion':done,'labels':labels},indent=2)+'\n')
 (O/'binary_diff.txt').write_text('\n'.join(f"{x['address']} {x['before']} -> {x['after']} {x['reason']}" for x in patches)+'\n')
 print(json.dumps({k:v for k,v in manifest.items() if k not in ('patches','allowed_ranges')},indent=2))
if __name__=='__main__':build()

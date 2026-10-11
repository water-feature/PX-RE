"""Unpackaged .1.6 experiment: stable sample framebuffer between transitions."""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'b14_ui_candidate_work'))
from build_display import enc
BASE=0x9d000000
sha=lambda b:hashlib.sha256(b).hexdigest()
def build():
 old=(ROOT/'b14_metadata_packaging_work/pic_2.2.2.1.6.bin').read_bytes()
 assert sha(old)=='6389eb6d26c5df964d4fd6de9371e7760d58b2e4e5715d0af4a92035385c85e1'
 assert old[0x13ac:0x1480]==bytes([255])*212
 blocks={
 'guard':[
  ('lbu','v0','gp',-0x7fef),('beq','v0','zero','busy'),('nop',),
  ('lbu','v0','gp',-0x7ff0),('beq','v0','zero','busy'),('nop',),
  ('addiu','sp','sp',-104),('sw','ra','sp',100),('j',BASE+0x3ed14),('nop',),
  ('jr','ra'),('nop',)],
 'page':[
  ('addiu','v0','zero',1),('sb','v0','gp',-0x7fef),('sh','zero','gp',-0x7dec),
  ('addiu','sp','sp',-24),('sw','ra','sp',20),
  ('jal',BASE+0x3ec50),('nop',),('j',BASE+0x3ecb8),('nop',)],
 'resume':[
  ('addiu','v0','zero',1),('sb','v0','gp',-0x7fef),('sh','zero','gp',-0x7dec),
  ('jr','ra'),('sw','v0','gp',-0x7de4)],
 'blank':[
  ('sb','v0','gp',-0x7fef),('sh','zero','gp',-0x7dec),('j',BASE+0x6a8cc),('nop',)],
 'fullclear':[
  ('addiu','v0','zero',1),('bne','a0','v0','full_original'),('nop',),
  ('sb','v0','gp',-0x7fef),('sh','zero','gp',-0x7dec),
  ('addiu','sp','sp',-24),('sw','ra','sp',20),('j',BASE+0x7e410),('nop',)],
 'clear':[
  ('addiu','v0','zero',1),('bne','a0','v0','clear_original'),('nop',),
  ('sb','v0','gp',-0x7fef),('sh','zero','gp',-0x7dec),
  ('sll','v0','a0',3),('sll','a0','a0',15),('j',BASE+0x7e27c),('nop',)]}
 starts={};pc=BASE+0x13ac
 for name,rows in blocks.items():starts[name]=pc;pc+=4*len(rows)
 assert pc<=BASE+0x1480
 labels={'busy':starts['guard']+40,'full_original':starts['fullclear']+20,'clear_original':starts['clear']+20}
 new=bytearray(old);patches=[]
 def put(address,row,reason):
  offset=address-BASE;word=enc(address,row,labels);after=struct.pack('<I',word)
  patches.append({'address':hex(address),'before':old[offset:offset+4].hex(),'after':after.hex(),'reason':reason})
  new[offset:offset+4]=after
 hooks=[(0x3ed0c,(0x27bdff98,0xafbf0064),'guard','j'),
        (0x3ecb0,(0x27bdffe8,0xafbf0014),'page','j'),
        (0x7e408,(0x27bdffe8,0xafbf0014),'fullclear','j'),
        (0x7e274,(0x000410c0,0x000423c0),'clear','j'),
        (0x298d8,(0x24020001,0xaf82821c),'resume','jal')]
 for off,expected,name,op in hooks:
  assert struct.unpack_from('<II',old,off)==expected
  put(BASE+off,(op,starts[name]),name+' entry hook');put(BASE+off+4,('nop',),name+' hook delay')
 assert struct.unpack_from('<I',old,0x29ce0)[0]==0x0f41aa33
 put(BASE+0x29ce0,('jal',starts['blank']),'blanking rectangle cancels previous primary transfer; original selector delay retained')
 assert struct.unpack_from('<I',old,0x3ee54)[0]==0x1460ffc0
 put(BASE+0x3ee54,('bne','v1','zero',BASE+0x3ed24),'render all pending fields before starting stable frame')
 for name,rows in blocks.items():
  for i,row in enumerate(rows):put(starts[name]+i*4,row,name+' helper')
 allowed=[(0x13ac,pc-BASE),*( (off,off+8) for off,_,_,_ in hooks),(0x29ce0,0x29ce4),(0x3ee54,0x3ee58)]
 diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
 assert len(old)==len(new)==530784
 assert all(any(lo<=i<hi for lo,hi in allowed) for i in diff)
 name='pic_B14_stable_frame_unpackaged.bin';(OUT/name).write_bytes(new)
 report={'baseline_sha256':sha(old),'candidate':name,'candidate_sha256':sha(new),'size':len(new),
  'changed_bytes':len(diff),'write_span_bytes':sum(hi-lo for lo,hi in allowed),'helper_bytes':pc-BASE-0x13ac,
  'helper_starts':{k:hex(v) for k,v in starts.items()},'helper_end':hex(pc),'allowed_ranges':allowed,'patches':patches,
  'new_RAM_bytes':0,'new_stack_bytes':0,'revision_metadata':'inherited .1.6 unchanged','packaged':False,
  'limits':'No hardware latency/tearing claim; arbitrary computed writers not excluded by static audit.'}
 (OUT/'patch_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
 (OUT/'assembly_input.json').write_text(json.dumps({'starts':starts,'labels':labels,'blocks':blocks},indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('patches','allowed_ranges')},indent=2))
if __name__=='__main__':build()

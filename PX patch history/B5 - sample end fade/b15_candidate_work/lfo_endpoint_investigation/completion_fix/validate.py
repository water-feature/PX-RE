from pathlib import Path
import subprocess,json,hashlib
O=Path(__file__).resolve().parent;R=O.parents[2]
fixture=(O.parent/'inherited_fixture.c').read_text().replace('reader[128][0x1c0]','reader[128][0x1c8]').replace('#include "../../b5_candidate_work/b5_core.generated.h"','#include "'+str(R/'b5_candidate_work/b5_core.generated.h')+'"').replace('#include "b5_offsets.generated.h"','#include "'+str(O.parent/'b5_offsets.generated.h')+'"')
fixture=fixture.replace('static void init(void){','static int test_slot=0,test_channels=2,test_reverse=0;\nstatic void init(void){')
fixture=fixture.replace('PTR(pool,0)=audio;pool[0x2c]=1;','PTR(pool+test_slot*0x30,0)=audio;pool[test_slot*0x30+0x2c]=1;U32(osc,8)=test_slot;')
fixture=fixture.replace('s=(State *)(pool+0xc00);','s=(State *)(pool+0xc00+test_slot*0x100);')
fixture=fixture.replace('c.rbx=(uintptr_t)pool;c.rdi=(uintptr_t)reader[0];','c.rbx=(uintptr_t)(pool+test_slot*0x30);c.rdi=(uintptr_t)reader[test_slot*2];')
(O/'fixture.c').write_text(fixture)
src=(O.parent/'completion_reproduce.c').read_text().replace('#include "inherited_fixture.c"','#include "fixture.c"').replace('if(next==1){','CHECK(s->d.effective.rate_bits==bits(next));CHECK(!s->d.has_pending);\n if(FIXED || next==1){')
src=src.replace('reader[0]','reader[test_slot*2]').replace('INT(cf+8,0x28)=2','INT(cf+8,0x28)=test_channels').replace('init();prepare(1);read_batch','init();INT(reader[test_slot*2],0x30)=test_reverse;prepare(1);read_batch').replace('1000,9000,0,256','1000,9000,test_reverse,256')
src=src[:src.index('int main(void)')]+(O/'extra_tests.c').read_text();(O/'tests.c').write_text(src)
rows=[]
for label,p,fixed in [('baseline',R/'b14_sample_acceleration_work/voice_2.2.2.1.10_B14_sample_acceleration_candidate_qnx.elf',0),('fixed',O/'fixed_qnx.elf',1)]:
 asm=O/(label+'_image.s')
 lines=['.section __TEXT,__text,regular,pure_instructions','.p2align 4','_firmware:'];cursor=0
 for off,name in sorted([(0x3f840,'read'),(0x2e2e0,'load'),(0x36b20,'filter'),(0x417f0,'publish')]):
  lines += [f'.incbin "{p}",{cursor},{off-cursor}',f'jmp _fixture_{name}','.space 11,0x90'];cursor=off+16
 lines += [f'.incbin "{p}",{cursor},{987136-cursor}','.globl _b5_image','_b5_image:',f'.incbin "{p}",987136,49152']
 asm.write_text('\n'.join(lines)+'\n')
 exe=O/(label+'_tests');subprocess.run(['clang','-arch','x86_64','-O2','-fno-strict-aliasing','-DFIXED='+str(fixed),str(O/'tests.c'),str(asm),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(exe)],check=True)
 run=subprocess.run([str(exe)],capture_output=True,text=True);rows.append(dict(variant=label,exit=run.returncode,stdout=run.stdout,stderr=run.stderr,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
report=dict(status='PASS' if all(r['exit']==0 for r in rows) else 'FAIL',tests=rows,scope='actual baseline/candidate B5 and B8 dispatch/core, inherited wrappers with stock-function substitutes; modeled stock reader/load/filter audio; target hardware NOT VERIFIED')
(O/'validation_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['status']=='PASS'

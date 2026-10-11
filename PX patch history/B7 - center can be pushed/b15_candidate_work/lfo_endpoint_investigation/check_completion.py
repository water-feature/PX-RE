from pathlib import Path
import hashlib,subprocess,json
O=Path(__file__).resolve().parent
R=O.parents[1]
p=R/'b14_sample_acceleration_work/voice_2.2.2.1.10_B14_sample_acceleration_candidate_qnx.elf'
data=p.read_bytes()
asm=O/'completion_image.s'
asm.write_text('.section __TEXT,__text,regular,pure_instructions\n.p2align 4\n.globl _b5_image\n_b5_image:\n.incbin "'+str(p)+'",987136,12288\n')
exe=O/'completion_tests'
subprocess.run(['clang','-arch','x86_64','-O2','-fno-strict-aliasing',str(O/'completion_reproduce.c'),str(asm),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(exe)],check=True)
run=subprocess.run([str(exe)],capture_output=True,text=True)
report={'baseline':str(p),'sha256':hashlib.sha256(data).hexdigest(),'status':'PASS' if run.returncode==0 else 'FAIL','scope':'actual .1.10 B5 dispatch/core; modeled stock audio/loader; hardware NOT VERIFIED','stdout':run.stdout,'stderr':run.stderr,'exit':run.returncode}
(O/'completion_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert run.returncode==0

from pathlib import Path
import json,hashlib,subprocess,sys
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
v=json.loads((OUT/'b6_validation_results.json').read_text());b7=json.loads((OUT/'b6_inherited_B7_results.json').read_text());p=json.loads((OUT/'b6_packaged_validation_results.json').read_text())
assert v['host_cases']==193536 and v['targeted_entry_ABI_and_B7_cases']==2400
assert b7['status']=='PASS' and b7['endpoint_cases_with_retreat']==52224 and p['status']=='PASS'
assert (OUT/'b6_all_patch_decoded.txt').exists()
package=(OUT/'package_pending_validation.bin').read_bytes()
assert hashlib.sha256(package).hexdigest()==p['package_sha256']=='438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d'
assert hashlib.sha256((ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes()).hexdigest()=='c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f'
target=ROOT/'PxUpdate_V2.2.2.0.9.bin'
with target.open('xb') as f:f.write(package)
subprocess.run([sys.executable,str(OUT/'verify_package.py'),str(target)],check=True)
v['status']='PASS';v['baseline_package_sha256']=v.pop('package_sha256');v['candidate_PIC_sha256']=p['PIC_sha256'];v['candidate_package_sha256']=p['package_sha256'];v['instruction_source']='Saved patched PIC candidate; independent raw decoder; no symbolic/sparse execution'
(OUT/'b6_validation_results.json').write_text(json.dumps(v,indent=2)+'\n')
checkpoint={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('build_b6.py','validate_candidate.py','verify_package.py','publish_b6.py','pic_2.2.2.0.9.bin','voice_2.2.2.0.9_qnx.elf')}
(OUT/'b6_build_checkpoint.json').write_text(json.dumps(checkpoint,indent=2)+'\n')
assert target.read_bytes()==package
print('Published and independently re-extracted final .9 package; .8 remains unchanged.')

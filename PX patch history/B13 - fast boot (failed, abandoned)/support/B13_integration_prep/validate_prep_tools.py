# SPDX-License-Identifier: GPL-2.0-or-later
import subprocess,json,hashlib,tempfile
from pathlib import Path
prep=Path(__file__).resolve().parent;review=prep.parent/'B13_v4_review';base=review/'v10_exact_reconstructed.elf';expected_candidate=review/'v10_b13_uuid_v4_candidate.elf';sha=hashlib.sha256(base.read_bytes()).hexdigest();results=[]
with tempfile.TemporaryDirectory() as td:
 d=Path(td)
 def apply(label,path,expected,ok):
  out=d/(label+'.elf');r=subprocess.run(['python3',str(prep/'apply_b13_to_elf.py'),'--baseline',str(path),'--output',str(out),'--expected-baseline-sha256',expected],capture_output=True,text=True)
  assert (r.returncode==0)==ok,(label,r.stdout,r.stderr)
  results.append({'check':label,'result':'pass','candidate_created':out.exists()});return out
 out=apply('known_baseline_reproduces_v4',base,sha,True);assert out.read_bytes()==expected_candidate.read_bytes()
 apply('wrong_baseline_hash_rejected',base,'0'*64,False)
 for label,off in [('startup_contract_change_rejected',0x35281),('occupied_helper_space_rejected',0xf9240)]:
  b=bytearray(base.read_bytes());b[off]^=1;f=d/(label+'.input');f.write_bytes(b);apply(label,f,hashlib.sha256(b).hexdigest(),False)
 b=bytearray(base.read_bytes())
 for o in [0x1f4e3,0x250ef]:b[o]^=1
 f=d/'revision.input';f.write_bytes(b);out=apply('known_revision_operands_preserved',f,hashlib.sha256(b).hexdigest(),True)
 for o in [0x1f4e3,0x250ef]:assert out.read_bytes()[o]==b[o]
 for component in ['pic','fpga']:
  (d/(component+'.old')).write_bytes(('original-'+component).encode());(d/(component+'.new')).write_bytes(('original-'+component).encode())
 (d/'qnx.old').write_bytes(base.read_bytes());(d/'qnx.new').write_bytes(expected_candidate.read_bytes())
 m={'qnx_component_name':'QNX','baseline':{k:k.lower()+'.old' for k in ['PIC','FPGA','QNX']},'candidate':{k:k.lower()+'.new' for k in ['PIC','FPGA','QNX']}}
 (d/'mapping.json').write_text(json.dumps(m));cmd=['python3',str(prep/'verify_extracted_payloads.py'),str(d/'mapping.json'),'--expected-qnx',str(expected_candidate)]
 assert subprocess.run(cmd,capture_output=True).returncode==0;results.append({'check':'preserved_components_accepted','result':'pass'})
 (d/'pic.new').write_bytes(b'changed-PIC');assert subprocess.run(cmd,capture_output=True).returncode!=0;results.append({'check':'PIC_change_rejected','result':'pass'})
 (d/'pic.new').write_bytes((d/'pic.old').read_bytes());(d/'qnx.new').write_bytes(base.read_bytes());assert subprocess.run(cmd,capture_output=True).returncode!=0;results.append({'check':'wrong_packaged_QNX_rejected','result':'pass'})
print(json.dumps(results,indent=2))

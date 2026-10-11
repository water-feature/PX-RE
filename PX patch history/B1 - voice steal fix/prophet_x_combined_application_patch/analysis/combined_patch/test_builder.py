"""Check reproducibility and fail-closed behavior of the offline builder."""
from pathlib import Path
import copy,json,hashlib
from build_application_patch import build
P=Path(__file__).resolve().parent
source=(P.parent/'ProphetX.elf').read_bytes();spec=json.loads((P/'patch_spec.json').read_text())
result,report=build(source,spec)
assert hashlib.sha256(result).hexdigest()=='a47fa006e7f179b5860ff4e8d7e268dc3e5136c6e5cec3a7ec85087afe9e6b02'
assert result==(P/'ProphetX_voice_fade_candidate.elf').read_bytes()
rejections=[]
def reject(name,b,s):
    try:build(b,s)
    except ValueError:rejections.append(name)
    else:raise AssertionError('Invalid input accepted: '+name)
b=bytearray(source);b[0x21399]^=1;reject('modified source',bytes(b),spec)
reject('truncated source',source[:-1],spec)
reject('already patched input',result,spec)
s=copy.deepcopy(spec);s['spans'][0]['expected_sha256']='0'*64;reject('wrong expected bytes',source,s)
s=copy.deepcopy(spec);s['spans'].append(copy.deepcopy(s['spans'][0]));reject('overlapping edits',source,s)
s=copy.deepcopy(spec);s['spans'][0]['replacement_hex']+='00';reject('size-changing replacement',source,s)
s=copy.deepcopy(spec);s['integration_hooks'][0]['target']='0x49fd5';reject('wrong hook destination',source,s)
assert (P.parent/'ProphetX.elf').read_bytes()==source
r={'reproducible_candidate_sha256':report['output_sha256'],'rejected_cases':rejections,'source_unchanged':True}
(P/'builder_test_results.json').write_text(json.dumps(r,indent=2)+'\n')
print('PASS: deterministic candidate and seven invalid-input/specification rejections; original application unchanged.')

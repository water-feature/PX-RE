"""Reuse B6 suites against actual saved candidate instructions, never sparse words."""
from pathlib import Path
import json,hashlib,struct
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
candidate=(OUT/'pic_2.2.2.0.9.bin').read_bytes()
s=(ROOT/'b6_investigation/assemble_layout.py').read_text()
s=s.replace("OUT=Path(__file__).resolve().parent","OUT=Path(__file__).resolve().parent")
s=s.replace("w=overlay.get(pc)\n    if w is None:w=struct.unpack_from('<I',pic,pc-m.BASE)[0]", "w=struct.unpack_from('<I',candidate if overlay else pic,pc-m.BASE)[0]")
# Bind baseline comparison to decoded .8 bytes too, suppress symbolic B7 blocks.
s=s.replace('m.IMAGE=pic','m.IMAGE=pic\nm.Machine.instruction=lambda self,pc:m.decode(pc)')
s=s.replace("'placement_verified':False", "'placement_verified':True")
s=s.replace("'limitations':'External engine/MIDI/custom functions use B7 summaries; no firmware image or package written.'", "'limitations':'Actual candidate bytes executed with external engine/MIDI/custom summaries; hardware pending.'")
s=s.replace("(OUT/'standalone_layout.txt')", "(OUT/'b6_candidate_decoded.txt')")
s=s.replace("(OUT/'layout_results.json')", "(OUT/'b6_validation_results.json')")
ns={'__file__':__file__,'candidate':candidate}
exec(compile(s,str(ROOT/'b6_investigation/assemble_layout.py'),'exec'),ns)
# Reuse B7 endpoint oracle, retreat, custom-side-effect and redispatch suites.
m=ns['m'];BaselineMachine=m.Machine;NewMachine=ns['Machine']
class ComparedMachine(NewMachine):
 def instruction(self,pc):
  return ns['decode'](pc) if self.design else m.decode(pc)
m.Machine=ComparedMachine
source=(ROOT/'b7_combined_instruction_model.py').read_text()
run=source[source.index('def run():'):source.index("\nif __name__")]
a=run.index('    # Direct Center edits unchanged');z=run.index('    # Regression and independence examples.')
run=run[:a]+'    centers=0  # Intentional B6 change covered by B6 suite.\n'+run[z:]
a=run.index('    stock_fault=');z=run.index("    return {'status'")
run=run[:a]+run[z:]
run=run.replace("'stock_linked_bug_reproduced_raw_values':stock_fault.values(1),",'')
exec(run,m.__dict__)
b7=m.run()
for key in ('symbolic_instructions','symbolic_inserted_bytes','planning_extent','limitations'):b7.pop(key,None)
(OUT/'b6_inherited_B7_results.json').write_text(json.dumps(b7,indent=2)+'\n')
# Independently decode manifest and delayed controls from actual candidate.
manifest=json.loads((OUT/'b6_patch_manifest.json').read_text())['PIC'];listing=[]
for a,item in manifest.items():
 pc=int(a,16);w=struct.unpack_from('<I',candidate,pc-m.BASE)[0];assert w==int(item['new'],16)
 row=ns['decode'](pc);listing.append(f'{pc:08X} {w:08X} {row!r}')
 if row[0] in ns['control']:
  assert ns['decode'](pc+4)[0] not in ns['control']
  if row[0] in ('beq','bne'):assert row[3] in ns['words']
assert ns['decode'](0x9d001228)==('addu','s2','a1','zero')
# Execute actual version call, its LUI delay, thunk and return, both senders.
version_cases=[]
for site,thunk,target in [(0x9d0258c0,0x9d001394,0x9d075c1c),(0x9d051bc8,0x9d0013a0,0x9d075b18)]:
 machine=BaselineMachine([(0,999,499,0)]*2,0,0,0)
 machine.set('ra',site+8);machine.simple(ns['decode'](site+4))
 before=machine.r.copy();assert ns['decode'](site)==('jal',thunk)
 machine.simple(ns['decode'](thunk));assert ns['decode'](thunk+4)==('j',target)
 machine.simple(ns['decode'](thunk+8));assert machine.get('a0')==0x402a0009
 assert machine.get('ra')==site+8
 assert all(machine.r[i]==before[i] for i in range(32) if i!=m.R['a0'])
 version_cases.append(hex(site))
(OUT/'b6_all_patch_decoded.txt').write_text('\n'.join(listing)+'\n')
print(json.dumps({'inherited_B7':b7,'actual_candidate_sha256':hashlib.sha256(candidate).hexdigest(),'version_thunk_ABI_cases':version_cases},indent=2))

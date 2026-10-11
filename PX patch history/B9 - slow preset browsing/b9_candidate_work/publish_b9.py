"""Publish the exact independently validated candidate without overwriting files."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
reports=[json.loads((OUT/n).read_text()) for n in ('b9_instruction_validation.json','b9_placement_validation.json','b9_packaged_validation.json')]
assert all(r['status']=='PASS' for r in reports)
b=(OUT/'package_pending_validation.bin').read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha==reports[2]['package_sha256']
p=ROOT/'PxUpdate_V2.2.2.1.1.bin'
with p.open('xb') as f:f.write(b)
assert p.read_bytes()==b
(OUT/'revision_reservation.md').write_text('# B9 revision assignment\n\n2.2.2.1.1 is assigned to this B9 candidate. No pre-existing workspace artifact or reservation for it was found. User explicitly selected the next unused revision after resolving the contradictory .1.0 deliverable name. B7 retains 2.2.2.1.0. The baseline is B6 2.2.2.0.9; no unfinished branch work is incorporated.\n')
print(p.name,sha,len(b))

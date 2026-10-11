#!/usr/bin/env python3
"""Bounded exact-image integration audit, reusing established B15/B14 evidence."""
from pathlib import Path
import ast,json,struct,hashlib,subprocess
import validate_pic_operations as p
O=Path(__file__).resolve().parent;R=O.parent;m=p.m
b=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
t=ast.parse((O/'audit_pic_size.py').read_text());f=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='scan');exec(compile(ast.Module(body=[f],type_ignores=[]),'scan','exec'))
j=json.loads((O/'absolute_pic_integration.json').read_text());new=(O/'pic_B15_absolute_INCOMPLETE.bin').read_bytes();assert len(new)==len(b)==530784
interiors=[];callers={}
for x in j['writes']:
 if x['reason'].startswith('entry '):
  pc=int(x['pc'],16);r=scan(pc+4,pc+8);assert not r['literal_hits'] and not r['nearby_constructed_hits'] and not r['direct_control_hits'],(x['reason'],r)
  interiors.append(hex(pc+4));callers[x['reason']]=scan(pc,pc+4)['direct_control_hits']
# Expanded new private IDs lie in the same bounded unknown40xx family already
# closed in the design. Guard actual QNX comparisons/branch bytes in exact1.7.
q=(R/'b14_stable_frame_packaging_work/voice_2.2.2.1.7_qnx.elf').read_bytes()
# ELF mappings for baseline VAs from builder utility.
import sys
sys.path.insert(0,str(R));from qnx_elf import Elf
elf=Elf(q)
# Use disassembly evidence and exact baseline hash as authority; it was generated
# against this exact image, not the user's mutable Ghidra session.
d=(R/'b15_investigation/qnx_1_7_disassembly.txt').read_text()
for address in ('1f3e8:','1f403:','206a6:'):assert address in d
assert '0x403d' in d and '0x6000' in d
cmdhits=[]
for off in range(0,len(b)-3,4):
 w=struct.unpack_from('<I',b,off)[0]
 if w>>26 in (9,13,15) and 0x4053<=w&65535<=0x4059:cmdhits.append(hex(m.BASE+off))
assert not cmdhits
# New C callees of interior group detour must not touch unsaved SIMD state.
for stem in ('adapter','core'):
 obj=O/('b15_absolute_qnx_adapter.o' if stem=='adapter' else 'b15_absolute_core.o')
 dis=subprocess.check_output(['objdump','-d',str(obj)],text=True)
 (O/f'absolute_{stem}_disassembly.txt').write_text(dis)
 assert not any('%'+reg in dis for reg in ('xmm','ymm','zmm'))
# Every inherited loaded byte outside allowlisted writes is untouched. Whole
# protected spans include vectors/startup, B6 helpers, DINIT, B14 decoder/service.
for lo,hi in [(0,0x2a0),(0xc00,0x1480),(0x1480,0x1b7a0),(0x7a258,0x7a408),(0x7a450,0x7a4f8)]:assert new[lo:hi]==b[lo:hi]
for pc in (0x9d081868,0x9d07fb40):assert struct.unpack_from('<I',new,pc-m.BASE)[0]&65535==0x3fc0
for n in ('absolute_pic_placed_execution.json','absolute_pair_results.json','absolute_stock_setter_results.json'):
 assert 'PASS' in json.loads((O/n).read_text())['status']
qr=json.loads((O/'absolute_qnx_integration_results.json').read_text());assert qr['old_loaded_byte_changes_guarded'] and qr['fixed_frame_cache_endpoint_preserved'] and qr['inherited_FDEs_preserved']==870
report={'status':'BOUNDED_STATIC_INTEGRATION_PASS','hook_interior_ingress':interiors,'root_direct_caller_inventory':callers,'command_allocation':'4048/49/4a/4b..4f/4050/4053..4059 precede stock dispatch; within existing exact unknown40xx family below6000; no alias to ordinary0..9b6, notes20xx/21xx or bounded6080..608f strings. No new4051/4052 use.','new_pic_id_immediate_hits':cmdhits,'lifecycle_coverage':{'load':'040418 invalidates before file decode/raw stores;041db0/041e10/bank export callers keep ordinary return behaviour','import':'0744cc invalidates before replacement; subsequent046e4c apply route and07c470->07c368 covered','defaults':'04cd14 runtime invalidation;052d0c explicit cold bypass initializes64B first','reset':'07c2ac A-only default/send bulk; B unchanged','compare_restore':'04feb4/04ffc4 before copy, original likely branch annul preserved','bulk':'07c368 shared bank replay BEGIN/END prevents loaded Key/Vel/enable/group order becoming edits','group':'ordinary22..24/63..65 invalidation before command; QNX22280 cache/cancellation seam, after resolves matching pair','serialization':'046b5c loops read immediate P; display never writes parameter array; no deferred return or waiting gates'},'RAM_ownership':'Both allocator providers shrunk4000->3fc0; owned tail80057aa0..80057ae0. Reuses closure_pic_evidence/closure_placement_audit; cold init before stock defaults, no DINIT ownership change. QNX RW zero-fill2b1ec0..2b21c0/end symbols verified by builder.','QNX_ABI':{'call_alignment':'entry8; message push8/sub16->0; noteon sub40->0; attempt sub24->0; group interior0 pushes80->0','group_preservation':'all caller GPRs and flags saved; emitted C no SIMD; callee saved via ABI; copied cache store retains flags for2228c conditional','noteon_return':'23b32 jumps2172c; return value/flags not consumed; accepted handler only if oscillator+20 equals requested handler','attempt_return':'stock getter EAX restored by final call, subtraction23a3f unchanged','unwind':'870 inherited FDEs and24 new FDEs; static builder checks relocated index/layout'},'inherited_patches':'Exact write allowlist; protected vectors/startup/B6/DINIT/B14 spans unchanged; QNX fixed-frame endpoint and all other loaded changes guarded. No payload extension or bootloader change.','limits':'Recovered exact-image static caller/reference scope; arbitrary computed aliases not mathematically excluded. Native QNX source/contract tests and fitted MIPS execution, not QNX hardware or physical transport/disk loading.'}
(O/'absolute_integration_audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'entry_interiors_checked':len(interiors),'caller_roots':len(callers)},indent=2))

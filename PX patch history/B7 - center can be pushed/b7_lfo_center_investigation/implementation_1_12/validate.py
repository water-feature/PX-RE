"""Validate saved integrated ELF: never overlay/replace its Center helper."""
from pathlib import Path
import sys,json,struct,hashlib,subprocess,re,copy
O=Path(__file__).resolve().parent;D=O.parent;R=D.parent
sys.path[:0]=[str(R),str(R/'b5_candidate_work')]
from b5_elf_placement_check import ExactElf,decode_index,encode_index,leb,encoded
from validate_b5_candidate import cie_state
BASE=R/'b15_candidate_work/lfo_endpoint_investigation/completion_fix'
P=O/'voice_2.2.2.1.12_qnx.elf';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 b=P.read_bytes();old=(BASE/'voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf').read_bytes()
 build=json.loads((O/'integration.json').read_text());m=json.loads((D/'measurement.json').read_text())
 assert sha(b)==build['QNX_sha256'] and sha(old)==m['baseline_sha256']
 e=ExactElf(b);a=ExactElf(old)
 assert len(b)==len(old) and e.read(0x1a87b,12)==bytes.fromhex(m['hook'])
 assert e.read(0x100f60,859)==(D/'design_payload.bin').read_bytes()
 assert e.read(0x1024e8,188)==(D/'design_frames.bin').read_bytes()
 assert struct.unpack_from('<I',b,0x1f4e3)[0]==0x4013921c and b[0x250ef]==12
 ah=next(p for p in a.phdr if p['type']==0x6474e550);bh=next(p for p in e.phdr if p['type']==0x6474e550)
 frame,pairs=decode_index(a.read(ah['va'],ah['filesz']),ah['va']);_,new=decode_index(e.read(bh['va'],bh['filesz']),bh['va'])
 assert new==sorted(pairs+[tuple(x) for x in m['new_FDEs']]) and len(new)==899
 assert e.read(bh['va'],bh['filesz'])==encode_index(new,bh['va'],frame)
 for pc,f in pairs:assert e.read(f,a.fde(f)['length']+4)==a.read(f,a.fde(f)['length']+4)
 for pc,f in new:assert e.fde(f)['pc']==pc
 for x,y in zip(a.phdr,e.phdr):
  if x['type']==0x6474e550:assert y==dict(x,filesz=0x1c24,memsz=0x1c24)
  else:assert x==y
 secends={'.b15_text':0x1012bb,'.b15_eh_frame':0x1025a4,'.eh_frame_hdr':0x104c24}
 assert a.shnum==e.shnum and a.section_names==e.section_names
 for name,x,y in zip(a.section_names,a.sections,e.sections):
  want=list(x)
  if name in secends:want[5]=secends[name]-x[3]
  assert tuple(want)==y
 whitelist=[(0x1a87b,0x1a887),(0x100f60,0x1012bb),(0x1024e8,0x1025a4),(0x103000,0x104c24),(0x1f4e3,0x1f4e4),(0x250ef,0x250f0)]
 j=a.phdr.index(ah);whitelist.append((a.phoff+j*a.phentsize+32,a.phoff+j*a.phentsize+48))
 for name in secends:
  i=a.section_names.index(name);whitelist.append((a.shoff+i*a.shentsize+32,a.shoff+i*a.shentsize+40))
 diffs=[i for i,(x,y) in enumerate(zip(old,b)) if x!=y]
 assert all(sum(lo<=i<hi for lo,hi in whitelist)==1 for i in diffs)
 # Reuse reviewed bounded CFI decoder/assertions against the saved ELF itself.
 source=(D/'validate_design.py').read_text();code=source[source.index('def rows('):source.index('# Execute emitted payload')]
 ns=dict(e=e,M=m,O=D,leb=leb,encoded=encoded,cie_state=cie_state,copy=copy,re=re)
 exec(code,ns)
 # Generate the same fixture with the payload/hook injection removed. All
 # instructions under test come exclusively from PT_LOADs of saved .1.12.
 fixture=(D/'probe_tests.c').read_text()
 inject=' load(argv[2],image+0x100f60,payload_size);\n image[0x1a87b]=0xe9;int32_t jump=(int32_t)(thunk-0x1a880);memcpy(image+0x1a87c,&jump,4);memset(image+0x1a880,0x90,7);'
 replacement=' CHECK(payload_size==859);CHECK(image[0x1a87b]==0xe9);int32_t jump;memcpy(&jump,image+0x1a87c,4);CHECK((uintptr_t)(0x1a880+jump)==thunk);for(int i=5;i<12;i++)CHECK(image[0x1a87b+i]==0x90);'
 assert fixture.count(inject)==1;fixture=fixture.replace(inject,replacement)
 (O/'integrated_fixture.c').write_text(fixture)
 exe=O/'integrated_tests'
 subprocess.run(['clang','-arch','x86_64','-O2','-ffp-contract=off','-fno-strict-aliasing',str(O/'integrated_fixture.c'),str(D/'probe_getter.s'),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(exe)],check=True)
 run=subprocess.run([str(exe),str(P),'UNUSED_NO_PAYLOAD_OVERLAY','859',str(m['symbols']['center_thunk'])],capture_output=True,text=True)
 assert run.returncode==0,(run.stdout,run.stderr)
 # Inherited .1.11 completion/B5/B8 regression fixture, now .incbin saved .1.12.
 asm=(BASE/'fixed_image.s').read_text();oldpath=str(BASE/'fixed_qnx.elf');assert oldpath in asm
 asm=asm.replace(oldpath,str(P));(O/'inherited_image.s').write_text(asm)
 inherited=O/'inherited_tests'
 subprocess.run(['clang','-arch','x86_64','-O2','-fno-strict-aliasing','-DFIXED=1',str(BASE/'tests.c'),str(O/'inherited_image.s'),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(inherited)],check=True)
 regression=subprocess.run([str(inherited)],capture_output=True,text=True);assert regression.returncode==0,(regression.stdout,regression.stderr)
 pic=(O/'pic_2.2.2.1.12.bin').read_bytes();pic0=(BASE/'pic_2.2.2.1.11_B5_completion_fade_candidate.bin').read_bytes()
 assert sha(pic)==build['PIC_sha256'] and [i for i,(x,y) in enumerate(zip(pic0,pic)) if x!=y]==[0x1394,0x13a0]
 report=dict(status='PASS',QNX_sha256=sha(b),PIC_sha256=sha(pic),emitted_saved_ELF=json.loads(run.stdout),inherited_regression=dict(exit=regression.returncode,stdout=regression.stdout,stderr=regression.stderr),all_differences_accounted=True,QNX_differing_bytes=len(diffs),PIC_behavior_byte_identical_except_two_revision_bytes=True,reviewed_payload_and_CFI_identical=True,CFI_and_alignment_checks='PASS against saved ELF',inherited_FDEs_identical=897,all_FDEs_decodable=899,extra_peak_stack_through_getter_entry=456,hardware='NOT VERIFIED',scope='actual integrated x86 hook/helper, stock geometry slices/getters; inherited emitted completion/B5/B8 code with modeled dependencies; complete QNX runtime/audio not executed')
 assert P.read_bytes()==b
 (O/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

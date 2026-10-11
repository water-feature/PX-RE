"""Run bounded emitted-code fixture and validate exact CFI/placement evidence."""
from pathlib import Path
import sys,struct,json,subprocess,re,copy,hashlib
O=Path(__file__).resolve().parent;R=O.parent
sys.path[:0]=[str(R),str(R/'b5_candidate_work')]
from b5_elf_placement_check import ExactElf,leb,encoded
from validate_b5_candidate import cie_state
M=json.loads((O/'measurement.json').read_text())
P=R/'b15_candidate_work/lfo_endpoint_investigation/completion_fix/voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf'
B=P.read_bytes();assert hashlib.sha256(B).hexdigest()==M['baseline_sha256']
view=bytearray(B)
view[M['code_base']:M['code_end']]=(O/'design_payload.bin').read_bytes()
view[M['frame_base']:M['frame_end']]=(O/'design_frames.bin').read_bytes()
e=ExactElf(bytes(view))
def rows(va):
 rec=e.fde(va);data=e.read(va,rec['length']+4);cie=rec['cie'];ca,da,initial,aug=cie_state(e,cie['va']);pc=rec['pc']
 _,p=encoded(data,8,cie['encoding'],va);_,p=encoded(data,p,cie['encoding']&15,va)
 if aug.startswith('z'):n,p=leb(data,p);p+=n
 state=copy.deepcopy(initial);out=[(pc,copy.deepcopy(state))];saved=[]
 def arg():
  nonlocal p
  v,p=leb(data,p);return v
 def expr():
  nonlocal p
  n=arg();x=data[p:p+n];p+=n;return x.hex()
 while p<len(data):
  op=data[p];p+=1
  if op==0:continue
  if op&0xc0==0x40:pc+=(op&63)*ca
  elif op&0xc0==0x80:state['rules'][op&63]=('offset',arg()*da)
  elif op&0xc0==0xc0:
   reg=op&63
   if reg in initial['rules']:state['rules'][reg]=initial['rules'][reg]
   else:state['rules'].pop(reg,None)
  elif op in (2,3,4):
   n={2:1,3:2,4:4}[op];pc+=int.from_bytes(data[p:p+n],'little')*ca;p+=n
  elif op==12:state['cfa']=(arg(),arg())
  elif op==13:state['cfa']=(arg(),state['cfa'][1])
  elif op==14:state['cfa']=(state['cfa'][0],arg())
  elif op==15:state['cfa']=('expression',expr())
  elif op==16:reg=arg();state['rules'][reg]=('expression',expr())
  elif op==10:saved.append(copy.deepcopy(state))
  elif op==11:state=saved.pop()
  elif op==0x2e:arg()
  else:raise ValueError('unsupported CFI opcode '+hex(op))
  out.append((pc,copy.deepcopy(state)))
 return out
def at(rs,pc):return next(r for p,r in reversed(rs) if p<=pc)
original=at(rows(0x95338),0x1a87b) # exact current baseline FDE address
assert original['cfa']==('expression','765806')
thunk_fde=next(f for pc,f in M['new_FDEs'] if pc==M['symbols']['center_thunk'])
tr=rows(thunk_fde)
for pc in range(M['symbols']['center_thunk'],M['code_end']):assert at(tr,pc)==original
# Independently evaluate the exact DWARF expressions used by this frame.
rbp=0x700000;outer_cfa=0x710000
memory={rbp-40:outer_cfa,rbp:0x111,rbp-8:0x222,rbp-16:0x333,rbp-24:0x444,rbp-32:0x555,rbp-48:0x666,outer_cfa-8:0x777}
def evaluate(x):
 b=bytes.fromhex(x);assert b[0]==0x76;offset,pos=leb(b,1,True);v=rbp+offset
 if pos<len(b):assert b[pos:]==b'\x06';v=memory[v]
 return v
assert evaluate(original['cfa'][1])==outer_cfa
recovered={}
for reg,rule in original['rules'].items():
 recovered[reg]=memory[evaluate(rule[1])] if rule[0]=='expression' else memory[outer_cfa+rule[1]]
assert recovered=={16:0x777,6:0x111,15:0x222,14:0x333,13:0x444,12:0x555,3:0x666}
# Core frame rows: normal CALL frame, at maximum allocation CFA=rsp+112.
core_fde=next(f for pc,f in M['new_FDEs'] if pc==M['symbols']['center_probe'])
cr=rows(core_fde);deep=at(cr,M['symbols']['center_probe']+0xe)
assert deep['cfa']==(7,112)
assert deep['rules']=={16:('offset',-8),6:('offset',-16),15:('offset',-24),14:('offset',-32),13:('offset',-40),12:('offset',-48),3:('offset',-56)}
# Original stack is 64-byte aligned: realign, 2 pushes, then 6 pushes + 0x280.
assert (-16-48-0x280)%64==0
assert (0-80-256)%16==0 # wrapper call site
assert (0-80-256-8-48-56)%16==0 # core's getter call sites
peak=336+8+104+8;assert peak==456
# Stolen instruction window has no interior branch target in full Ghidra body.
trace=(O/'trace.txt').read_text()
for line in trace.splitlines():
 if re.match(r'^001[0-9a-f]+ (?:J\w+|CALL) ',line):
  targets=re.findall(r'0x([0-9a-f]+)',line)
  assert not any(0x11a87b<int(t,16)<0x11a887 for t in targets)
# Execute emitted payload bytes, stock .1.11 getters/map and actual hook/replay.
exe=O/'probe_tests'
subprocess.run(['clang','-arch','x86_64','-O2','-ffp-contract=off','-fno-strict-aliasing',str(O/'probe_tests.c'),str(O/'probe_getter.s'),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(exe)],check=True)
run=subprocess.run([str(exe),str(P),str(O/'design_payload.bin'),str(M['code_and_constants_and_alignment']),str(M['symbols']['center_thunk'])],capture_output=True,text=True)
report=dict(status='PASS' if run.returncode==0 else 'FAIL',exit=run.returncode,stderr=run.stderr,emitted_host=json.loads(run.stdout) if run.returncode==0 else run.stdout,wrapper_CFI_matches_original_at_every_byte=True,original_CFA_expression_evaluated=True,core_CFI_validated=True,stack_alignment=True,extra_peak_stack_bytes=peak,interior_branch_targets_absent_in_ghidra_function=True,firmware_unmodified=P.read_bytes()==B,scope='actual isolated emitted x86/hook replay, stock getters/map and both stock geometry instruction slices in all size modes; fake parameter/modulation/reader objects and bounded arithmetic oracle; complete QNX playback and hardware NOT VERIFIED')
(O/'design_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['status']=='PASS'

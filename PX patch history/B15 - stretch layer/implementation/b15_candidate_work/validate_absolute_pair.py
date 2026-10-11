#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fitted PIC emitted execution connected to native actual QNX adapter/policy.
Stock peripheral, setter body and resolver are test contracts; no hardware claim.
"""
from pathlib import Path
import os,ctypes,json
os.environ['B15_PLACED']='1'
import validate_pic_absolute as v
import validate_absolute_stock_setter as stock
O=Path(__file__).resolve().parent;L=v.L;S=v.S
q=ctypes.CDLL(str(O/'absolute_pair_bridge.dylib'));cbtype=ctypes.CFUNCTYPE(None,ctypes.c_uint,ctypes.c_uint)
feedback=[]
@cbtype
def receive(cmd,data):feedback.append((cmd,data))
ctypes.c_void_p.in_dll(q,'b15_pair_feedback').value=ctypes.cast(receive,ctypes.c_void_p).value
q.b15_pair_value.restype=ctypes.c_uint
class CPU(stock.CPU):
 def external(self,pc):
  if pc in (0x9d04dacc,0x9d075c1c):return False # execute real installed entry wrapper
  if pc==0x9d075c24:
   a=self.g('a0');q.b15_pair_command(a>>16,a&65535)
  return super().external(pc)
c=CPU();cases=[]
def call(name,*args):
 for n,x in zip(('a0','a1','a2','a3'),args):c.s(n,x)
 c.s('ra',v.STOP);before={n:c.g(n) for n in ('sp','s0','s1','s2','s3','s4','s5','s6','s7','fp','gp')};irq=c.status
 c.run(L.get(name,name),{v.STOP},maxsteps=100000)
 assert all(c.g(n)==x for n,x in before.items()) and c.status==irq
 return c.g('v0')
def drain():
 while feedback:
  cmd,data=feedback.pop(0);call('b15_pic_receive',cmd,data)
def actual(p):return c.read(S+16*p+4,1)
def store(bank,pid,n):call(0x9d04dacc,0,bank,pid,n)
def turn(bank,pid,n):c.write(c.g('sp')+16,16,4);call('b15_encoder',0,bank,pid,n&0xffffffff)
q.b15_pair_init();call('b15_pic_init')
for bank in (0,1):
 for inst in (0,1):store(bank,0x14+65*inst,64+inst);store(bank,0x12+65*inst,1)
drain();assert [actual(p) for p in range(4)]==[3,4,6,8]
assert [q.b15_pair_value(p,2) for p in range(4)]==[64,65,64,65]
cases.append('installed setter entry: no-held highest at stored Key, all four pairs')
for d in [-1,1]*500:turn(2,0x1c,d)
assert len(feedback)>1000;drain();assert actual(0)==3 and actual(2)==6
cases.append('1000 A+B reversals with delayed feedback cannot rebase later edits')
for bank in (0,1):
 store(bank,0x1c,2);store(bank,0x14,70+bank)
drain();assert actual(0)==actual(2)==2
for bank in (0,1):
 before=q.b15_pair_value(0,7);store(bank,0x1c,0);assert q.b15_pair_value(0,7)==before
 drain();turn(bank,0x1c,1)
drain();assert actual(0)==actual(2)==3
cases.append('absolute/MIDI-style stores, Key target retention and On/no-reload/next actual-base detent')
# Feedback captured before a new raw context must be rejected; fresh replay wins.
store(0,0x1c,1);stale=feedback[:];feedback.clear()
c.write(c.g('sp')+16,0x11223344,4);c.write(c.g('sp')+20,0x55667788,4);call('b15_load',0,22,33,44)
for cmd,data in stale:call('b15_pic_receive',cmd,data)
assert actual(0)==0
drain()
# Replay uses real bulk wrapper around a modeled stock replay body. Exercise its
# own packets and then explicit loaded contents inside one additional real token.
call('b15_context',15,1);call('b15_transport',0x404f000f)
for bank in (0,1):
 for inst in (0,1):store(bank,0x14+65*inst,74);store(bank,0x1c+65*inst,1);store(bank,0x12+65*inst,1)
call('b15_transport',0x4050000f);drain()
assert [actual(p) for p in range(4)]==[3,4,6,8] and all(not q.b15_pair_value(p,4) for p in range(4))
cases.append('raw-load invalidation rejects saved old feedback; bulk loaded settings do not become explicit layer edits')
# Capture actual played instrument2 layer; snapshot precedes enable/legacy clear,
# COMMIT consumes final stored key. Both bank snapshots independent.
for bank in (0,1):store(bank,0x53,0);q.b15_pair_note(2*bank+1,67,2+bank)
drain();root=0x80052e18;c.write(root+6,1,2);c.s('s0',root);c.s('s1',67)
call('b15_capture_prepare',2)
assert q.b15_pair_value(1,8)==q.b15_pair_value(3,8)==1, [q.b15_pair_value(p,8) for p in range(4)]
for bank in (0,1):store(bank,0x53,1);store(bank,0x55,67)
assert not feedback, (feedback, c.sent[-15:]) # prepared suppresses intermediate display frames
call('b15_capture_commit',0,2,0x54,0);drain();assert actual(1)==2 and actual(3)==3
cases.append('held instrument2 A+B captures actual independent played layers; intermediate feedback suppressed')
# Key/group-await cursor0 permits drops, no edit queue or waits.
store(0,0x55,75);p_before=c.read(0x8000046c+2*0x5d,2);turn(0,0x5d,1);assert c.read(0x8000046c+2*0x5d,2)==p_before
drain();assert actual(1)==2
store(0,0x53,0);store(0,0x53,1);drain();assert actual(1)==4
cases.append('pending-key detent drops; disable/re-enable chooses highest without layer history')
report={'status':'PAIRED_COMPONENT_PASS_NOT_RELEASE','cases':cases,'pic_image':'pic_B15_absolute_INCOMPLETE.bin','limits':'Fitted MIPS helper/detour execution plus actual native QNX C adapter/policy; stock setter, raw operation bodies and sample resolver remain contracts. Does not establish lifecycle coverage or target QNX thunk runtime/physical transport.'}
(O/'absolute_pair_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

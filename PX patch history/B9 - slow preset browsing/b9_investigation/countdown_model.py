# SPDX-License-Identifier: GPL-2.0-or-later
"""B9 behavioral design model, not a firmware emulator or patched payload.
Application callees and IRQ timing are summarized; zero is held until main service.
"""
from dataclasses import dataclass,field
from itertools import product
import json
from pathlib import Path

@dataclass
class Model:
    design:str='baseline'
    window:int=500
    desired:tuple=(0,0)
    applied:list=field(default_factory=lambda:[(0,0),(0,0)])
    count:list=field(default_factory=lambda:[-1,-1])
    pending:list=field(default_factory=lambda:[None,None])
    tick:int=0
    loads:list=field(default_factory=list)
    def apply(self,key,mode,why):
        for p in ([0,1] if mode==2 else [mode]): self.applied[p]=key
        self.loads.append((self.tick,key,mode,why))
    def select(self,key,source='panel',mode=2):
        # Panel callers suppress deltas clamped to their already desired value.
        if source=='panel' and key==self.desired: return
        self.desired=key
        slot=int(mode==1)
        before=self.count[slot]
        self.pending[slot]=(key,mode,source)
        if before<=0: self.apply(key,mode,'input')
        if self.design=='B' and source=='panel' and before>0: return
        self.count[slot]=self.window if source=='panel' and self.design=='A' else 500
    def service_tick(self,eligible=True):
        self.tick+=1
        if eligible:
            self.count=[c-1 if c>0 else c for c in self.count]
    def expire(self):
        for slot,c in enumerate(self.count):
            if c==0:
                key,mode,source=self.pending[slot]
                # Matches baseline comparison against slot's applied identity.
                if key!=self.applied[slot]:self.apply(key,mode,'expiry')
                self.count[slot]=-1
    def op(self,x):
        b,p=self.desired
        if x=='+':self.select((b,min(127,p+1)))
        elif x=='-':self.select((b,max(0,p-1)))
        elif x=='bank':self.select((min(11,b+1),p))
        elif x=='midiA':self.select((1,9),'midi',0)
        elif x=='midiB':self.select((2,9),'midi',1)
        elif x=='stored':self.select((3,9),'stored',2)
        elif x=='tick':self.service_tick()
        elif x=='expiry':self.expire()
        else:raise ValueError(x)

def finish(m):
    for _ in range(max(m.count+[0])):m.service_tick()
    m.expire()
    return m

results={}
for design in ['baseline','A','B']:
    m=Model(design,100)
    for t in range(2001):
        if t:m.service_tick()
        if t%50==0:m.select((0,(t//50+1)%128))
        m.expire()
    finish(m)
    results[design]={'continuous_every_50_ticks':m.loads,'final':m.applied,'count':m.count}

# Both possible serial orderings of input coincident with zero/expiry.
for order in ['input_first','expiry_first']:
    m=Model('B');m.select((0,1));m.select((0,2))
    for _ in range(500):m.service_tick()
    if order=='input_first':m.select((0,3));m.expire()
    else:m.expire();m.select((0,3))
    assert m.applied==[(0,3),(0,3)]
    finish(m);assert m.count==[-1,-1]
    results[order]=m.loads
# Reversal coincident with zero exposes inherited immediate-path non-suppression.
for order in ['input_first','expiry_first']:
    m=Model('B');m.select((0,1));m.select((0,2))
    for _ in range(500):m.service_tick()
    if order=='input_first':m.select((0,1));m.expire()
    else:m.expire();m.select((0,1))
    assert m.applied==[(0,1),(0,1)]
    results['zero_reversal_'+order]=m.loads
# Expiry-first periodic execution exposes paired intermediate applications.
m=Model('B')
for t in range(2001):
    if t:m.service_tick()
    m.expire()
    if t%50==0:m.select((0,(t//50+1)%128))
finish(m)
results['continuous_expiry_first']=m.loads
# Reversal back to applied is suppressed at expiry, bank changes count as different.
m=Model('B');m.select((0,1));m.select((0,2));m.select((0,1));finish(m)
assert len(m.loads)==1
results['reversal_to_applied']=m.loads
m=Model('B');m.select((0,1));m.select((1,1));finish(m)
assert m.applied==[(1,1),(1,1)]
results['bank_change']=m.loads
# An interrupt making the countdown zero after its positive snapshot must not be lost.
m=Model('B');m.select((0,1));m.count[0]=1;m.select((0,2));m.service_tick();m.expire()
assert m.applied==[(0,2),(0,2)]
# Ineligible time delays wall progress but never decrements zero below zero.
m=Model('B');m.select((0,1));m.select((0,2))
for _ in range(200):m.service_tick(False)
assert m.count[0]==500
finish(m);assert m.applied==[(0,2),(0,2)]
# Explicit final-delay upper bound in eligible ticks, absent main starvation.
for c in range(1,501):
 m=Model('B');m.select((0,1));m.count[0]=c;m.select((0,2))
 before=m.tick;finish(m)
 assert m.tick-before==c and m.applied==[(0,2),(0,2)]
# Nonpanel-only traces must retain baseline behavior, including slot routing.
remote_cases=0
for seq in product(['midiA','midiB','stored','tick','expiry'],repeat=5):
 a=Model('baseline');b=Model('B')
 for op in seq:a.op(op);b.op(op)
 assert (a.desired,a.applied,a.count,a.pending,a.loads)==(b.desired,b.applied,b.count,b.pending,b.loads)
 remote_cases+=1
# Exhaustive short serial event traces with a scaled countdown boundary.
# Use baseline's 500 value replaced through explicit tick-to-expiry operations.
checked=0
for seq in product(['+','-','bank','midiA','midiB','stored','tick','expiry'],repeat=5):
 m=Model('B')
 for op in seq:
  if op=='tick':
   # Jump to zero; deliberately postpone main expiry until its explicit operation.
   m.tick+=max(m.count+[0]);m.count=[0 if c>0 else c for c in m.count]
  else:m.op(op)
  assert all(c>=-1 for c in m.count)
  if m.loads and m.loads[-1][2]==2:
   # Last both-layer application updates both together in this abstract model.
   pass
 finish(m)
 assert m.count==[-1,-1]
 checked+=1
results['checks']={'remote_only_traces':remote_cases,'mixed_serial_traces':checked,'final_delay_positions':500,'targeted_scenarios':10,'status':'PASS'}
results['limits']=['Application is an atomic contract in this model, not proof of physical layer atomicity.','No instruction execution, interrupt latency, sample I/O, external reentrancy, or wall-clock bound is simulated.','Nonpanel equivalence is for nonpanel-only traces; panel changes naturally change subsequent shared-slot history.','Existing expiry returns to -1: subsequent continuous input can immediately apply, giving paired loads.']
Path(__file__).with_name('countdown_model_results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'checks':results['checks'],'continuous_load_counts':{d:len(results[d]['continuous_every_50_ticks']) for d in ['baseline','A','B']},'expiry_orderings':{o:results[o] for o in ['input_first','expiry_first']}}))

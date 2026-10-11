# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only B7 design model: stock MIPS instructions plus symbolic proposed shims.

No instruction bytes are assembled or written. External output/UI callees are
contract summaries, deliberately clobbering volatile registers. This is not a
PIC/transport emulator. Run from the working folder; prints a JSON report.
"""
from pathlib import Path
import hashlib
import itertools
import json
import struct

BASE = 0x9D000000
IMAGE = Path(__file__).with_name('pic_2.2.2.0.7.bin').read_bytes()
EXPECTED = '94e75694df255b6e93dc1786b91dad31cc631e87224362dc2fcbf4f2e8c94bb0'
assert hashlib.sha256(IMAGE).hexdigest() == EXPECTED
REGS = 'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
R = dict(zip(REGS, range(32)))
PARAM = 0x8000046C
GATE = 0x80006FFE
ENTRY = 0x9D04DACC
CAPTURE = 0x9D001220
ORDER = 0x9D001240
ADAPT_A = 0x9D0012C0
ADAPT_B = 0x9D0012F0
PUSH = 0x9D001320

# Planning instructions only. Tuple interpreter uses the same delayed control
# transfer semantics as recovered MIPS. No assembler/object/firmware output.
BLOCKS = {}
def block(base, instructions):
    labels = {}
    pc = base
    for row in instructions:
        if row[0].endswith(':'):
            labels[row[0][:-1]] = pc
        else:
            pc += 4
    pc = base
    for row in instructions:
        if row[0].endswith(':'):
            continue
        BLOCKS[pc] = tuple(labels.get(x, x) if isinstance(x, str) else x for x in row)
        pc += 4
    return pc

CAPTURE_END = block(CAPTURE, [
    ('sw', 'a3', 0x10, 'sp'),
    ('j', 0x9D04DAFC), ('move', 's2', 'a1'),
])
ORDER_END = block(ORDER, [
    ('addiu', 't0', 's0', -0x41), ('sltiu', 't1', 's0', 0x41),
    ('movn', 't0', 's0', 't1'), ('addiu', 't1', 't0', -7),
    ('andi', 't1', 't1', 0xFFFD), ('bne', 't1', 'zero', 'done'), ('nop',),
    ('lw', 's3', 0x10, 'sp'),
    ('addiu', 't2', 's0', 0x6B7), ('sll', 't2', 't2', 1),
    ('addu', 't2', 's1', 't2'), ('addiu', 't1', 't0', -7),
    ('bne', 't1', 'zero', 'end'), ('nop',),
    ('lhu', 't3', 4, 't2'), ('sltu', 't1', 't3', 's3'),
    ('j', 'done'), ('movn', 's3', 't3', 't1'),
    ('end:',), ('lhu', 't3', -4, 't2'), ('sltu', 't1', 's3', 't3'),
    ('movn', 's3', 't3', 't1'),
    ('done:',), ('j', 0x9D04DFA8), ('li', 'a0', 1),
])
def adapter(base, part, yes, no):
    return block(base, [
        ('move', 'a0', 's5'), ('li', 'a1', part),
        ('jal', PUSH), ('move', 'a2', 'v1'),
        ('bne', 's5', 'zero', 'yes'), ('nop',),
        ('j', no), ('nop',), ('yes:',), ('j', yes), ('nop',),
    ])
AA_END = adapter(ADAPT_A, 0, 0x9D04DE80, 0x9D04DE70)
AB_END = adapter(ADAPT_B, 1, 0x9D04DFD4, 0x9D04DFC4)
PUSH_END = block(PUSH, [
    ('addiu', 't0', 's0', -0x41), ('sltiu', 't1', 's0', 0x41),
    ('movn', 't0', 's0', 't1'), ('addiu', 't1', 't0', -7),
    ('andi', 't1', 't1', 0xFFFD), ('bne', 't1', 'zero', 'return'), ('nop',),
    ('addiu', 't1', 't0', -5), ('sll', 't1', 't1', 1),
    ('subu', 't2', 'a2', 't1'), ('lhu', 't1', 0, 't2'),
    ('beq', 't1', 'zero', 'return'), ('nop',),
    ('lhu', 'a3', 0, 'a2'), ('lhu', 't3', 20, 't2'),
    ('addiu', 't1', 't0', -7), ('bne', 't1', 'zero', 'end'), ('nop',),
    ('sltu', 't1', 't3', 'a3'), ('j', 'cross'), ('nop',),
    ('end:',), ('sltu', 't1', 'a3', 't3'),
    ('cross:',), ('beq', 't1', 'zero', 'return'), ('nop',),
    ('subu', 'a2', 's0', 't0'), ('j', ENTRY), ('addiu', 'a2', 'a2', 15),
    ('return:',), ('jr', 'ra'), ('nop',),
])
assert CAPTURE_END <= ORDER and ORDER_END <= ADAPT_A
assert AA_END <= ADAPT_B and AB_END <= PUSH and PUSH_END <= 0x9D001480
GATES = {
    0x9D04E2D0: 0x9D04E4EC, 0x9D04DCC4: 0x9D04E4EC,
    0x9D04E4D4: 0x9D04E4EC, 0x9D04E420: 0x9D04E4EC,
    0x9D04DDE8: 0x9D04E4B0, 0x9D04DBFC: 0x9D04E4B0,
    0x9D04E498: 0x9D04E4B0, 0x9D04E45C: 0x9D04E4B0,
}
OVERLAY = {a: ('j', b) for a, b in GATES.items()}
OVERLAY.update({0x9D04DAF4: ('j', CAPTURE), 0x9D04DFA0: ('j', ORDER),
                0x9D04DE68: ('j', ADAPT_A), 0x9D04DFBC: ('j', ADAPT_B)})

def signed(v):
    return v if v < 0x80000000 else v - 0x100000000

def decode(pc):
    w = struct.unpack_from('<I', IMAGE, pc-BASE)[0]
    op, rs, rt, rd, sa, fn = w >> 26, (w >> 21)&31, (w >> 16)&31, (w >> 11)&31, (w >> 6)&31, w&63
    im = w&0xFFFF
    si = im if im < 0x8000 else im-0x10000
    s,t,d = REGS[rs],REGS[rt],REGS[rd]
    if w == 0: return ('nop',)
    if op == 0:
        if fn == 8: return ('jr', s)
        if fn == 0: return ('sll', d,t,sa)
        name = {10:'movz',11:'movn',33:'addu',35:'subu',43:'sltu'}.get(fn)
        if name: return (name,d,s,t)
    if op in (2,3): return ('j' if op == 2 else 'jal', ((pc+4)&0xF0000000)|((w&0x3FFFFFF)<<2))
    if op in (4,5,20,21): return ({4:'beq',5:'bne',20:'beql',21:'bnel'}[op],s,t,pc+4+si*4)
    if op == 15: return ('lui',t,im)
    if op in (9,11,12): return ({9:'addiu',11:'sltiu',12:'andi'}[op],t,s, im if op==12 else si)
    if op in (35,37,41,43): return ({35:'lw',37:'lhu',41:'sh',43:'sw'}[op],t,si,s)
    raise AssertionError(f'Unhandled reachable instruction {pc:08x} {w:08x}')

class Machine:
    def __init__(self, layers, osc, flag, gate, custom=(0,0), design=True):
        self.r = [0]*32
        self.r[R['sp']] = 0x80070000
        self.r[R['gp']] = 0x80008000
        for n in range(16,24): self.r[n] = 0x11110000+n
        self.m, self.events, self.steps, self.design = {}, [], 0, design
        self.osc = osc
        self.write(GATE,gate,2)
        for part, values in enumerate(layers):
            for id,val in zip((7,9,15,5), values): self.write(self.slot(part,id+osc*0x41),val,2)
            self.write(self.slot(part,17+osc*0x41),custom[part],2)
        self.flag = flag
    def slot(self,part,id): return PARAM+2*(id+part*0x6B7)
    def read(self,a,n): return sum(self.m.get(a+i,0)<<(8*i) for i in range(n))
    def write(self,a,v,n):
        for i in range(n): self.m[a+i] = (v>>(8*i))&255
    def get(self,n): return self.r[R[n]]
    def set(self,n,v):
        if n != 'zero': self.r[R[n]] = v&0xFFFFFFFF
    def instruction(self,pc):
        if self.design and pc in OVERLAY: return OVERLAY[pc]
        if pc in BLOCKS: return BLOCKS[pc]
        return decode(pc)
    def simple(self,row):
        op,*a = row
        g,s = self.get,self.set
        if op=='nop': return
        if op=='move': s(a[0],g(a[1]))
        elif op=='li': s(a[0],a[1])
        elif op=='lui': s(a[0],a[1]<<16)
        elif op=='addiu': s(a[0],g(a[1])+a[2])
        elif op=='sltiu': s(a[0],int(g(a[1])<(a[2]&0xFFFFFFFF)))
        elif op=='andi': s(a[0],g(a[1])&a[2])
        elif op=='sll': s(a[0],g(a[1])<<a[2])
        elif op=='addu': s(a[0],g(a[1])+g(a[2]))
        elif op=='subu': s(a[0],g(a[1])-g(a[2]))
        elif op=='sltu': s(a[0],int(g(a[1])<g(a[2])))
        elif op in ('movn','movz'):
            if (g(a[2])!=0)==(op=='movn'): s(a[0],g(a[1]))
        elif op in ('lw','lhu'): s(a[0],self.read(g(a[2])+a[1],4 if op=='lw' else 2))
        elif op in ('sw','sh'):
            addr=g(a[2])+a[1];value=g(a[0]);self.write(addr,value,4 if op=='sw' else 2)
            if op=='sh' and PARAM<=addr<PARAM+2*0xD6E:
                index=(addr-PARAM)//2;part=int(index>=0x6B7);id=index-part*0x6B7
                self.events.append(('store',part,id,value&65535))
        else: raise AssertionError(row)
    def external(self,pc):
        g=self.get
        if pc==0x9D04D4FC:
            id,value=g('a1'),g('a2')
            maximum=struct.unpack_from('<H',IMAGE,0x47498+id*12)[0]
            answer=min(value,maximum)
            if id in (11,76) and answer==0: answer=1
        elif pc in (0x9D04F510,0x9D04F48C):
            part,id=(g('a1'),g('a2')) if pc==0x9D04F510 else (1,g('a1'))
            assert part in (0,1)
            self.events.append(('engine',part,id,self.read(self.slot(part,id),2)))
            answer=0
        elif pc==0x9D04D7B8:
            part,id=g('a0'),g('a1')
            assert part in (0,1)
            # MIDI helper invocation; actual transport depends on mappings/cache.
            self.events.append(('midi-helper',part,id,self.read(self.slot(part,id),2)))
            answer=0
        elif pc==0x9D01E434:
            self.events.append(('custom-ui',g('a0'),g('a1'),g('a2')))
            answer=0
        else: return False
        ra=g('ra')
        for n in list(range(2,16))+[24,25]: self.r[n]=(0xBAD00000+n)&0xFFFFFFFF
        self.set('v0',answer)
        self.set('ra',ra)
        return True
    def edit(self,selector,id,request):
        before=self.r.copy()
        self.set('a0',self.flag);self.set('a1',selector);self.set('a2',id);self.set('a3',request)
        stop=0x90000000;self.set('ra',stop);pc=ENTRY
        start_steps=self.steps
        while pc!=stop:
            self.steps+=1
            assert self.steps-start_steps<5000, hex(pc)
            if self.external(pc): pc=self.get('ra');continue
            row=self.instruction(pc);op=row[0]
            if op in ('j','jal','jr','beq','bne','beql','bnel'):
                if op in ('beq','bne','beql','bnel'):
                    take=(self.get(row[1])==self.get(row[2]))==(op in ('beq','beql'))
                    target=row[3] if take else pc+8
                    if not take and op.endswith('l'): pc+=8;continue
                else:
                    target=self.get(row[1]) if op=='jr' else row[1]
                    if op=='jal': self.set('ra',pc+8)
                self.simple(self.instruction(pc+4));self.steps+=1;pc=target
            else: self.simple(row);pc+=4
        for n in list(range(16,24))+[28,29,30]: assert self.r[n]==before[n], (REGS[n],hex(self.r[n]),hex(before[n]))
        assert self.get('ra')==stop
    def values(self,part):
        return tuple(self.read(self.slot(part,id+self.osc*0x41),2) for id in (7,9,15,5,17))

def oracle(values,kind,req,selected):
    s,e,c,loop,custom=values
    if not selected: return values
    accepted=min(req,e,999) if kind==7 else min(max(req,s),999)
    if kind==7: s=accepted
    else: e=accepted
    if loop and ((kind==7 and accepted>c) or (kind==9 and accepted<c)): c=accepted
    return s,e,c,loop,custom

def run():
    assert [id for id in range(0x6B6)
            if (((id if id<0x41 else id-0x41)-7)&0xFFFFFFFF)&0xFFFD==0]==[7,9,72,74]
    windows=[(0,999,499),(100,400,250),(600,900,750),(400,400,400)]
    requests=(0,1,99,100,249,250,399,400,401,499,600,750,900,998,999,1000,65535)
    count=0
    for osc,selector,kind,wa,wb,loops,flag,gate in itertools.product(
            (0,1),(0,1,2),(7,9),windows,windows,itertools.product((0,1),repeat=2),(0,1),(0,1)):
        for req in requests:
            layers=[(*wa,loops[0]),(*wb,loops[1])]
            m=Machine(layers,osc,flag,gate,custom=(0,0))
            initial=[m.values(p) for p in (0,1)]
            m.edit(selector,kind+osc*0x41,req)
            selected=(selector in (0,2),selector in (1,2))
            for p in (0,1):
                expected=oracle(initial[p],kind,req,selected[p])
                assert m.values(p)[:4]==expected[:4], (osc,selector,kind,layers,req,p,m.values(p),expected)
                assert m.values(p)[0]<=m.values(p)[1]
                assert m.values(p)[4]==int(selected[p])  # initial A custom=0 linked enables both
                stores=[x for x in m.events if x[0]=='store' and x[1]==p and x[2]==kind+osc*0x41]
                assert len(stores)==int(selected[p])
            engines=[x for x in m.events if x[0]=='engine' and x[2] in (kind+osc*0x41,15+osc*0x41)]
            assert bool(engines)==bool(flag or gate)
            mids=[x for x in m.events if x[0]=='midi-helper' and x[2] in (kind+osc*0x41,15+osc*0x41)]
            assert bool(mids)==(flag==0)
            for p in (0,1):
                seq=[x[2] for x in engines if x[1]==p]
                assert seq.count(kind+osc*0x41)==int(selected[p] and bool(flag or gate))
                if 15+osc*0x41 in seq:
                    assert seq.index(15+osc*0x41)<seq.index(kind+osc*0x41)
            # Persistent push and retreat: captured request is refreshed per call.
            saved=[m.values(p)[2] for p in (0,1)]
            m.edit(selector,kind+osc*0x41,0 if kind==7 else 999)
            assert [m.values(p)[2] for p in (0,1)]==saved
            count+=1
    # Existing mismatch in custom flags remains identical to stock, rather than
    # quietly broadening the linked side-effect behavior.
    side_cases=0
    for osc,sel,kind,custom in itertools.product((0,1),(0,1,2),(7,9),itertools.product((0,1),repeat=2)):
        args=([(100,400,250,1),(600,900,750,0)],osc,0,0,custom)
        old=Machine(*args,design=False);new=Machine(*args)
        old.edit(sel,kind+osc*0x41,350);new.edit(sel,kind+osc*0x41,350)
        assert [old.values(p)[4] for p in (0,1)]==[new.values(p)[4] for p in (0,1)]
        side_cases+=1
    # Direct Center edits unchanged, including linked stock semantics.
    centers=0
    for osc,sel,loops,req,flag,gate in itertools.product((0,1),(0,1,2),itertools.product((0,1),repeat=2),requests,(0,1),(0,1)):
        args=([(100,400,250,loops[0]),(600,900,750,loops[1])],osc,flag,gate)
        old=Machine(*args,design=False);new=Machine(*args)
        old.edit(sel,15+osc*0x41,req);new.edit(sel,15+osc*0x41,req)
        assert [old.values(p) for p in (0,1)]==[new.values(p) for p in (0,1)]
        assert old.events==new.events
        centers+=1
    # Regression and independence examples.
    examples=[]
    for kind,wa,wb,req in [(7,(0,900,499),(0,400,200),600),
                           (7,(0,400,200),(0,900,499),600),
                           (9,(100,999,499),(600,999,750),400),
                           (9,(600,999,750),(100,999,499),400)]:
        m=Machine([(*wa,1),(*wb,1)],0,0,0);m.edit(2,kind,req)
        examples.append({'kind':kind,'request':req,'A':m.values(0),'B':m.values(1)})
    # Single-part redispatch reference: same original request, valid window
    # outcomes agree; custom flags can differ from the original linked path.
    redispatch=0
    custom_differences=0
    for osc,kind,wa,wb,loops,req in itertools.product((0,1),(7,9),windows,windows,itertools.product((0,1),repeat=2),(0,400,600,999,1000)):
        args=([(*wa,loops[0]),(*wb,loops[1])],osc,0,0,(1,0))
        narrow=Machine(*args);split=Machine(*args)
        narrow.edit(2,kind+osc*0x41,req)
        split.edit(0,kind+osc*0x41,req);split.edit(1,kind+osc*0x41,req)
        assert [narrow.values(p)[:4] for p in (0,1)]==[split.values(p)[:4] for p in (0,1)]
        assert split.values(1)[4]==1
        custom_differences+=int(narrow.values(1)[4]!=split.values(1)[4])
        redispatch+=1
    stock_fault=Machine([(0,900,499,1),(0,400,200,1)],0,0,0,design=False)
    # With stock Center gates the linked bug is also exposed by an A Center
    # beyond B End; the hardware's loaded preset can have this configuration.
    stock_fault.write(stock_fault.slot(0,15),800,2)
    stock_fault.edit(2,7,600)
    assert stock_fault.values(1)[0]>stock_fault.values(1)[1]
    return {'status':'PASS','endpoint_cases_with_retreat':count,
            'direct_center_equivalence_cases':centers,'custom_side_effect_equivalence_cases':side_cases,
            'single_part_redispatch_comparison_cases':redispatch,
            'redispatch_custom_side_effect_differences':custom_differences,
            'stock_linked_bug_reproduced_raw_values':stock_fault.values(1),
            'symbolic_instructions':len(BLOCKS),'symbolic_inserted_bytes':4*len(BLOCKS),
            'planning_extent':[hex(CAPTURE),hex(PUSH_END)],'examples':examples,
            'limitations':['External descriptor/output/UI callees are contract summaries, not transport simulation.',
                          'No firmware assembled, patched, built, or packaged.',
                          'Placement bytes checked separately; indirect references/boot vector safety require review.']}

if __name__=='__main__': print(json.dumps(run(),indent=2))

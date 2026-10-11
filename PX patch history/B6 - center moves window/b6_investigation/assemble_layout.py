"""Standalone B6 words and sparse-overlay host model. Never writes firmware."""
from pathlib import Path
import sys, struct, hashlib, json
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import b7_combined_instruction_model as m
pic=(ROOT/'b7_candidate_work/pic_2.2.2.0.8.bin').read_bytes()
package=(ROOT/'PxUpdate_V2.2.2.0.8.bin').read_bytes()
assert hashlib.sha256(package).hexdigest()=='c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f'
p=1;parts=[]
for typ in (1,2,3):
    h=package[p:p+12];assert h[:2]==bytes((typ,123))
    n=int.from_bytes(h[8:12],'big');parts.append(package[p+12:p+12+n]);p+=n+14
assert p==len(package)-1 and parts[2]==pic
assert hashlib.sha256(pic).hexdigest()=='3554fc3dc413c05fd329df1d04efd1ea49e27469121b38d140b7ebdf3be2e254'
m.IMAGE=pic
R=m.R
# Reuse only B7's bounded assembler definition, never its build/packaging code.
source=(ROOT/'b7_candidate_work/build_validate_b7.py').read_text()
namespace={'r':R}
exec(source[source.index('def assemble('):source.index('\npic=bytearray')],namespace)
assemble=namespace['assemble']

# Relocatable standalone assembly source. One word per tuple, labels cost zero.
CODE=[
('entry:',),
('li','t0',15),('beq','s0','t0','work'),('nop',),
('li','t0',80),('bne','s0','t0','resume'),('nop',),
('work:',),('addiu','sp','sp',-48),
('sw','s0',16,'sp'),('sw','s1',20,'sp'),('sw','s2',24,'sp'),
('sw','s3',28,'sp'),('sw','s4',32,'sp'),('sw','s6',36,'sp'),('sw','ra',40,'sp'),
('andi','s0','s2',1),('li','s6',999),('sltiu','t0','a3',1000),('movn','s6','a3','t0'),
('part:',),('lw','t0',16,'sp'),('sll','t0','t0',1),
('lui','s1',0x8000),('addiu','s1','s1',0x46c),('addu','s1','s1','t0'),
('beq','s0','zero','pointer_ready'),('nop',),('addiu','s1','s1',0xd6e),
('pointer_ready:',),('lhu','t0',-20,'s1'),('beq','t0','zero','next_part'),('nop',),
('lhu','t1',-16,'s1'),('lhu','t2',-12,'s1'),
('subu','s4','s6','t1'),('sltu','t0','s6','t1'),('bne','t0','zero','left'),('nop',),
('subu','s4','s6','t2'),('sltu','t0','t2','s6'),('beq','t0','zero','next_part'),('nop',),
('lw','s2',16,'sp'),('addiu','s2','s2',-6),('li','s3',-2),
('addu','t1','t1','s4'),('addu','t2','t2','s4'),
('sh','t2',-12,'s1'),('sh','t1',-16,'s1'),('j','notify_setup'),('nop',),
('left:',),('lw','s2',16,'sp'),('addiu','s2','s2',-8),('li','s3',2),
('addu','t1','t1','s4'),('addu','t2','t2','s4'),
('sh','t1',-16,'s1'),('sh','t2',-12,'s1'),
('notify_setup:',),('li','s4',2),
('notify:',),('bne','s5','zero','engine'),('nop',),
('lui','t0',0x8000),('lhu','t0',0x6ffe,'t0'),('beq','t0','zero','midi'),('nop',),
('engine:',),('move','a0','s5'),('move','a1','s0'),('jal',0x9d04f510),('move','a2','s2'),
('midi:',),('bne','s5','zero','notified'),('nop',),
('move','a0','s0'),('jal',0x9d04d7b8),('move','a1','s2'),
('notified:',),('addiu','s4','s4',-1),('bne','s4','zero','notify'),('addu','s2','s2','s3'),
('next_part:',),('lw','t0',24,'sp'),('li','t1',2),
('bne','t0','t1','restore'),('nop',),('bne','s0','zero','restore'),('nop',),
('li','s0',1),('j','part'),('nop',),
('restore:',),('move','a0','s5'),('lw','a1',24,'sp'),('lw','a2',16,'sp'),('lw','a3',64,'sp'),
('lw','s0',16,'sp'),('lw','s1',20,'sp'),('lw','s2',24,'sp'),('lw','s3',28,'sp'),
('lw','s4',32,'sp'),('lw','s6',36,'sp'),('lw','ra',40,'sp'),('addiu','sp','sp',48),
('resume:',),('j',0x9d04dafc),('li','v0',80),
]

def layout(base):
    labels={};pc=base
    for row in CODE:
        if row[0].endswith(':'):labels[row[0][:-1]]=pc
        else:pc+=4
    rows={};words={};pc=base
    for row in CODE:
        if row[0].endswith(':'):continue
        row=tuple(labels.get(x,x) if isinstance(x,str) else x for x in row)
        if row[0]=='lui':word=15<<26|R[row[1]]<<16|row[2]
        else:word=assemble(pc,row)
        rows[pc]=row;words[pc]=word;pc+=4
    return labels,rows,words

# This virtual address is for standalone size/ABI validation only. Placement
# is NOT asserted safe by layout(). It is the one bounded extra region checked.
BASE=0x9d000c00
labels,rows,words=layout(BASE)
hook=assemble(0x9d001224,('j',BASE))
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,0x1224)[0])).hexdigest()=='1eada8c9665036a19c6d8696edb9251c9c0b1230117bba3a6241a8ed24b88c6e'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,0x1228)[0])).hexdigest()=='840f37e17d061f31105a15dda1aab1e26f21efd59855070d58417023d332894b'
overlay={**words,0x9d001224:hook}

def decode(pc):
    # Independent raw-word decoder; execution never reads assembly tuples.
    w=overlay.get(pc)
    if w is None:w=struct.unpack_from('<I',pic,pc-m.BASE)[0]
    op,rs,rt,rd,sa,fn=w>>26,(w>>21)&31,(w>>16)&31,(w>>11)&31,(w>>6)&31,w&63
    imm=w&65535;si=imm if imm<32768 else imm-65536
    regs=m.REGS;s,t,d=regs[rs],regs[rt],regs[rd]
    if w==0:return ('nop',)
    if op==0:
        if fn==8:return ('jr',s)
        if fn==0:return ('sll',d,t,sa)
        names={10:'movz',11:'movn',33:'addu',35:'subu',43:'sltu'}
        if fn in names:return (names[fn],d,s,t)
    if op in (2,3):return ('j' if op==2 else 'jal',((pc+4)&0xf0000000)|((w&0x3ffffff)<<2))
    if op in (4,5,20,21):return ({4:'beq',5:'bne',20:'beql',21:'bnel'}[op],s,t,pc+4+si*4)
    if op==15:return ('lui',t,imm)
    if op in (9,11,12):return ({9:'addiu',11:'sltiu',12:'andi'}[op],t,s,imm if op==12 else si)
    if op in (35,37,41,43):return ({35:'lw',37:'lhu',41:'sh',43:'sw'}[op],t,si,s)
    raise AssertionError((hex(pc),hex(w)))

control={'j','jal','jr','beq','bne','beql','bnel'}
for pc in words:
    row=decode(pc)
    if row[0] in control:
        assert pc+4 in words and decode(pc+4)[0] not in control
        if row[0] in ('beq','bne'):assert row[3] in words

class Machine(m.Machine):
    def instruction(self,pc):return decode(pc)
    def simple(self,row):
        super().simple(row)
        if row[0]=='sh':
            for part in (0,1):assert self.values(part)[0]<=self.values(part)[1]

def targeted_regressions():
    class EntryMachine(Machine):
        def instruction(self,pc):
            if pc==0x9d001224:
                self.entry_state=self.r.copy()
                # The preserved hook delay slot sets s2 to the selector.
                self.entry_state[R['s2']]=self.get('a1')
                self.request_slot=self.read(self.get('sp')+16,4)
            if pc==0x9d04dafc:
                for name in ('a0','a1','a2','a3','s0','s1','s2','s3','s4','s5','s6','s7','gp','sp','fp','ra'):
                    assert self.get(name)==self.entry_state[R[name]],name
                assert self.get('v0')==80
                assert self.read(self.get('sp')+16,4)==self.request_slot
            return super().instruction(pc)
        def external(self,pc):
            if pc in (0x9d04f510,0x9d04f48c,0x9d04d7b8):
                # The o32 outgoing home area may be overwritten by callees.
                for offset in range(0,16,4):self.write(self.get('sp')+offset,0xdeadbeef,4)
            return super().external(pc)
    count=0
    for osc in (0,1):
      for selector in (0,1,2):
       for loops in ((0,0),(0,1),(1,0),(1,1)):
        for flag,gate in ((0,0),(0,1),(1,0),(1,1)):
         for id in (7,9,11,15,17):
          for req in (0,450,700,999,65535):
           initial=[(200,600,450,loops[0]),(700,900,800,loops[1])]
           new=EntryMachine(initial,osc,flag,gate,custom=(1,0),design=False)
           new.edit(selector,id+osc*0x41,req)
           if id!=15:
               stock=m.Machine(initial,osc,flag,gate,custom=(1,0),design=False)
               stock.edit(selector,id+osc*0x41,req)
               assert [new.values(i) for i in (0,1)]==[stock.values(i) for i in (0,1)]
               assert new.events==stock.events
           count+=1
    return count

def expected(values,selector,req):
    out=[];events=[]
    for part,(s,e,c,loop,custom) in enumerate(values):
        selected=selector==2 or selector==part
        if selected and loop:
            q=min(req,999);d=q-s if q<s else q-e if q>e else 0
            d=max(-s,min(d,999-e));ns,ne=s+d,e+d
            if d:
                for id,val in ((9,ne),(7,ns)) if d>0 else ((7,ns),(9,ne)):
                    events.append((part,id,val))
            s,e=ns,ne
        out.append([s,e,c,loop,custom])
    # The stock linked Center path passes A's accepted raw request to B.
    # A loop-on translation makes min(req,999) fit; loop-off preserves stock.
    accepted=req
    for part in (0,1):
        if selector!=2 and selector!=part:continue
        s,e,c,loop,custom=out[part]
        if loop:accepted=max(s,min(accepted,e))
        out[part][2]=min(accepted,999)
    return out,events

windows=[(0,999,499),(200,600,450),(700,900,800),(400,400,400),(0,100,50),(900,999,950)]
requests=[0,1,199,200,399,400,600,601,900,998,999,1000,65535,0xffffffff]
cases=0
for osc in (0,1):
 for selector in (0,1,2):
  for wa in windows:
   for wb in windows:
    for loops in ((0,0),(0,1),(1,0),(1,1)):
     for custom in ((0,0),(0,1),(1,0),(1,1)):
      initial=[(*wa,loops[0]),(*wb,loops[1])]
      for flag,gate in ((0,0),(0,1),(1,0),(1,1)):
       for req in requests:
        machine=Machine(initial,osc,flag,gate,custom=custom,design=False)
        oracle,ends=expected([(*initial[i],custom[i]) for i in (0,1)],selector,req)
        machine.edit(selector,15+osc*0x41,req)
        actual=[machine.values(i) for i in (0,1)]
        assert [v[:4] for v in actual]==[tuple(v[:4]) for v in oracle],(initial,selector,req,actual,oracle)
        # Compare custom flags to exact .8's original Center setter; no split.
        original_overlay=overlay.copy();overlay.clear()
        stock=m.Machine(initial,osc,flag,gate,custom=custom,design=False)
        stock.edit(selector,15+osc*0x41,req)
        overlay.update(original_overlay)
        assert [v[4] for v in actual]==[stock.values(i)[4] for i in (0,1)]
        end_engine=[(p,id-osc*0x41,val) for kind,p,id,val in machine.events if kind=='engine' and id-osc*0x41 in (7,9)]
        end_midi=[(p,id-osc*0x41,val) for kind,p,id,val in machine.events if kind=='midi-helper' and id-osc*0x41 in (7,9)]
        assert end_engine==(ends if flag or gate else [])
        assert end_midi==(ends if flag==0 else [])
        # No Center output precedes either endpoint's output during translation.
        relevant=[(kind,p,id-osc*0x41,val) for kind,p,id,val in machine.events if kind in ('engine','midi-helper') and id-osc*0x41 in (7,9,15)]
        for part in (0,1):
            for kind in ('engine','midi-helper'):
                ids=[id for k,p,id,v in relevant if k==kind and p==part]
                assert 15 not in ids or all(id==15 for id in ids[ids.index(15):])
        cases+=1

padding=[(0x122c,0x1240),(0x129c,0x12c0),(0x12e8,0x12f0),(0x1318,0x1320),(0x1394,0x1480)]
assert all(pic[a:z]==b'\xff'*(z-a) for a,z in padding)
report={'package_sha256':hashlib.sha256(package).hexdigest(),
 'instructions':len(words),'code_bytes':4*len(words),'hook_words':1,
 'private_frame_bytes':48,'host_cases':cases,'targeted_entry_ABI_and_B7_cases':targeted_regressions(),'padding_bytes':sum(z-a for a,z in padding),
 'fits_verified_padding':4*len(words)<=sum(z-a for a,z in padding),
 'standalone_test_base':hex(BASE),'standalone_test_end':hex(BASE+4*len(words)),
 'placement_verified':False,'delay_slots':'checked; no control transfer in a delay slot',
 'ABI':'parent request slot retained; callee-saved/GP/SP/RA checked with volatile clobbers',
 'limitations':'External engine/MIDI/custom functions use B7 summaries; no firmware image or package written.'}
(OUT/'standalone_layout.txt').write_text('\n'.join(f'{pc:08X} {words[pc]:08X} {rows[pc]!r} decoded={decode(pc)!r}' for pc in words)+'\n')
(OUT/'layout_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

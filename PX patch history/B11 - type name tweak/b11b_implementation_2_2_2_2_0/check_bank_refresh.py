"""Execute stock PIC bank-delete completion and debug reload dispatch.
Library/UI/flash I/O are controlled callbacks. No firmware image writes.
"""
from pathlib import Path
import json
from setter_harness import CPU
ROOT=Path(__file__).resolve().parent
BASE=0x80037e90
ui=0x80050000; event=0x80051000; ret=0x9d0267c0
# Extended-format count page: marker FF, then 65*17 raw real counts.
raw=[0]*(65*17)
raw[2]=3;raw[17*10]=2;raw[17*34+4]=1
page=bytes([255]+raw)
state={'counts_refreshed':False,'names_refreshed':False,'deleted':False,'reads':0}
def delete(c):
 assert c.r[4:6]==[0,1]
 state['deleted']=True
 c.r[2]=0
def counts(c):
 assert state['deleted'];state['counts_refreshed']=True
 assert c.load(BASE+8*(17+5),4)==2
 c.r[2]=0
def names(c):
 assert state['counts_refreshed'];state['names_refreshed']=True
 c.r[2]=0
def flash(c):
 assert state['names_refreshed']
 offset=c.r[4]-0x5fd000
 assert 0<=offset<len(page),hex(c.r[4])
 c.r[2]=page[offset];state['reads']+=1
noop=lambda c:None
callbacks={a:noop for a in (0x9d07e274,0x9d068d64,0x9d07e3dc,0x9d075c1c,0x9d04d764,0x9d0426c0,0x9d045bd8,0x9d03ec50,0x9d01b46c,0x9d03ed0c)}
callbacks.update({0x9d0798d8:delete,0x9d079744:lambda c:c.r.__setitem__(2,0),0x9d042a8c:counts,0x9d042b80:names,0x9d040a4c:flash})
c=CPU(callbacks=callbacks);c.r[4]=ui;c.r[5]=event;c.r[31]=ret
saved=tuple(c.r[16:24]);sp=c.r[29]
c.store(event,2,4);c.store(event+4,1,14);c.store(event+5,1,1)
c.store(ui+0xc4,2,0)
for row in range(65*17):c.store(BASE+8*row,4,2);c.store(BASE+8*row+4,4,1234)
c.run(0x9d01b61c,{ret},limit=100000)
assert 0x9d040ed8 in c.trace
assert c.r[29]==sp and tuple(c.r[16:24])==saved
cumulative=0
for row,n in enumerate(raw):
 assert c.load(BASE+8*row,4)==n+1,(row,n)
 assert c.load(BASE+8*row+4,4)==(cumulative if n else 0xffffffff),row
 cumulative+=n+1
assert c.load(0x8004a118+4,4)==0
order=[a for a,_ in c.calls if a in (0x9d0798d8,0x9d079744,0x9d042a8c,0x9d042b80)]
assert order==[0x9d0798d8,0x9d079744,0x9d042a8c,0x9d042b80]

# Actual debug menu event dispatch: Confirm (12), press, item 3.
d=CPU(callbacks={a:noop for a in (0x9d075c1c,0x9d042a8c,0x9d042b80,0x9d01ab84)})
d.r[4]=ui;d.r[5]=event;d.r[31]=ret;d.store(event,2,4);d.store(event+4,1,12);d.store(event+5,1,1);d.store(ui+0xc0,2,3)
d.run(0x9d021b00,{ret})
assert 0x9d022760 in d.trace and 0x9d040ed8 not in d.trace
assert [a for a,_ in d.calls]==[0x9d075c1c,0x9d042a8c,0x9d042b80,0x9d075c1c,0x9d01ab84]
summary={'stock_bank_delete_dispatch':'PASS: button 14 press enters bank deletion; stock mapper selects group 1','stock_bank_delete_cache_builder':'PASS: actual expanded builder executes after count/name completion, before UI return','expanded_cache_rows_verified':65*17,'flash_byte_reads':state['reads'],'bank_availability_word':'PASS: selected bank availability refreshed to zero','debug_reload_dispatch':'PASS: Confirm press on item 3 invokes 9D022760; no expanded builder call','external_effects':'deletion, count/name refresh, UI and flash byte reads are controlled callbacks; actual PIC dispatch and cache builder execute','hardware':'owner confirms complete User-bank deletion refreshes category files and immediately skips deleted bank on .1.15','firmware_modified':False}
(ROOT/'bank_refresh_results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

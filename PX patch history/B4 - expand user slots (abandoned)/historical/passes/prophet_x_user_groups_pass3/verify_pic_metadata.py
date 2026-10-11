# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import json,struct
from unicorn import *
from unicorn.mips_const import *
b=Path('pic.bin').read_bytes()
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
STOP=0x9d0817f0;GP=0x80007ff0
def rd(p,n):return bytes(u.mem_read(p&0x1fffffff,n))
def wr(p,v):u.mem_write(p&0x1fffffff,v)
def run(pc,args=(),limit=40000000):
 u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_RA,STOP);u.reg_write(UC_MIPS_REG_GP,GP)
 for r,a in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2],args):u.reg_write(r,a)
 u.emu_start(pc,STOP,count=limit);assert u.reg_read(UC_MIPS_REG_PC)==STOP,hex(u.reg_read(UC_MIPS_REG_PC));return u.reg_read(UC_MIPS_REG_V0)
# Actual browsing reorder functions form a permutation for IDs0..64.
forward=[run(0x9d080e2c,[i]) for i in range(65)]
reverse=[run(0x9d080e60,[i]) for i in range(65)]
assert sorted(forward)==list(range(65))
assert all(reverse[forward[i]]==i for i in range(65))
assert all(run(f,[i])==64 for f in [0x9d080e2c,0x9d080e60] for i in [65,96,127,128,132,255])
labels=[]
for i in range(132):
 p=struct.unpack_from('<I',b,0x63f60+4*i)[0]-0x9d000000
 assert 0<=p<len(b)
 labels.append(b[p:p+32].split(b'\0')[0].decode())
assert labels==[f'User {i}' for i in range(1,9)]+[f'Purchased {i}' for i in range(1,33)]+[f'User {i}' for i in range(9,101)]
# Actual name-record builder, mock external UI and serial-memory operations.
# Mock count query and name replies. File/flash device acceptance is not tested.
st={};stubs={0x9d0689d8,0x9d07e274,0x9d068d64,0x9d07e3dc,0x9d05f770,0x9d08169c,0x9d0811c4,0x9d0421ac,0x9d042340,0x9d079978,0x9d079340}
def hook(uc,pc,size,data):
 if pc not in stubs:return
 a0=uc.reg_read(UC_MIPS_REG_A0);a1=uc.reg_read(UC_MIPS_REG_A1)
 ret=0
 if pc==0x9d079978:
  st['queries']+=1;ret=st['count']
 elif pc==0x9d079340:
  st['names']+=1;wr(0x80037e3c,bytes([st['names']%251])*46)
 elif pc==0x9d0421ac:st['erases'].append(a0)
 elif pc==0x9d042340:
  st['writes']+=1;st['minwrite']=min(st['minwrite'],a0);st['maxwrite']=max(st['maxwrite'],a0)
 uc.reg_write(UC_MIPS_REG_V0,ret);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
h=u.hook_add(UC_HOOK_CODE,hook)
results=[]
for groups,count in [(65,0),(97,0),(97,1),(97,255)]:
 wr(0x9d042d9c,struct.pack('<I',0x24020000|groups))
 u.ctl_flush_tb()
 st.clear();st.update(count=count,queries=0,names=0,erases=[],writes=0,minwrite=0xffffffff,maxwrite=0)
 run(0x9d042b80)
 expected=min(groups*17*(count+1),65536)
 assert st['names']==expected,(st,expected)
 assert st['minwrite']==0xc00000 and st['maxwrite']<0x1000000
 results.append({'groups':groups,'instruments_each_category':count,'requested_records':groups*17*(count+1),'built_records':st['names'],'written_pages_256_bytes':st['writes'],'last_page':hex(st['maxwrite']),'capacity_truncated':groups*17*(count+1)>65536})
 print(results[-1],flush=True)
u.hook_del(h)
# Demonstrate precise first-extra-row collision with size cache.
for i in range(65):wr(0x8003a118+4*i,struct.pack('<I',0x11223344+i))
wr(0x80037e90+65*17*8,struct.pack('<I',2))
assert struct.unpack('<I',rd(0x8003a118,4))[0]==2
out={'stock_selector_forward':forward,'stock_selector_inverse':reverse,'labels':labels,'name_builder':results,'first_extra_row_overwrites_group_size_cache':True}
Path('branch4/pic_metadata_results.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS: actual remappers, 132 labels, name builder/capacity and table collision')

# SPDX-License-Identifier: GPL-2.0-or-later
import runpy,json,struct
from pathlib import Path
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
x=runpy.run_path('branch4/verify_qnx_import_bound.py');u=x['u'];STOP=x['STOP']
OBJECT=0x73000000;u.mem_map(OBJECT,0x10000)
writes=[]
def capture(uc,access,addr,size,value,data):
 if OBJECT<=addr<OBJECT+0x33d0:writes.append((addr-OBJECT,size,value))
h=u.hook_add(UC_HOOK_MEM_WRITE,capture)
results=[]
for group,category in [(64,0),(65,0),(0xffffffff,0xffffffff)]:
 u.mem_write(OBJECT,bytes(0x10000));writes.clear()
 sp=0x7001fff0;u.mem_write(sp,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,sp)
 for reg,val in [(UC_X86_REG_RDI,OBJECT),(UC_X86_REG_RSI,group),(UC_X86_REG_RDX,category)]:u.reg_write(reg,val)
 u.emu_start(0x33ca0,STOP,count=100000);assert u.reg_read(UC_X86_REG_RIP)==STOP
 counts=[a for a,n,v in writes if n==4 and a<0x1148];pointers=[a for a,n,v in writes if n==8 and a>=0x1148]
 expected=1 if group==64 else 17
 assert len(counts)==expected and len(pointers)==expected
 results.append({'group_argument':hex(group),'category_argument':hex(category),'count_entries_cleared':len(counts),'pointer_entries_cleared':len(pointers)})
u.hook_del(h)
Path('branch4/qnx_release_bound_results.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: actual release routine; group65 enters broad-release branch and clears factory17 in zero-pointer fixture')

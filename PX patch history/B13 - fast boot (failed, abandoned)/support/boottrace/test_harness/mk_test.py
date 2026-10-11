# SPDX-License-Identifier: GPL-2.0-or-later
import re, struct, subprocess
from pathlib import Path
import argparse, os
parser = argparse.ArgumentParser(description='Generate boottrace host harness inputs in a private work directory.')
parser.add_argument('--work-dir', type=Path, required=True, help='Directory containing assembled stubs.bin')
args = parser.parse_args()
S = str(Path(__file__).resolve().parents[1] / 'source')
os.chdir(args.work_dir.resolve())
blob=open('stubs.bin','rb').read()
magic=struct.pack('<Q',0xDEADBEEFCAFEF00D); mo=blob.index(magic)
names=['procmgr','comopen','comrts','ctor','index','cacheinfo','preload','newarr','workers','vt0','vt8','vt10',
       'clock','errno','remove','open','write','close','misalign','clk_n','errno_var']+['rec_'+n for n in
       ['procmgr','comopen','comrts','ctor','index','cacheinfo','preload','newarr','workers','vt0','vt8','vt10']]+['last_open_rsi','last_open_rdx']
vals=struct.unpack_from('<%dQ'%len(names),blob,mo+8)
A=dict(zip(names,vals))
src=open(f'{S}/trace.asm').read()
def sub(name,val):
    global src
    pat=re.compile(r'^(%s\s+equ\s+)\S+'%name,re.M)
    assert pat.search(src),name
    src=pat.sub(lambda m:m.group(1)+hex(val),src)
sub('TS',0x10100000)
sub('PLT_CLOCK',A['clock']); sub('PLT_REMOVE',A['remove']); sub('PLT_OPEN',A['open'])
sub('PLT_WRITE',A['write']); sub('PLT_CLOSE',A['close']); sub('PLT_ERRNO',A['errno'])
sub('T_PROCMGR',A['procmgr']); sub('T_COMOPEN',A['comopen']); sub('T_COMRTS',A['comrts'])
sub('T_CTOR',A['ctor']); sub('T_INDEX',A['index']); sub('T_CACHEINFO',A['cacheinfo'])
sub('T_PRELOAD',A['preload']); sub('T_NEWARR',A['newarr']); sub('T_WORKERS',A['workers'])
assert '"/hd/px_boot_trace.bin"' in src
src=src.replace('"/hd/px_boot_trace.bin"','"out_trace.bin"')
# vtable stubs: harness vtable points to the vt stubs; nothing else to change
open('test_trace.asm','w').write(src)
subprocess.run(['nasm','-f','bin','-DCODE_BASE=0x10000000','-I',S+'/','test_trace.asm','-o','test_trace.bin','-l','test_trace.lst'],check=True)
tb=open('test_trace.bin','rb').read()
mo2=tb.index(magic)
names2=['stamp','flush','w_main','w_serial_beg','w_serial_end','w_ctor','w_index','w_cache_beg','w_preload','w_select_end','w_fpga_open','w_sched','w_workers','w_stream']
labs=struct.unpack_from('<%dQ'%(3*len(names2)+1),tb,mo2+8)
code_end=labs[-1]
open('trace_code.bin','wb').write(tb[:code_end-0x10000000])
hdr=''.join('#define A_%s 0x%xULL\n'%(n,A[n]) for n in names)
hdr+=''.join('#define F_%s 0x%xULL\n'%(n,labs[3*i]) for i,n in enumerate(names2))
open('addrs.h','w').write(hdr)
print('ok code bytes',code_end-0x10000000)

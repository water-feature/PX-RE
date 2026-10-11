"""Execute the firmware's own FDE lookup callback against the trial layout.

QNX dl_iterate_phdr is replaced by its input structure; the callback and all
encoding/lookup routines execute original machine code. No personality call or
exception is raised. Tests zero and nonzero PIE load biases and cache reuse.
"""
from pathlib import Path
from io import BytesIO
import struct, json, os
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
P=Path(__file__).resolve().parent
raw=Path(os.environ.get('PX_CANDIDATE_ELF',P/'unwind_layout_trial.elf')).read_bytes(); elf=ELFFile(BytesIO(raw))
hdr=elf.get_section_by_name('.eh_frame_hdr'); hb=hdr['sh_addr']
count=struct.unpack_from('<I',raw,hb+8)[0]
table=[]
for j in range(count):
    a,f=struct.unpack_from('<ii',raw,hb+12+j*8)
    a+=hb;f+=hb
    size=struct.unpack_from('<I',raw,f+12)[0]
    table.append((a,f,size))
md=Cs(CS_ARCH_X86,CS_MODE_64)
boundaries=[]
for name,a in [('debug_stub.bin',0x49fd0),('hooks_code.bin',0x49fd4),('quiet_code.bin',0x8fed0)]:
    boundaries.extend(i.address for i in md.disasm((P/name).read_bytes(),a))
cases=[(a,f,a) for a,f,n in table]+[(a+n-1,f,a) for a,f,n in table]
for a in boundaries:
    start,ptr,n=next(t for t in table if t[0]<=a<t[0]+t[2])
    cases.append((a,ptr,start))
for a in [0x4a08d,0x8fecf,0x8ff19]:cases.append((a,0,None))
total=0; encoded_checks=0
for bias in [0,0x10000000]:
    uc=Uc(UC_ARCH_X86,UC_MODE_64)
    for s in elf.iter_segments():
        if s['p_type']=='PT_LOAD':
            start=(s['p_vaddr']+bias)&~4095
            end=(s['p_vaddr']+bias+s['p_memsz']+4095)&~4095
            uc.mem_map(start,end-start)
            uc.mem_write(s['p_vaddr']+bias,s.data())
    ARENA=0x40000000; INFO=ARENA; DATA=ARENA+0x100; STOP=ARENA+0x200; STACK=ARENA+0xf000
    uc.mem_map(ARENA,0x10000)
    uc.mem_write(INFO,struct.pack('<QQQH',bias,0,bias+elf['e_phoff'],elf['e_phnum'])+bytes(6)+struct.pack('<QQ',1,0))
    def hook(u,a,size,data):
        if a==bias+0x7220:raise AssertionError('firmware lookup called abort')
        if a==bias+0x7b60:
            p=u.reg_read(UC_X86_REG_RDI); n=0
            while bytes(u.mem_read(p+n,1))!=b'\0':n+=1
            u.reg_write(UC_X86_REG_RAX,n)
            sp=u.reg_read(UC_X86_REG_RSP); ret=struct.unpack('<Q',u.mem_read(sp,8))[0]
            u.reg_write(UC_X86_REG_RSP,sp+8);u.reg_write(UC_X86_REG_RIP,ret)
    uc.hook_add(UC_HOOK_CODE,hook)
    for a,expected,region in cases:
        uc.mem_write(DATA,struct.pack('<QQQQQI',bias+a,0,0,0,0,1))
        uc.mem_write(STACK,struct.pack('<Q',STOP))
        uc.reg_write(UC_X86_REG_RSP,STACK)
        uc.reg_write(UC_X86_REG_RDI,INFO)
        uc.reg_write(UC_X86_REG_RSI,48)
        uc.reg_write(UC_X86_REG_RDX,DATA)
        
        try: uc.emu_start(bias+0x4ea40,STOP,count=100000)
        except Exception:
            print("failure",hex(a),hex(uc.reg_read(UC_X86_REG_RIP)),bytes(uc.mem_read(uc.reg_read(UC_X86_REG_RIP),16)).hex());raise
        assert uc.reg_read(UC_X86_REG_RIP)==STOP
        found=struct.unpack('<Q',uc.mem_read(DATA+32,8))[0]
        assert found==(bias+expected if expected else 0),(hex(bias),hex(a),hex(found),hex(expected))
        if expected:
            found_region=struct.unpack('<Q',uc.mem_read(DATA+24,8))[0]
            assert found_region==bias+region
        total+=1
    # The firmware decoder treats an encoded zero LSDA pointer as NULL;
    # pyelftools currently reports its field address instead. Test the real
    # decoder, including the PIE-adjusted indirect personality pointer slot.
    manifest=json.loads((P/'unwind_manifest.json').read_text())
    meta=int(manifest['metadata_address'],16)
    first_fde=meta+32
    second_fde=first_fde+4+struct.unpack_from('<I',raw,first_fde)[0]
    lsda_field=first_fde+17
    quiet_lsda_field=second_fde+17
    expected_lsda=lsda_field+struct.unpack_from('<i',raw,lsda_field)[0]
    slot=int(manifest['personality_pointer_slot'],16)
    marker=bias+0x123456
    uc.mem_write(bias+slot,struct.pack('<Q',marker))
    for encoding,field,expected in [(0x1b,lsda_field,bias+expected_lsda),(0x1b,quiet_lsda_field,0),(0x9b,meta+19,marker)]:
        uc.mem_write(STACK,struct.pack('<Q',STOP))
        uc.reg_write(UC_X86_REG_RSP,STACK)
        uc.reg_write(UC_X86_REG_RDI,encoding)
        uc.reg_write(UC_X86_REG_RSI,0)
        uc.reg_write(UC_X86_REG_RDX,bias+field)
        uc.reg_write(UC_X86_REG_RCX,DATA)
        uc.emu_start(bias+0x4e5b0,STOP,count=100000)
        assert struct.unpack('<Q',uc.mem_read(DATA,8))[0]==expected
        encoded_checks+=1
result={'lookup_cases':total,'encoded_pointer_cases':encoded_checks,'load_biases':['0x0','0x10000000'],'routine':'stock _Unwind_IteratePhdrCallback 0x4ea40 and read_encoded_value_with_base 0x4e5b0','scope':'all 839 FDE starts and final covered bytes, 61 replacement instruction boundaries, three uncovered boundaries; cold and reused header cache; helper NULL LSDA and indirect personality encoding','limits':'dl_iterate_phdr input supplied and libc strlen mocked; exception personality and actual QNX runtime not executed'}
(P/'unwind_lookup_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {total} stock binary lookup cases and {encoded_checks} pointer-decode cases at two PIE load biases; all original indexed frames retained and replacement frames found.')

if os.environ.get('PX_CANDIDATE_ELF'):print('Installed candidate unwind header and FDE bytes tested.')

#!/usr/bin/env python3
"""Reproduce the tested PX maintenance VM from an owner's private boot file."""
import argparse, hashlib, json, struct, subprocess, tempfile
from pathlib import Path

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def put(b,o,v): struct.pack_into('<I',b,o,v)
def checksum(b):
    if len(b)%4: raise ValueError('unaligned checksum region')
    return sum(struct.unpack('<%dI'%(len(b)//4),b)) & 0xffffffff

def decompress_block(src):
    pos=0; bits=0; out=bytearray(); previous=1
    def byte():
        nonlocal pos
        if pos>=len(src): raise ValueError('compressed input overrun')
        v=src[pos];pos+=1;return v
    def bit():
        nonlocal bits
        if bits & 0x7f: bits*=2
        else: bits=byte()*2+1
        return (bits>>8)&1
    while True:
        while bit():
            out.append(byte())
            if len(out)>65536: raise ValueError('block output overrun')
        offset=1
        while True:
            offset=offset*2+bit()
            if offset>0xffffff+3: raise ValueError('invalid offset prefix')
            if bit(): break
        if offset==2: offset=previous
        else:
            offset=(offset-3)*256+byte()
            if offset==0xffffffff: break
            offset+=1; previous=offset
        length=bit()*2+bit()
        if not length:
            length=1
            while True:
                length=length*2+bit()
                if length>65536: raise ValueError('invalid length prefix')
                if bit(): break
            length+=2
        length+=(offset>0xd00)
        if offset>len(out) or len(out)+length+1>65536: raise ValueError('invalid match')
        for _ in range(length+1): out.append(out[-offset])
    if pos!=len(src): raise ValueError('compressed block trailing bytes')
    return bytes(out)

def decode_image(b):
    start=0xf30; size=u32(b,start+32); off=start+size
    expected=u32(b,start+44); result=bytearray();blocks=0
    while len(result)<expected:
        n=struct.unpack_from('>H',b,off)[0];off+=2
        if not n or off+n>len(b): raise ValueError('invalid compressed block size')
        block=decompress_block(b[off:off+n]);off+=n
        result.extend(block);blocks+=1
    if len(result)!=expected or checksum(result): raise ValueError('IFS length/checksum mismatch')
    return off,bytes(result),blocks


INPUT_SHA256 = "6a5124d8ee0eb6ad7561bf394e3c7469115dc6184e397d34ea7e3b72f8f6fccc"
IFS_SHA256 = "276d810a039e6d15cd4c7ceb04f8a829db0e4396e1e55e5eacb15b7d8ce6d8a1"
DISK_SHA256 = "d09c8e53353ac9aabe7bcc9e905c6e5feabaa3002a0f92f72a99ac85beca4662"

def record(kind, data):
    n=(4+len(data)+3)&~3
    return struct.pack('<HH',n,kind)+data+bytes(n-4-len(data))

def launch(exe,args,flags):
    env=["PATH=/proc/boot:/bin:/sbin:/usr/bin:/usr/sbin",
         "LD_LIBRARY_PATH=/proc/boot:/lib:/usr/lib:/lib/dll:/lib/dll/pci", "TERM=vt100"]
    strings=[exe,exe]+args+env
    fields=struct.pack('<IHBB',flags,0,len(args)+1,len(env))
    return record(0,fields+b''.join(x.encode()+b'\0' for x in strings))

def maintenance_script(original):
    # Retain the two owner-supplied dynamic-loader symlink records.
    o=0
    for _ in range(2):
        n,kind=struct.unpack_from('<HH',original,o)
        if kind!=4 or n<4 or o+n>len(original): raise ValueError('unexpected loader links')
        o+=n
    return (original[:o]+record(3,b'PX maintenance candidate: no disks mounted automatically\n\0')
       +launch('devc-ser8250',['-e','-b115200','3f8,4'],0x2000)
       +record(1,struct.pack('<H',100)+b'/dev/ser1\0')
       +record(2,struct.pack('<H',100)+b'/dev/ser1\0')
       +launch('pipe',[],0x2000)+launch('ksh',['-i'],0x200)+bytes(4))

def patch_ifs(ifs):
    b=bytearray(ifs);o=u32(b,16);entries=[];script=None
    while o<len(b)-4:
        n=struct.unpack_from('<H',b,o)[0]
        if not n: break
        if n<24 or o+n>len(b): raise ValueError('invalid IFS directory entry')
        mode=u32(b,o+8); name=bytes(b[o+32:o+n]).split(b'\0')[0] if n>=32 else b''
        if mode & 0xf000 == 0x8000:
            off,size=struct.unpack_from('<II',b,o+24)
            if off+size>len(b)-4: raise ValueError('file exceeds IFS')
            entries.append((name,off,size))
            if name==b'proc/boot/startup-script':script=(off,size)
        o+=n
    if script is None:raise ValueError('startup-script absent')
    off,size=script;new=maintenance_script(bytes(b[off:off+size]))
    if len(new)>size:raise ValueError('script exceeds original allocation')
    b[off:off+size]=new+bytes(size-len(new))
    put(b,len(b)-4,0);put(b,len(b)-4,(-checksum(b))&0xffffffff)
    for name,f,n in entries:
        if name!=b'proc/boot/startup-script' and b[f:f+n]!=ifs[f:f+n]:
            raise ValueError('unexpected file modification')
    return bytes(b),len(entries)

def build(input_path, output, assembler, linker):
    source=input_path.read_bytes()
    digest=hashlib.sha256(source).hexdigest()
    if digest!=INPUT_SHA256:
        raise ValueError('unsupported input SHA-256: '+digest+'; only the tested original PX boot file is supported')
    if output.exists(): raise ValueError('output directory already exists; choose a fresh path')
    start=0xf30;startup_size=u32(source,start+32);offset=start+startup_size
    if checksum(source[start:offset]):raise ValueError('startup checksum mismatch')
    end,ifs,blocks=decode_image(source)
    new_ifs,file_count=patch_ifs(ifs)
    prefix=bytearray(source[:offset]);prefix[start+6]&=~0x0c
    put(prefix,start+36,startup_size+len(new_ifs))
    put(prefix,start+40,u32(source,start+20)+startup_size)
    put(prefix,offset-4,0);put(prefix,offset-4,(-checksum(prefix[start:]))&0xffffffff)
    payload=bytes(prefix)+new_ifs
    if hashlib.sha256(payload).hexdigest()!=IFS_SHA256:raise ValueError('rebuilt payload differs from tested reference')
    chunks=(len(payload)+32767)//32768
    low_chunks=(offset+32767)//32768
    loader_path=Path(__file__).with_name('bootloader.S')
    loader=loader_path.read_text().replace('mov $715,%bp',f'mov ${chunks},%bp').replace('mov $6,%bp',f'mov ${low_chunks},%bp')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'loader.S').write_text(loader)
        subprocess.run([assembler,'--32','-o',str(root/'loader.o'),str(root/'loader.S')],check=True)
        subprocess.run([linker,'-m','elf_i386','-Ttext','0x7c00','--oformat','binary','-o',str(root/'loader.bin'),str(root/'loader.o')],check=True)
        boot=(root/'loader.bin').read_bytes()
    if len(boot)!=512 or boot[-2:]!=b'\x55\xaa':raise ValueError('invalid boot sector')
    disk=boot+payload+bytes(chunks*32768-len(payload))
    if hashlib.sha256(disk).hexdigest()!=DISK_SHA256:raise ValueError('rebuilt disk differs from tested reference')
    output.mkdir(parents=True)
    (output/'px-maintenance-candidate.ifs').write_bytes(payload)
    (output/'px-maintenance-vm-boot.img').write_bytes(disk)
    report=dict(input_sha256=digest,payload_sha256=IFS_SHA256,boot_disk_sha256=DISK_SHA256,
        payload_bytes=len(payload),boot_disk_bytes=len(disk),decompressed_blocks=blocks,
        retained_regular_files=file_count-1, startup_checksum=checksum(prefix[start:]),
        ifs_checksum=checksum(new_ifs), reference_match=True)
    (output/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path,help='private original .boot/x86_64-generic.bin')
    p.add_argument('--output',type=Path,required=True,help='new private output directory')
    p.add_argument('--assembler',default='as',help='GNU assembler executable')
    p.add_argument('--linker',default='ld',help='GNU linker executable')
    a=p.parse_args()
    try: build(a.input,a.output,a.assembler,a.linker)
    except (ValueError,OSError,subprocess.CalledProcessError,struct.error) as e:
        p.exit(1,'Build stopped: '+str(e)+'\n')

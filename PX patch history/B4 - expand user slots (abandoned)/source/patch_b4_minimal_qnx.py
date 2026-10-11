#!/usr/bin/env python3
"""Stock-only minimal B4 QNX ELF patcher. Never writes or packages its input."""
import argparse, hashlib, json, struct, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STOCK_SHA='7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff'
CONTAINER_SHA='a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9'
BASE=0x9d480; LIMIT=0x9d680
TARGETS={
 'b4_size_extension':0x2b1eb0,'b4_size_extension_end':0x2b1fb0,'b4_extension_bias':0x2b1ca8,
 'b4_stock_size_cache':0x2a4a20,'b4_stock_init_continue':0x7bc7,
 'b4_stock_size_load':0x1532e,'b4_stock_size_miss':0x15340,'b4_stock_size_store':0x1527f,
 'b4_stock_copy_cache_continue':0x15bb8,'b4_stock_delete_cache_continue':0x15e29,
 'b4_stock_size_backend':0x151c0,'b4_stock_group_names':0x2a0160,
 'b4_stock_copy_group_continue':0x15aff,'b4_stock_copy_epilogue':0x15ad3,
 'b4_stock_release_scoped':0x33cc3,'b4_stock_release_all':0x33d6c,'b4_stock_release_group':0x33d8c,
 'b4_stock_release_epilogue':0x33d5d,'b4_stock_index_scoped':0x33dff,
 'b4_stock_index_all':0x33e69,'b4_stock_index_group':0x33ea8,'b4_stock_index_epilogue':0x33e4f,
 'b4_stock_update_branch':0x35365,'b4_stock_update_epilogue':0x35483,'b4_stock_count_send':0x22c9c}
# Whole instruction guards. Entries are VA, original bytes, replacement bytes.
EDITS=[
 (0x16181,'bfd0330000','bf504d0000','owner allocation'),
 (0x33390,'488d8f88220000','488d8f88330000','constructor row end'),
 (0x333af,'48c784474811000000000000','48c78447c819000000000000','constructor heads'),
 (0x33c10,'83fe40','83fe60','folder group limit'),
 (0x33c2a,'488d843228020000','488d843238030000','folder head base'),
 (0x33c72,'83fe40','83fe60','count group limit'),
 (0x336e4,'4883fb41','4883fb61','index name end'),
 (0x33dde,'488d8748110000','488d87c8190000','index head alias'),
 (0x33e9e,'83fb41','83fb61','index size refresh end'),
 (0x33cfb,'498bbd48110000','498bbdc8190000','release head read'),
 (0x33d30,'49c7854811000000000000','49c785c819000000000000','release head clear'),
 (0x33d45,'448b642404','4531e49090','release category cursor correction'),
 (0x33d6c,'c744240c41000000','c744240c61000000','release group end'),
 (0x3518c,'4a8bb4e848110000','4a8bb4e8c8190000','parser head read 1'),
 (0x351cc,'4a8bb4e848110000','4a8bb4e8c8190000','parser head read 2'),
 (0x35410,'4b8b94ee48110000','4b8b94eec8190000','update head read 1'),
 (0x3552d,'498b94c648110000','498b94c6c8190000','update head read 2'),
 (0x35216,'83f841','83f861','parser group end'),
 (0x35650,'c744244c41000000','c744244c61000000','update group end'),
 (0x2e01e,'4c8db008020000','4c8db008030000','user folder end'),
 (0x1542a,'4d8da708020000','4d8da708030000','import name end'),
 (0x15d91,'83ff40','83ff60','delete group limit')]
HOOKS=[
 (0x7bc0,'488d0559ce2900','b4_cache_init',False),
 (0x15320,'85ff751c488d05f5f62800','b4_size_front',False),
 (0x15278,'488d15a1f72800','b4_size_store_base',False),
 (0x15bb1,'488d0568ee2800','b4_copy_cache_base',False),
 (0x15e22,'488d05f7eb2800','b4_delete_cache_base',False),
 (0x15bca,'e8f1f5ffff','b4_direct_size_guard',True),
 (0x15af8,'488d0561a62800','b4_copy_group_guard',False),
 (0x33cb1,'83fe400f87b200000083fa100f87c9000000','b4_release_guard',False),
 (0x33df1,'83fb407773','b4_index_guard',False),
 (0x3535c,'4183ff404889442408','b4_update_guard',False),
 (0x22c92,'89c2be124000004c89ff','b4_count_reply_guard',False)]
def sha(b):return hashlib.sha256(b).hexdigest()
def read_stock(path):
 data=Path(path).read_bytes()
 if data[:4]==b'\x7fELF':elf=data
 else:
  if sha(data)!=CONTAINER_SHA:raise ValueError('not accepted clean stock container')
  elf=data[13:0xf0da5]
 if sha(elf)!=STOCK_SHA:raise ValueError('QNX ELF is not accepted clean stock')
 return elf
class Elf:
 def __init__(self,b):
  self.b=b;self.phoff=struct.unpack_from('<Q',b,32)[0];self.shoff=struct.unpack_from('<Q',b,40)[0]
  self.phents,self.phnum,self.shents,self.shnum,self.shstr=struct.unpack_from('<HHHHH',b,54)
  self.ph=[struct.unpack_from('<IIQQQQQQ',b,self.phoff+i*self.phents) for i in range(self.phnum)]
  self.sh=[struct.unpack_from('<IIQQQQIIQQ',b,self.shoff+i*self.shents) for i in range(self.shnum)]
  s=self.sh[self.shstr];st=b[s[4]:s[4]+s[5]]
  self.names=[st[x[0]:st.find(b'\0',x[0])].decode() for x in self.sh]
 def off(self,va,n=1):
  for typ,flags,o,v,p,f,m,a in self.ph:
   if typ==1 and v<=va and va+n<=v+f:return o+va-v
  raise ValueError(f'VA {va:#x} not wholly file backed')
def build_helpers(clang='clang'):
 with tempfile.TemporaryDirectory(prefix='b4_qnx_asm_') as td:
  obj=Path(td)/'helpers.o'
  subprocess.run([clang,'-target','x86_64-unknown-linux-gnu','-c',str(ROOT/'b4_minimal_qnx_helpers.s'),'-o',str(obj)],check=True,capture_output=True)
  raw=obj.read_bytes();e=Elf(raw);ti=e.names.index('.text');ts=e.sh[ti];code=bytearray(raw[ts[4]:ts[4]+ts[5]])
  syms={};tables={}
  for si,s in enumerate(e.sh):
   if s[1]!=2:continue
   strings=e.sh[s[6]];st=raw[strings[4]:strings[4]+strings[5]];tab=[]
   for o in range(s[4],s[4]+s[5],s[9]):
    no,info,other,ndx,val,size=struct.unpack_from('<IBBHQQ',raw,o)
    name=st[no:st.find(b'\0',no)].decode();tab.append((name,ndx,val,size))
    if ndx==ti and name.startswith('b4_'):syms[name]={'va':BASE+val,'size':size}
   tables[si]=tab
  rels=[]
  for s in e.sh:
   if s[1]!=4:continue
   if s[7]!=ti:raise ValueError('unexpected non-text relocation')
   for o in range(s[4],s[4]+s[5],s[9]):
    loc,info,add=struct.unpack_from('<QQq',raw,o);typ=info&0xffffffff
    name,ndx,val,size=tables[s[6]][info>>32]
    if typ not in (2,4):raise ValueError(f'unsupported relocation {typ}')
    target=BASE+val if ndx==ti else TARGETS[name]
    delta=target+add-(BASE+loc)
    struct.pack_into('<i',code,loc,delta)
    rels.append({'offset':hex(loc),'type':typ,'symbol':name,'target':hex(target),'addend':add,'resolved':delta})
  if len(code)!=359 or BASE+len(code)>LIMIT:raise ValueError('helper size changed; review placement')
  return bytes(code),syms,rels
def patch(stock,code,syms,rels):
 e=Elf(stock);out=bytearray(stock);manifest=[]
 def put(o,expected,new,label,va=None):
  if stock[o:o+len(expected)]!=expected:raise ValueError(f'original-byte guard failed: {label} at {o:#x}')
  if len(new)!=len(expected):raise ValueError('length-changing patch')
  if any(o<x['file_offset']+x['length'] and x['file_offset']<o+len(new) for x in manifest):raise ValueError('overlapping patch entries')
  out[o:o+len(new)]=new;manifest.append({'label':label,'va':hex(va) if va is not None else None,'file_offset':o,'length':len(new),'original':expected.hex(),'replacement':new.hex()})
 for va,old,new,label in EDITS:put(e.off(va,len(bytes.fromhex(old))),bytes.fromhex(old),bytes.fromhex(new),label,va)
 for va,old,name,call in HOOKS:
  expected=bytes.fromhex(old);dest=syms[name]['va'];new=bytes([0xe8 if call else 0xe9])+struct.pack('<i',dest-va-5)+b'\x90'*(len(expected)-5)
  put(e.off(va,len(expected)),expected,new,name,va)
 put(BASE,b'\0'*(LIMIT-BASE),code+b'\0'*(LIMIT-BASE-len(code)),'owned helper reservation',BASE)
 for o,old,new,label in [(0xb0+32,0x9d480,0x9d680,'RX filesz'),(0xb0+40,0x9d480,0x9d680,'RX memsz'),(0xe8+40,0x13bf8,0x13cf8,'RW memsz'),(e.shoff+24*e.shents+32,0xda10,0xdb10,'BSS size'),(0x1398,0x2b1eb0,0x2b1fb0,'dynamic end'),(0xe63f8,0x2b1eb0,0x2b1fb0,'static end')]:put(o,struct.pack('<Q',old),struct.pack('<Q',new),label)
 fixed=bytes.fromhex('4c8d0515342600');o=e.off(0x4ea94,len(fixed))
 if stock[o:o+7]!=fixed or out[o:o+7]!=fixed:raise ValueError('fixed frame-cache endpoint changed')
 changed={i for i,(a,b) in enumerate(zip(stock,out)) if a!=b}
 allowed=set().union(*(set(range(x['file_offset'],x['file_offset']+x['length'])) for x in manifest))
 if not changed<=allowed or len(out)!=len(stock):raise ValueError('unmanifested change')
 return bytes(out),{'assembly_sha256':sha((ROOT/'b4_minimal_qnx_helpers.s').read_bytes()),'helper_sha256':sha(code),'stock_sha256':sha(stock),'patched_sha256':sha(out),'elf_length':len(out),'helper_bytes':len(code),'helpers':syms,'relocations':rels,'patches':manifest,'changed_bytes':len(changed),'fixed_frame_cache_endpoint':'0x2B1EB0; instruction unchanged'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--clang',default='clang');a=p.parse_args()
 if a.output.resolve()==a.manifest.resolve():p.error('ELF output and manifest must be distinct')
 if a.output.exists() or a.manifest.exists():p.error('refusing to overwrite an existing output or manifest')
 if a.output.resolve()==a.input.resolve() or a.manifest.resolve()==a.input.resolve():p.error('output aliases input')
 stock=read_stock(a.input);code,syms,rels=build_helpers(a.clang);out,m=patch(stock,code,syms,rels)
 # Exclusive creation: never truncate inputs or preexisting files.
 with a.output.open('xb') as f:f.write(out)
 with a.manifest.open('x') as f:json.dump(m,f,indent=2);f.write('\n')
 print(json.dumps({k:m[k] for k in ('stock_sha256','patched_sha256','elf_length','helper_bytes','changed_bytes')},indent=2))
if __name__=='__main__':main()

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
 (0x16181,{'size': 5, 'sha256': '86b198e9879bd4d5209775ca211e81a9580770f2453ed123e39ec7812d683d54'},'bf504d0000','owner allocation'),
 (0x33390,{'size': 7, 'sha256': 'e8343a97c4e30e6af587f53e154953b70dc2fbd7fd6a6d1a321e859cae752f51'},'488d8f88330000','constructor row end'),
 (0x333af,{'size': 12, 'sha256': 'b9132c721f394827cd22858b55799f5b1abbb09c657e1d8f0a6e8614a28f4cbd'},'48c78447c819000000000000','constructor heads'),
 (0x33c10,{'size': 3, 'sha256': '7e54f30b6504023c5db9d667c5978b5991bead2dfe3a571d62a4ec9de1a51e75'},'83fe60','folder group limit'),
 (0x33c2a,{'size': 8, 'sha256': '52c158b321b07f2c32e58b8554e487937d043228ea01b76f61ce1968b123a8fb'},'488d843238030000','folder head base'),
 (0x33c72,{'size': 3, 'sha256': '7e54f30b6504023c5db9d667c5978b5991bead2dfe3a571d62a4ec9de1a51e75'},'83fe60','count group limit'),
 (0x336e4,{'size': 4, 'sha256': '76c345a3e3f79ae1306262330812a21406ced19f79c7ae91de885cccd0437762'},'4883fb61','index name end'),
 (0x33dde,{'size': 7, 'sha256': '421782f2d9662e8fbe820e5d27fa912547acfa709fd1378270b39f91121da507'},'488d87c8190000','index head alias'),
 (0x33e9e,{'size': 3, 'sha256': '1c28d7ea70a0154b1fd4ea10f3644313c29adc059e8768cd8f8ae9326f7786d6'},'83fb61','index size refresh end'),
 (0x33cfb,{'size': 7, 'sha256': 'bd5bd8c1358a6a43bcdf4a814dc3f4595f60f94f7ff410f1ae63815398d2cfc9'},'498bbdc8190000','release head read'),
 (0x33d30,{'size': 11, 'sha256': '5061bc9b3af42330118edf36a97d8a04f5553eadcc4d856bbf0ed4c7a2b4f75c'},'49c785c819000000000000','release head clear'),
 (0x33d45,{'size': 5, 'sha256': '5dc71ade3c3fc5fbcec3e925f266beaeb3d14064f4627ba6bcacee38af2aff74'},'4531e49090','release category cursor correction'),
 (0x33d6c,{'size': 8, 'sha256': '2090789601218df4bbb417e174ffd88420865659f858d877551f330807968ae6'},'c744240c61000000','release group end'),
 (0x3518c,{'size': 8, 'sha256': '99abba391c960d9c33c6c5a5ea2aa1c039cd2f110032963ac52ac2116e43250d'},'4a8bb4e8c8190000','parser head read 1'),
 (0x351cc,{'size': 8, 'sha256': '99abba391c960d9c33c6c5a5ea2aa1c039cd2f110032963ac52ac2116e43250d'},'4a8bb4e8c8190000','parser head read 2'),
 (0x35410,{'size': 8, 'sha256': 'ffd37a894cd7d281bc3ddccd22eeec7e14a691b15784c47385bba383a5f2d3dd'},'4b8b94eec8190000','update head read 1'),
 (0x3552d,{'size': 8, 'sha256': 'eb8b5a0c0772fda3ff1c2c7d2dc282d4dcebfde139fc78725e373c7fa38f501c'},'498b94c6c8190000','update head read 2'),
 (0x35216,{'size': 3, 'sha256': '9751df4a31ea78fa896280958c55c069a89e1a4aff0b65466b7d1322fc44b2cc'},'83f861','parser group end'),
 (0x35650,{'size': 8, 'sha256': '49e22cd7631fd5e82c27018ebbb33293e2cca8a69ee74c026a0af32becdc1f1e'},'c744244c61000000','update group end'),
 (0x2e01e,{'size': 7, 'sha256': 'a0b0d096ad10c734737fe74a7c0b3029184eed47e5ece5fae411983969ffc1f5'},'4c8db008030000','user folder end'),
 (0x1542a,{'size': 7, 'sha256': '66d498a9a83b705bf0f83e69865e0fc54d654c4a515dc60bac65229eacefb890'},'4d8da708030000','import name end'),
 (0x15d91,{'size': 3, 'sha256': 'e6e1a746b28aedb3760d65e8bbbb356881ced01597b3b20cb2f728b51fdc1988'},'83ff60','delete group limit')]
HOOKS=[
 (0x7bc0,{'size': 7, 'sha256': '213d28f3b4e1fe76021e2767f75ca00c308aec2a60c86c672cc82eaec721628b'},'b4_cache_init',False),
 (0x15320,{'size': 11, 'sha256': '6d427c03d92fc0163048a2ec9358eea75c51e2b48c4da5dc5485c34286a8b82e'},'b4_size_front',False),
 (0x15278,{'size': 7, 'sha256': 'c0c1f6e01b4186dc3dfb60581e91da8ba383e6509f9b7a12e44b3d6f3211cd49'},'b4_size_store_base',False),
 (0x15bb1,{'size': 7, 'sha256': '260ffe11c2fa59654fd634debe1b2e43f35b7ee0a61b286ccccb5224d451afab'},'b4_copy_cache_base',False),
 (0x15e22,{'size': 7, 'sha256': '081e4e3a5c2073445b5a87430fa5c046d604b219c4ca423d7ab5b9ffdabbc744'},'b4_delete_cache_base',False),
 (0x15bca,{'size': 5, 'sha256': '813fb0ac3c5361a3631029ee41072576c24260869568f870258eb906187df7ff'},'b4_direct_size_guard',True),
 (0x15af8,{'size': 7, 'sha256': 'd07ab93a3c5475d5d6b030e8ea4426e2ee83cc98ab021928821a8ba46be4d875'},'b4_copy_group_guard',False),
 (0x33cb1,{'size': 18, 'sha256': '0f47394566cb63f22ce70461e6ef63bb981e26db1bd4e01399b9828361156f9a'},'b4_release_guard',False),
 (0x33df1,{'size': 5, 'sha256': '8220a95aab3f406c7cb363f608f45378b61fb150f72f0f75a96c2ba011ec083e'},'b4_index_guard',False),
 (0x3535c,{'size': 9, 'sha256': '020c9b5f6011986c24b093e18301260cc4dcd6c36d4c400f5a8235c9378230b0'},'b4_update_guard',False),
 (0x22c92,{'size': 10, 'sha256': '98bdfa105b31bf1f067385f5ba60435c11fbf0f40bf7a9b4549adabc6b18b9c3'},'b4_count_reply_guard',False)]
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
 for va,old,new,label in EDITS:put(e.off(va,old['size']),guarded(lambda a,n:stock[e.off(a,n):e.off(a,n)+n],va,old),bytes.fromhex(new),label,va)
 for va,old,name,call in HOOKS:
  expected=guarded(lambda a,n:stock[e.off(a,n):e.off(a,n)+n],va,old);dest=syms[name]['va'];new=bytes([0xe8 if call else 0xe9])+struct.pack('<i',dest-va-5)+b'\x90'*(len(expected)-5)
  put(e.off(va,len(expected)),expected,new,name,va)
 put(BASE,b'\0'*(LIMIT-BASE),code+b'\0'*(LIMIT-BASE-len(code)),'owned helper reservation',BASE)
 for o,old,new,label in [(0xb0+32,0x9d480,0x9d680,'RX filesz'),(0xb0+40,0x9d480,0x9d680,'RX memsz'),(0xe8+40,0x13bf8,0x13cf8,'RW memsz'),(e.shoff+24*e.shents+32,0xda10,0xdb10,'BSS size'),(0x1398,0x2b1eb0,0x2b1fb0,'dynamic end'),(0xe63f8,0x2b1eb0,0x2b1fb0,'static end')]:put(o,struct.pack('<Q',old),struct.pack('<Q',new),label)
 o=e.off(0x4ea94,7);fixed=stock[o:o+7]
 if sha(fixed)!='bdede4b2ef220055128c5923e8e4617cf7b7b8348abb6e4b517521303a287c68':raise ValueError('fixed endpoint guard failed')
 if stock[o:o+7]!=fixed or out[o:o+7]!=fixed:raise ValueError('fixed frame-cache endpoint changed')
 changed={i for i,(a,b) in enumerate(zip(stock,out)) if a!=b}
 allowed=set().union(*(set(range(x['file_offset'],x['file_offset']+x['length'])) for x in manifest))
 if not changed<=allowed or len(out)!=len(stock):raise ValueError('unmanifested change')
 return bytes(out),{'assembly_sha256':sha((ROOT/'b4_minimal_qnx_helpers.s').read_bytes()),'helper_sha256':sha(code),'stock_sha256':sha(stock),'patched_sha256':sha(out),'elf_length':len(out),'helper_bytes':len(code),'helpers':syms,'relocations':rels,'patches':manifest,'changed_bytes':len(changed),'fixed_frame_cache_endpoint':'0x2B1EB0; instruction unchanged'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,default=ROOT/'PxUpdate_V2.2.2.0.0.bin');p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--clang',default='clang');a=p.parse_args()
 if a.output.resolve()==a.manifest.resolve():p.error('ELF output and manifest must be distinct')
 if a.output.exists() or a.manifest.exists():p.error('refusing to overwrite an existing output or manifest')
 if a.output.resolve()==a.input.resolve() or a.manifest.resolve()==a.input.resolve():p.error('output aliases input')
 stock=read_stock(a.input);code,syms,rels=build_helpers(a.clang);out,m=patch(stock,code,syms,rels)
 # Exclusive creation: never truncate inputs or preexisting files.
 with a.output.open('xb') as f:f.write(out)
 with a.manifest.open('x') as f:json.dump(m,f,indent=2);f.write('\n')
 print(json.dumps({k:m[k] for k in ('stock_sha256','patched_sha256','elf_length','helper_bytes','changed_bytes')},indent=2))

def guarded(read, address, guard):
    data=read(address,guard['size'])
    if len(data)!=guard['size'] or hashlib.sha256(data).hexdigest()!=guard['sha256']:
        raise ValueError(f'Original-byte SHA-256 guard failed at {address:#x}')
    return data

if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute isolated x86-64 stock/patched ELF code. No QNX OS or filesystem I/O."""
import ctypes as C, json,platform,struct,sys,argparse,tempfile
from pathlib import Path
import patch_b4_minimal_qnx as P
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('candidate', type=Path)
parser.add_argument('--input', type=Path, required=True, help='Exact factory update container')
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--results', type=Path, required=True, help='Private output JSON path')
args=parser.parse_args()
if platform.machine() not in ('x86_64','AMD64'):raise SystemExit('Run using an x86-64 Python runtime (e.g. python3-intel64).')
LIB=C.CDLL(None);LIB.mmap.argtypes=[C.c_void_p,C.c_size_t,C.c_int,C.c_int,C.c_int,C.c_long];LIB.mmap.restype=C.c_void_p
U64=C.c_uint64;U32=C.c_uint32;PTR=C.c_void_p;STOP=0
class Image:
 def __init__(self,b):
  self.elf=P.Elf(b);self.raw=b;self.mem=LIB.mmap(None,0x300000,7,0x1002 if platform.system()=='Darwin' else 0x22,-1,0)
  if self.mem in (None,C.c_void_p(-1).value):raise RuntimeError('executable mmap failed')
  self.keep=[];self.logs=[];self.newnodes=[];self.frees=[];self.size_value=1234567;self.calls={};self.callback_errors=[];self.copy_mode=False
  for t,fl,o,v,p,f,m,a in self.elf.ph:
   if t==1:C.memmove(self.mem+v,b[o:o+f],f)
  self.symbols={};self.dyn=[]
  for i,s in enumerate(self.elf.sh):
   if s[1]!=11:continue
   st=self.elf.sh[s[6]];strings=b[st[4]:st[4]+st[5]]
   for o in range(s[4],s[4]+s[5],s[9]):
    n,info,other,idx,val,size=struct.unpack_from('<IBBHQQ',b,o);name=strings[n:strings.find(b'\0',n)].decode();self.dyn.append((name,val));self.symbols[name]=val
  self.canary=U64(0xfeed998811223344);self.keep.append(self.canary)
  for s in self.elf.sh:
   if s[1]!=4:continue
   for o in range(s[4],s[4]+s[5],24):
    addr,info,add=struct.unpack_from('<QQq',b,o);typ=info&0xffffffff;name,val=self.dyn[info>>32]
    if typ==8:self.w64(addr,self.mem+add)
    elif name=='__stack_chk_guard':self.w64(addr,C.addressof(self.canary))
    elif name in ['sprintf','strcpy','strrchr','strcmp','strlen','memcpy','memset','memmove','strncpy','strncasecmp','atoi','atol','sscanf']:
     self.w64(addr,C.cast(getattr(LIB,name),PTR).value)
  # Accepted GOT canary pointer is set explicitly, independently of symbol naming.
  self.w64(0x29ffa8,C.addressof(self.canary))
  self.install_import('_ZdlPv',None,[PTR],lambda p:self.frees.append(p))
  self.install_import('_Znwm',PTR,[C.c_size_t],self.alloc)
  self.install_import('sync',C.c_int,[],lambda:0)
  self.install_import('stat',C.c_int,[PTR,PTR],lambda a,z:0)
  self.install_import('open',C.c_int,[PTR,C.c_int],lambda a,f:-1)
  self.install_import('opendir',PTR,[PTR],self.opendir)
  self.install_import('closedir',C.c_int,[PTR],lambda p:0)
  self.install_import('mkdir',C.c_int,[PTR,C.c_int],self.mkdir)
  self.install_import('nftw',C.c_int,[PTR,PTR,C.c_int,C.c_int],self.walk_copy)
  self.interpose(0x339b0,C.c_int,[PTR,PTR,C.c_int],self.walk)
  self.interpose(0x14e90,C.c_int,[PTR,PTR],self.group_size)
  self.interpose(0x15050,C.c_int,[C.c_int,C.c_int,U64,C.c_int],lambda v,g,n,f:self.logs.append(('write_size',v,g,n)) or 0)
  self.interpose(0x4a2b0,C.c_int,[PTR],lambda p:self.logs.append(('delete',C.string_at(p).decode())) or 0)
  self.cache_stub=C.create_string_buffer(32);self.keep.append(self.cache_stub)
  self.interpose(0x34b90,PTR,[],lambda:C.addressof(self.cache_stub))
 def cb(self,result,args,fn):
  def checked(*a):
   try:return fn(*a)
   except BaseException as ex:self.callback_errors.append(repr(ex));return 0 if result is not None else None
  cb=C.CFUNCTYPE(result,*args)(checked);self.keep.append(cb);return C.cast(cb,PTR).value
 def install_import(self,name,result,args,fn):
  ptr=self.cb(result,args,fn)
  for s in self.elf.sh:
   if s[1]!=4:continue
   for o in range(s[4],s[4]+s[5],24):
    addr,info,add=struct.unpack_from('<QQq',self.raw,o)
    if self.dyn[info>>32][0]==name:self.w64(addr,ptr)
 def interpose(self,va,result,args,fn):
  p=self.cb(result,args,fn);C.memmove(self.mem+va,b'\x48\xb8'+struct.pack('<Q',p)+b'\xff\xe0',12)
 def opendir(self,p):
  self.logs.append(('opendir',C.string_at(p).decode()));return 0x1234
 def mkdir(self,p,mode):
  self.logs.append(('mkdir',C.string_at(p).decode(),mode));return 0
 def count_entry_shim(self):
  # Actual HandleMessage frame and count dispatch/reply/epilogue; unrelated
  # playback/dispatch setup is replaced only in harness memory.
  pc=0x2d0000;code=bytes.fromhex('c685fef7ffff00c685fff7ffff00')
  code+=b'\xe9'+struct.pack('<i',0x22c6a-(pc+len(code)+5))
  C.memmove(self.mem+pc,code,len(code));C.memmove(self.mem+0x1e087,b'\xe9'+struct.pack('<i',pc-0x1e087-5),5)
 def alloc(self,n):
  a=C.create_string_buffer(n);self.keep.append(a);p=C.addressof(a);self.newnodes.append(p);return p
 def walk(self,p,cb,depth):self.logs.append(('walk',C.string_at(p).decode()));return 0
 def walk_copy(self,p,cb,depth,flags):
  self.logs.append(('nftw',C.string_at(p).decode()))
  if cb==self.mem+0x14e20:self.w64(0x2a4c28,self.size_value)
  elif self.copy_mode:self.w32(0x2a4c48,1);C.c_uint8.from_address(self.mem+0x2a4e78).value=1
  return 0
 def group_size(self,path,out):
  self.logs.append(('size',C.string_at(path).decode()));U64.from_address(out).value=self.size_value;return 1
 def w64(self,va,v):U64.from_address(self.mem+va).value=v
 def r64(self,va):return U64.from_address(self.mem+va).value
 def w32(self,va,v):U32.from_address(self.mem+va).value=v
 def fn(self,va,result,*args):return C.CFUNCTYPE(result,*args)(self.mem+va)
 def ctor(self):
  size=0x4d50 if self.raw!=stock else 0x33d0
  a=C.create_string_buffer(size+32);C.memset(C.addressof(a),0xa5,size+32);self.keep.append(a)
  self.fn(0x33390,None,PTR)(C.addressof(a));return a,size
 def initialize(self):self.fn(0x7bc0,None)()
 def cell(self,a,g,c,n,head=0):
  i=17*g+c;p=C.addressof(a);U32.from_address(p+4*i).value=n;U64.from_address(p+(0x19c8 if self.raw!=stock else 0x1148)+8*i).value=head
 def transport(self):
  vtable=(U64*3)();obj=(U64*1)();msg=C.create_string_buffer(0x4000);self.keep.extend([vtable,obj,msg]);pack=[]
  def send(this,data):pack.append(U32.from_address(data).value);return 0
  vtable[2]=self.cb(C.c_int,[PTR,PTR],send);obj[0]=C.addressof(vtable);U64.from_address(C.addressof(msg)+0x1ff0).value=C.addressof(obj)
  return msg,pack
stock=P.read_stock(args.input)
patched=args.candidate.read_bytes()
expected_sha=json.loads(args.manifest.read_text())['patched_sha256']
if P.sha(patched)!=expected_sha:raise SystemExit('isolated ELF does not match the guarded patch manifest')
def main():
 tests=[]
 def check(name,condition):
  if not condition:raise AssertionError(name)
  tests.append(name)
 im=Image(patched);orig=Image(stock)
 a,size=im.ctor();p=C.addressof(a)
 check('constructor counts zero',C.string_at(p,0x19c4)==b'\0'*0x19c4)
 check('constructor heads zero',C.string_at(p+0x19c8,0x3388)==b'\0'*0x3388)
 check('constructor preserves stock padding behavior',C.string_at(p+0x19c4,4)==b'\xa5'*4)
 check('constructor end canary',C.string_at(p+size,32)==b'\xa5'*32)
 im.w64(0x2a4c28,0x1133557799);im.w64(0x2b1fb0,0x22446688aa)
 im.initialize();orig.initialize()
 check('initializer retains stock cache result',all(im.r64(0x2a4a20+8*g)==orig.r64(0x2a4a20+8*g)==2**64-1 for g in range(65)))
 check('initializer extension 32 unknown entries',all(im.r64(0x2b1eb0+8*g)==2**64-1 for g in range(32)))
 check('initializer neighboring words intact',im.r64(0x2a4c28)==0x1133557799 and im.r64(0x2b1fb0)==0x22446688aa)
 def count(m,o,g,c):return m.fn(0x33c70,U32,PTR,C.c_int,C.c_int)(C.addressof(o),g,c)
 def folder(m,o,g,c,i):return m.fn(0x33c10,PTR,PTR,C.c_int,C.c_int,C.c_int)(C.addressof(o),g,c,i)
 for g in (64,65,96):
  for c in (0,16):
   node=im.alloc(0x408);im.cell(a,g,c,g+c,node)
   check(f'count g{g} c{c}',count(im,a,g,c)==g+c)
   check(f'folder g{g} c{c}',folder(im,a,g,c,0)==node)
 check('count invalid g97/c17/-2 returns zero',all(count(im,a,g,c)==0 for g,c in ((97,0),(65,17),(-2,0),(65,-2))))
 check('folder invalid g97/c17 returns null',not folder(im,a,97,0,0) and not folder(im,a,65,17,0))
 ao,ns=orig.ctor();orig.cell(ao,64,16,80,0)
 check('stock valid count contract g64c16',count(orig,ao,64,16)==count(im,a,64,16))
 # Actual linked-list release and stock delete call boundary.
 def release(m,o,g,c):m.fn(0x33ca0,None,PTR,C.c_int,C.c_int)(C.addressof(o),g,c)
 for g in (64,65,96):
  for c in (0,16):
   x,n=im.ctor();head=im.alloc(0x408);tail=im.alloc(0x408);U64.from_address(head+0x400).value=tail;im.cell(x,g,c,2,head)
   old=len(im.frees);release(im,x,g,c)
   check(f'release chain g{g}c{c}',len(im.frees)==old+2 and count(im,x,g,c)==0 and not folder(im,x,g,c,0))
 for g,c in ((97,0),(65,17),(-2,0),(65,-2)):
  x,n=im.ctor();head=im.alloc(0x408);im.cell(x,65,0,1,head);before=C.string_at(C.addressof(x),n);nf=len(im.frees);release(im,x,g,c)
  check(f'release rejects {g}/{c}',C.string_at(C.addressof(x),n)==before and len(im.frees)==nf)
 for g,c in ((65,-1),(-1,-1),(-1,17)):
  x,n=im.ctor();fixtures=[(65,0),(65,16)] if g==65 else [(0,0),(64,16),(65,0),(96,16)]
  for h,k in fixtures:im.cell(x,h,k,1,im.alloc(0x408))
  nf=len(im.frees);release(im,x,g,c)
  check(f'release explicit sentinel {g}/{c}',len(im.frees)-nf==len(fixtures) and all(count(im,x,h,k)==0 for h,k in fixtures))
 # Differential proves the accepted category-cursor correction on actual bodies.
 for m in (orig,im):
  x,n=m.ctor()
  for g in (0,1):m.cell(x,g,16,1,m.alloc(0x408))
  nf=len(m.frees);release(m,x,-1,-1)
  check('patched category cursor frees both groups' if m is im else 'stock negative control retains later group',len(m.frees)-nf==(2 if m is im else 1))
 # Real size front/backend and continuation stores; backend GroupInfo I/O mocked.
 sizefn=im.fn(0x15320,U64,C.c_int,C.c_int,C.c_int)
 for g in (64,65,96):
  slot=0x2a4a20+8*g if g<=64 else 0x2b1eb0+8*(g-65)
  im.w64(slot,100+g);nlog=len(im.logs)
  check(f'HD cache hit routing g{g}',sizefn(0,g,0)==100+g and len(im.logs)==nlog)
  check(f'HD cached force behavior retained g{g}',sizefn(0,g,1)==100+g)
  im.w64(slot,2**64-1);im.size_value=200+g
  check(f'HD cache miss/write routing g{g}',sizefn(0,g,0)==200+g and im.r64(slot)==200+g)
  im.size_value=300+g
  check(f'USB bypass retains HD cache g{g}',sizefn(1,g,0)==300+g and im.r64(slot)==200+g)
  im.fn(0x15d60,None,U32)(g)
  check(f'delete stock zero-cache continuation g{g}',im.r64(slot)==0)
  im.copy_mode=True;im.size_value=400+g;im.fn(0x15a80,None,C.c_int,PTR)(g,0);im.copy_mode=False
  check(f'copy invalidation/direct backend/write g{g}',im.r64(slot)==400+g)
 for g in (97,-2):
  snapshot=C.string_at(im.mem+0x2a4a20,0x208)+C.string_at(im.mem+0x2b1eb0,256);nl=len(im.logs)
  check(f'size invalid group {g}',sizefn(0,g,0)==0 and sizefn(1,g,0)==0 and len(im.logs)==nl)
  im.fn(0x15d60,None,U32)(g&0xffffffff);im.fn(0x15a80,None,C.c_int,PTR)(g,0)
  check(f'copy/delete invalid group {g} no cache write',snapshot==C.string_at(im.mem+0x2a4a20,0x208)+C.string_at(im.mem+0x2b1eb0,256))
 check('size invalid volume returns zero',sizefn(2,65,0)==0)
 # Stock continuations for valid g64, size zero and force retain their behavior.
 for value in (0,987654):
  for m in (orig,im):m.size_value=value;m.w64(0x2a4a20+64*8,2**64-1)
  check(f'stock size backend differential {value}',orig.fn(0x15320,U64,C.c_int,C.c_int,C.c_int)(0,64,0)==sizefn(0,64,0)==value)
 # Actual index owner, release and post-index refresh; walk is empty by design.
 for g,c in ((64,0),(65,0),(96,16),(65,-1),(-1,-1),(-1,17),(97,0),(65,17),(-2,0),(65,-2)):
  x,n=im.ctor();im.initialize();nl=len(im.logs)
  im.fn(0x33db0,None,PTR,C.c_int,C.c_int)(C.addressof(x),g,c)
  logs=im.logs[nl:];walks=[z for z in logs if z[0]=='walk'];valid=g==-1 or (0<=g<=96 and (0<=c<=16 or c==-1))
  check(f'index scope {g}/{c}',len(walks)==(1 if valid else 0))
  if g==-1:check(f'index all refreshes g96 for c{c}',any(z[0]=='size' and z[1]=='/hd/u63' for z in logs))
  check(f'index aliases {g}/{c}',im.r64(0x2a9030)==C.addressof(x) and im.r64(0x2a9028)==C.addressof(x)+0x19c8)
 for g,c in ((64,0),(64,16),(64,-1)):
  outputs=[]
  for m in (orig,im):
   x,n=m.ctor();m.initialize();nl=len(m.logs);m.fn(0x33db0,None,PTR,C.c_int,C.c_int)(C.addressof(x),g,c);outputs.append(m.logs[nl:])
  check(f'stock index path differential {g}/{c}',outputs[0]==outputs[1])
 for g,c in ((97,0),(65,17),(-2,0),(65,-2)):
  x,n=im.ctor();head=im.alloc(0x408);im.cell(x,65,0,1,head);before=C.string_at(C.addressof(x),n);nf=len(im.frees)
  im.fn(0x33db0,None,PTR,C.c_int,C.c_int)(C.addressof(x),g,c)
  check(f'invalid index retains live nodes {g}/{c}',C.string_at(C.addressof(x),n)==before and len(im.frees)==nf)
 # Actual callback allocation/sorted insertion against host-backed new/delete.
 for g in (64,65,96,97):
  for c in (0,16):
   x,n=im.ctor();im.w64(0x2a9030,C.addressof(x));im.w64(0x2a9028,C.addressof(x)+0x19c8)
   group=C.string_at(im.r64(0x2a0160+8*g));category=C.string_at(im.r64(0x2a0020+8*c));st=C.create_string_buffer(256);nn=len(im.newnodes)
   for num in (2,1,3):
    path=C.create_string_buffer(b'/hd/'+group+b'/'+category+b'/'+str(num).encode()+b'-test/Group.grp')
    im.fn(0x33550,C.c_int,PTR,PTR,C.c_int)(C.addressof(path),C.addressof(st),0)
   if g<=96:
    check(f'index callback count/sort {g}/{c}',count(im,x,g,c)==3 and all(C.string_at(folder(im,x,g,c,i)).endswith(f'/{i+1}-test/'.encode()) for i in range(3)))
   else:check(f'index callback rejects97 category{c}',len(im.newnodes)==nn)
 # Update guard and stock empty-index continuations execute without dict effects.
 for g,c in ((64,0),(65,16),(96,0),(65,-1),(-1,-1),(97,0),(65,17),(-2,0)):
  x,n=im.ctor();nf=len(im.frees);im.fn(0x35320,None,PTR,PTR,C.c_int,C.c_int,C.c_int,C.c_int)(C.addressof(x),C.addressof(im.cache_stub),g,c,-1,1)
  check(f'update guard/empty continuation {g}/{c}',len(im.frees)==nf and not im.callback_errors)
 # Folder construction executes real name/category loop with directory I/O mocked.
 nl=len(im.logs);im.fn(0x2dfe0,None)();dirs=[z[1] for z in im.logs[nl:] if z[0]=='opendir']
 check('folder creation spans user u08 through u63',len(dirs)==56 and dirs[0]=='/hd/u08' and dirs[-1]=='/hd/u63' and '/hd/u32' in dirs)
 # Count guard + actual stock send serialization and owner epilogue.
 im.count_entry_shim();orig.count_entry_shim()
 for g in (64,65,96):
  for c in (0,16):
   for num in (0,255,256,65536,0xffffffff):
    x,n=im.ctor();im.cell(x,g,c,num);msg,pack=im.transport();U64.from_address(C.addressof(msg)).value=C.addressof(x)
    im.fn(0x1e050,None,PTR,U32,U32)(C.addressof(msg),0x4012,g*256+c)
    expected=(0x4012<<16)|num if num<=255 else 0x403c<<16
    check(f'count wire guard g{g}c{c} N{num}',pack==[expected])
 for num in (0,255):
  values=[]
  for m in (orig,im):
   x,n=m.ctor();m.cell(x,64,16,num);msg,pack=m.transport();U64.from_address(C.addressof(msg)).value=C.addressof(x);m.fn(0x1e050,None,PTR,U32,U32)(C.addressof(msg),0x4012,64*256+16);values.append(pack)
  check(f'stock count-reply differential N{num}',values[0]==values[1])
 # Reproducibility and negative patch guards, without creating another output.
 code,syms,rels=P.build_helpers();regenerated,manifest=P.patch(stock,code,syms,rels)
 check('patch script deterministic byte-for-byte',regenerated==patched)
 for o,name in ((0x16182,'allocation'),(0x9d480,'helper reservation'),(0x1398,'end symbol'),(0x4ea94,'fixed cache endpoint')):
  corrupt=bytearray(stock);corrupt[o]^=1
  try:P.patch(bytes(corrupt),code,syms,rels)
  except ValueError:rejected=True
  else:rejected=False
  check(f'original-byte guard rejects altered {name}',rejected)
 with tempfile.NamedTemporaryFile(suffix='.elf', delete=False) as f:
  f.write(bytes(corrupt));temp=Path(f.name)
 try:
  try:P.read_stock(temp)
  except ValueError:rejected=True
  else:rejected=False
  check('input identity rejects nonstock ELF',rejected)
 finally:temp.unlink()
 check('original container still has accepted identity',P.sha(args.input.read_bytes())==P.CONTAINER_SHA)
 check('callback mocks have no exceptions' ,not im.callback_errors and not orig.callback_errors)
 check('fixed frame-cache endpoint unchanged',patched[0x4ea94:0x4ea9b]==stock[0x4ea94:0x4ea9b])
 result={'passed':len(tests),'tests':tests,'execution':platform.machine()+' native machine code; Rosetta on this Apple host','stock_sha256':P.sha(stock),'patched_sha256':P.sha(patched),'limitations':['No QNX kernel, ldqnx or actual filesystem used.','Host-backed new and nonfreeing delete mocks; no allocation-failure/exception unwind execution.','Index walk mocked empty; real index callback independently executes sorted insertion.','Count owner entry shim bypasses unrelated playback/dispatcher setup; real count body, send serialization and epilogue execute.','In-memory boundary mocks and entry shim are never written into the output ELF.','No live worker scheduling, actual copy/delete I/O or firmware/PIC integration executed.']}
 args.results.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('passed','execution','patched_sha256')},indent=2))
if __name__=='__main__':main()

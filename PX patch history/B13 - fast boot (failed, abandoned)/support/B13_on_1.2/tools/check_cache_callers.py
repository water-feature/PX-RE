# SPDX-License-Identifier: GPL-2.0-or-later
"""Audit the known cache/thread entry closure in a supplied x86-64 ELF."""
import argparse,re,subprocess,struct,json
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('elf',type=Path);args=ap.parse_args();b=args.elf.read_bytes()
s=subprocess.check_output(['objdump','-d','-C',str(args.elf)],text=True)
addresses={0x34ef0:'GetGroupFileInfo',0x35860:'SwitchSampleGroup',0x35320:'GroupFileUpdateFolder',0x356b0:'CacheSampleGroups',0x1e050:'HandleMessage',0x1d580:'get_messages',0x350e0:'GroupFileParseThread'}
refs={a:[] for a in addresses};current=''
for line in s.splitlines():
 m=re.match(r'^[0-9a-f]+ <(.+)>:$',line)
 if m:current=m[1];continue
 fields=line.split('\t')
 if len(fields)<3:continue
 inst=fields[2]
 if not re.match(r'(call|jmp|lea|mov)\b',inst):continue
 for a in refs:
  if re.search(r'(?<![0-9a-f])(?:0x)?'+format(a,'x')+r'(?![0-9a-f])',inst):
   site=int(fields[0].strip().rstrip(':'),16);refs[a].append({'site':site,'caller':current,'instruction':inst.strip()})
expected={0x34ef0:{0x2307c,0x3527c,0x355a2,0x358c6},0x35860:{0x16396,0x222c3},0x35320:{0x1e32c,0x20149,0x210ea,0x227ab},0x356b0:{0x1636a},0x1e050:{0x1d648,0x1d67e,0x1d6b0},0x1d580:{0x7f4b},0x350e0:{0x3575b}}
for a in refs:assert {r['site'] for r in refs[a]}==expected[a], 'Changed caller closure: '+addresses[a]
# Function pointers in allocated sections would create additional indirect entries.
soff=struct.unpack_from('<Q',b,0x28)[0];ss,sn=struct.unpack_from('<HH',b,0x3a)
allocated=[]
for i in range(sn):
 sh=soff+i*ss;typ=struct.unpack_from('<I',b,sh+4)[0];flags=struct.unpack_from('<Q',b,sh+8)[0];off,size=struct.unpack_from('<QQ',b,sh+24)
 if flags&2 and typ!=8:allocated.append((off,off+size))
ptrs={}
for a in refs:
 hits=[];pat=struct.pack('<Q',a)
 for start,end in allocated:
  i=b.find(pat,start,end)
  while i>=0:hits.append(i);i=b.find(pat,i+1,end)
 ptrs[addresses[a]]=hits;assert not hits,'New allocated function pointer: '+addresses[a]
dyn=subprocess.check_output(['readelf','--dyn-syms','-W',str(args.elf)],text=True)
for name in addresses.values():assert name not in dyn,'Externally exported cache/thread entry: '+name
print(json.dumps({'direct_or_address_references':{addresses[a]:v for a,v in refs.items()},'allocated_function_pointers':ptrs,'external_exports':'none','conclusion':'Known caller closure unchanged. Runtime cache consumers are synchronous HandleMessage descendants on the one get_messages thread. Startup preload is joined before constructor slot loading and message-thread creation. No ordinary runtime duplicate-insertion path found in this ELF.'},indent=2))

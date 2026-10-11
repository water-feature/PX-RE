from pathlib import Path
from elftools.elf.elffile import ELFFile
import hashlib, struct, json
p=Path(__file__).resolve().parent.parent/'inputs/PX RE/PxUpdate_V2.2.2.0.0.bin'
b=p.read_bytes()
assert hashlib.sha256(b).hexdigest()=='a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9'
elfpath=p.parent.parent.parent/'stock.elf'
elfpath.write_bytes(b[13:0xf0da5])
with elfpath.open('rb') as f:
 e=ELFFile(f)
 def read(v,n):
  for s in e.iter_segments():
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=v and v+n<=s['p_vaddr']+s['p_filesz']:
    f.seek(s['p_offset']+v-s['p_vaddr']);return f.read(n)
  raise ValueError(hex(v))
 names=[]
 for i in range(133):
  ptr=struct.unpack('<Q',read(0x2a0160+8*i,8))[0]
  names.append(read(ptr,4).split(b'\0')[0].decode())
 assert names==['f00']+[f'u{i:02}' for i in range(8)]+[f'p{i:02}' for i in range(32)]+[f'u{i:02}' for i in range(8,100)]
 assert read(0x33c10,3)==bytes.fromhex('83fe40')
 assert read(0x16181,5)==bytes.fromhex('bfd0330000')
 assert read(0x33c72,3)==bytes.fromhex('83fe40')
 assert read(0x336e4,4)==bytes.fromhex('4883fb41')
 syms={s.name:s['st_size'] for s in e.get_section_by_name('.symtab').iter_symbols()}
 assert syms['gpGroupNames']==133*8
 assert syms['gGroupSizeCache']==65*8
out={'stock_sha256':hashlib.sha256(b).hexdigest(),'names':dict(enumerate(names)),'active_group_count':65,'category_count':17,'sample_group_allocation':0x33d0,'size_cache_bytes':520,'name_table_entries':133}
Path(__file__).with_name('group_layout.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS: stock hash, all 133 names, bounds, allocation and symbol sizes')

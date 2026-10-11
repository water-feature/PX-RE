# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import re,json,struct
b=Path('pic.bin').read_bytes();rows=[];other=[];cop=[]
for s in Path('pic.dis').read_text().splitlines():
 m=re.match(r'([0-9a-f]{8}): addiu \$sp, \$sp, (-?0x[0-9a-f]+|-?\d+)$',s)
 if m and int(m[2],0)<0:rows.append({'pc':'0x'+m[1],'frame_bytes':-int(m[2],0)})
 if ': ' in s and s.split(': ',1)[1].startswith(('subu $sp','sub $sp','addu $sp','add $sp','move $sp','lw $sp','lui $sp')):other.append(s)
for off in range(0,len(b)-3,4):
 w=struct.unpack_from('<I',b,off)[0]
 if w>>26==16 and (w>>21)&31 in [10,14] and (w>>16)&31==29 and (w>>11)&31==29:cop.append({'pc':hex(0x9d000000+off),'word':hex(w),'rs_field':(w>>21)&31,'rt_field':29,'rd_field':29})
x={'negative_immediate_sp_adjustments':rows,'other_sp_writes':other,'sum_all_frame_sites':sum(r['frame_bytes'] for r in rows),'max_frame':max(rows,key=lambda r:r['frame_bytes']),'cop0_shadow_register_word_candidates':cop,'candidate_cache_to_initial_sp_gap_bytes':0x8007fff0-0x8005b50c,'limitations':'Linear disassembly includes data and omits unsupported instructions. Sum is not a call-path bound; recursion/repeated frames, interrupt nesting and indirect paths unresolved.'}
Path('branch4/pic_stack_inventory.json').write_text(json.dumps(x,indent=2)+'\n')
print(len(rows),'frame sites;',len(cop),'COP0 SP word candidates')

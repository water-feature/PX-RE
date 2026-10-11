#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Emit full immediate-store helper plan. No payload written if audited cave fails."""
from pathlib import Path
import struct,json,hashlib
import build_pic_helpers as h
O=Path(__file__).resolve().parent;R=O.parent;BASE=h.BASE;STATE=h.STATE
stock=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
old=(O/'pre_immediate_store/build_pic_helpers.py').read_text()
def reuse(a,start,end):
 s=old[old.index(start):old.index(end)]
 s=s.replace("a.emit('sll','t0','a0',3);a.emit('sll','t1','a0',2)\n a.emit('addu','t0','t0','t1')","a.emit('sll','t0','a0',4)")
 s=s.replace("a.emit('sll','t2','t0',3);a.emit('sll','t3','t0',2);a.emit('addu','t2','t2','t3')","a.emit('sll','t2','t0',4)")
 s=s.replace("regs=['ra','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','t8','t9']","regs=['ra','a0','a1','t0','t1','t2','t3','t9']")
 s=s.replace("a.emit('addiu','sp','sp',-56);a.emit('sw','ra','sp',52);a.jump(0x9d029120)","a.emit('addiu','sp','sp',-56);a.jump(0x9d029120,('sw','ra','sp',52))")
 s=s.replace("a.branch('beq','a1','t0','get_inst0');a.li('t0',0x5d)\n a.branch('bne','a1','t0','get_stock');a.li('t1',1);a.jump('get_pair')\n a.label('get_inst0');a.li('t1',0)","a.branch('beq','a1','t0','get_pair',('srl','t1','a1',6));a.li('t0',0x5d)\n a.branch('bne','a1','t0','get_stock')")
 s=s.replace("a.branch('beq','v0','zero','get_stock')\n # Read enable parameter directly", "a.branch('beq','v0','zero','get_stock',('addiu','t1','a1',-10))\n # Read enable parameter directly")
 s=s.replace("a.emit('addiu','t1','a1',-10);a.li('t2',0x6b7)","a.li('t2',0x6b7)")
 s=s.replace("a.li('s3',0x4049);a.li('t0',0x54)\n a.emit('xor','t0','a2','t0');a.emit('sltiu','s0','t0',1)","a.li('s3',0x4049);a.emit('srl','s0','a2',6)")
 s=s.replace("a.branch('beq','v0','zero','get_stock',('addiu','t1','a1',-10))", "a.emit('addiu','t1','a1',-10)")
 s=s.replace("a.branch('beq','t2','zero','get_stock');a.ret()", "a.branch('beq','t2','zero','get_stock');a.branch('bne','v0','zero','get_return');a.emit('ori','v0','zero',65535);a.label('get_return');a.ret()")
 exec('def part(a):\n'+s,globals());part(a)
def build():
 a=h.Asm()
 reuse(a," a.func('b15_pic_init')"," # Register one outgoing edit")
 # State: four16B records: epoch32@0, actual@4,cursor@5,dirty@7,capture tag@8,
 # exhausted@9; global feedback staging epoch@12, framing phase@28, bulk depth@44 (unused record tails).
 a.func('b15_pic_receive');a.state();a.li('t0',0x4058)
 a.branch('beq','a0','t0','rx_low',('addiu','t0','zero',0x4059))
 a.branch('beq','a0','t0','rx_high',('addiu','t0','zero',0x404a))
 a.branch('bne','a0','t0','rx_no',('lbu','t0','t9',28));a.li('t1',2)
 a.branch('bne','t0','t1','rx_bad');a.emit('sb','zero','t9',28)
 a.emit('srl','t0','a1',7);a.emit('sltiu','t1','t0',4);a.branch('beq','t1','zero','rx_no',('andi','t1','a1',127));a.emit('sltiu','t2','t1',17);a.branch('beq','t2','zero','rx_no',('lw','t3','t9',12));a.emit('sll','t0','t0',4);a.emit('addu','t9','t9','t0')
 a.emit('lw','t0','t9',0);a.branch('bne','t0','t3','rx_no',('lbu','t0','t9',9));a.branch('bne','t0','zero','rx_no')
 a.emit('sb','t1','t9',4);a.li('t0',1);a.emit('sb','t0','t9',7)
 a.emit('sb','t1','t9',5);a.jump('rx_yes')
 a.label('rx_low');a.emit('sh','a1','t9',12);a.li('t0',1);a.emit('sb','t0','t9',28);a.jump('rx_yes')
 a.label('rx_high');a.emit('lbu','t0','t9',28);a.li('t1',1);a.branch('bne','t0','t1','rx_bad')
 a.emit('sh','a1','t9',14);a.li('t0',2);a.emit('sb','t0','t9',28);a.jump('rx_yes')
 a.label('rx_bad');a.emit('sb','zero','t9',28)
 a.label('rx_no');a.emit('jr','ra');a.li('v0',0)
 a.label('rx_yes');a.emit('jr','ra');a.li('v0',1)
 # Redraw only. Never writes an ordinary parameter.
 a.func('b15_pic_service');regs=['ra','s0','s1','s2','s3'];n=a.save(regs);a.li('s0',0);a.state('s1')
 a.label('service_loop');a.emit('di','t8');a.emit('ehb');a.emit('lbu','s2','s1',7);a.emit('sb','zero','s1',7);a.emit('mtc0_status','t8');a.emit('ehb')
 a.branch('beq','s2','zero','service_next',('andi','t0','s0',1));a.emit('sll','a1','t0',6);a.emit('addu','a1','a1','t0');a.emit('addiu','a1','a1',0x1c)
 a.emit('lui','a0',0x8005);a.emit('addiu','a0','a0',0x2fcc);a.call(0x9d03dcd8);a.branch('beq','v0','zero','service_next')
 a.emit('lui','a0',0x8005);a.emit('addiu','a0','a0',0x2fcc);a.call(0x9d036a38,('addu','a1','v0','zero'))
 a.label('service_next');a.emit('addiu','s0','s0',1);a.emit('sltiu','t0','s0',4);a.branch('bne','t0','zero','service_loop',('addiu','s1','s1',16));a.jump('capture_exit')
 reuse(a," a.func('b15_capture_prepare')"," # Relative encoder entry guard")
 # Held-enable wrapper preserves all setter arguments around snapshot preparation.
 a.func('b15_capture_enable');regs=['ra','a1','a2'];n=a.save(regs)
 a.call('b15_capture_prepare',('addu','a0','a1','zero'));a.restore(regs,n);a.li('a0',0);a.jump(0x9d04dacc,('addiu','a3','zero',1))
 # Local encoder absolute adapter; pending actual uses cursor or stored setting.
 a.func('b15_encoder');a.branch('bne','a0','zero','encoder_original',('addiu','t0','zero',0x1c));a.branch('beq','a2','t0','encoder_special',('addiu','t0','zero',0x5d));a.branch('bne','a2','t0','encoder_original')
 a.label('encoder_special');regs=['ra','s0','s1','s2','s3','s5'];n=a.save(regs,8)
 for d,s in zip(('s0','s1','s2'),('a1','a2','a3')):a.move(d,s)
 a.emit('andi','s3','s0',1);a.emit('lw','s5','sp',n+16)
 a.label('encoder_loop');a.move('a0','s3');a.call(0x9d04d300,('addiu','a1','s1',-10));a.branch('beq','v0','zero','encoder_stock_pair',('sll','a0','s3',1));a.emit('srl','t0','s1',6);a.emit('addu','a0','a0','t0')
 a.label('encoder_pair');a.call('b15_pair');a.emit('lbu','a0','t9',5);a.branch('beq','a0','zero','encoder_next',('addu','a1','s2','zero'))
 a.label('encoder_clamp');a.call(0x9d0816e0,('addu','a2','s5','zero'))
 a.move('s5','v0')
 a.label('encoder_store');a.li('a0',0);a.move('a1','s3');a.move('a2','s1');a.call(0x9d04dacc,('addu','a3','s5','zero'));a.jump('encoder_next')
 a.label('encoder_stock_pair');a.li('a0',0);a.move('a1','s3');a.move('a2','s1');a.move('a3','s2');a.emit('sw','s5','sp',16);a.call('encoder_original')
 a.label('encoder_next');a.li('t0',2);a.branch('bne','s0','t0','encoder_exit');a.branch('bne','s3','zero','encoder_exit',('lw','s5','sp',n+16));a.jump('encoder_loop',('addiu','s3','zero',1))
 a.label('encoder_exit');a.restore(regs,n);a.ret()
 a.label('encoder_original');a.emit('addiu','sp','sp',-32);a.emit('sw','ra','sp',28);a.jump(0x9d04fa74)
 reuse(a," a.func('b15_rx_entry')"," # Account at the central packed transport")
 # Invalidate one pair; full32-bit generation never aliases: exhaustion disables
 # feedback rather than recycling zero. No operation ever waits for feedback.
 a.func('b15_invalidate');a.emit('di','t8');a.emit('ehb');a.call('b15_pair') # ra must be saved by framed callers; use leaf inline instead
 # Replace this call with pair arithmetic to retain leaf ABI.
 a.rows=a.rows[:-2];a.emit('sll','t0','a0',4);a.state();a.emit('addu','t9','t9','t0')
 a.emit('lw','t0','t9',0);a.emit('addiu','t0','t0',1);a.emit('sw','t0','t9',0);a.branch('bne','t0','zero','invalidate_clear');a.li('t0',1);a.emit('sb','t0','t9',9)
 a.label('invalidate_clear');a.emit('sb','zero','t9',4);a.emit('sb','zero','t9',5);a.li('t0',1);a.emit('sb','t0','t9',7);a.emit('mtc0_status','t8');a.emit('ehb');a.ret()
 a.func('b15_token_send');regs=['ra','s0','s1','s2'];n=a.save(regs);a.emit('di','s2');a.emit('ehb');a.move('s0','a0');a.call('b15_pair');a.emit('lw','s1','t9',0)
 a.emit('addiu','t0','s0',0x404b);a.emit('sll','t0','t0',16);a.emit('andi','a0','s1',65535);a.call('transport_original',('or','a0','a0','t0'))
 a.emit('addiu','t0','s0',0x4053);a.emit('sll','t0','t0',16);a.emit('srl','a0','s1',16);a.call('transport_original',('or','a0','a0','t0'));a.emit('mtc0_status','s2');a.emit('ehb');a.jump('transport_exit')
 # Central packed-transport observer handles all ordinary absolute origins.
 a.func('b15_transport');a.emit('srl','t0','a0',16);a.emit('sltiu','t1','t0',0x9b7);a.branch('beq','t1','zero','transport_original',('andi','t1','t0',0x7ff))
 a.emit('sltiu','t2','t1',0x41);a.branch('bne','t2','zero','transport_id');a.emit('addiu','t1','t1',-0x41)
 a.label('transport_id');a.li('t3',0x1c);a.branch('beq','t1','t3','transport_vel',('addiu','t3','t1',-0x12));a.emit('andi','t3','t3',0xfffd);a.branch('beq','t3','zero','transport_lifecycle',('addiu','t3','t1',-0x22));a.emit('sltiu','t3','t3',3);a.branch('bne','t3','zero','transport_lifecycle')
 a.jump('transport_original')
 a.label('transport_vel');a.emit('andi','t3','a0',65535);a.branch('beq','t3','zero','transport_original',('sltiu','t4','t3',17));a.branch('beq','t4','zero','transport_original')
 a.label('transport_lifecycle');a.state();a.emit('lw','t3','t9',44);a.branch('bne','t3','zero','transport_original')
 regs=['ra','s0','s1','s2'];n=a.save(regs);a.emit('di','s2');a.emit('ehb');a.move('s0','a0');a.emit('srl','s1','t0',11);a.emit('andi','s1','s1',1);a.emit('sll','s1','s1',1);a.emit('xori','t2','t2',1);a.emit('addu','s1','s1','t2')
 a.call('b15_invalidate',('addu','a0','s1','zero'));a.call('b15_token_send',('addu','a0','s1','zero'));a.move('a0','s1');a.call('b15_pair');a.emit('srl','t0','s0',16);a.emit('andi','t0','t0',0x7ff);a.li('t1',0x1c);a.branch('beq','t0','t1','transport_cursor');a.li('t1',0x5d);a.branch('bne','t0','t1','transport_restore');a.label('transport_cursor');a.emit('andi','t0','s0',65535);a.emit('sb','t0','t9',5);a.label('transport_restore');a.move('a0','s0');a.call('transport_original');a.emit('mtc0_status','s2');a.emit('ehb');a.label('transport_exit');a.restore(regs,n);a.ret()
 a.label('transport_original');a.emit('addiu','sp','sp',-24);a.emit('sw','ra','sp',20);a.jump(0x9d075c24)
 # Common nonwaiting invalidation/token notification for a bank mask.
 a.func('b15_context');regs=['ra','s0','s1','s2','s3'];n=a.save(regs);a.move('s0','a0');a.move('s1','a1');a.li('s2',0);a.li('s3',1)
 a.label('context_loop');a.emit('and','t0','s0','s3');a.branch('beq','t0','zero','context_next');a.call('b15_invalidate',('addu','a0','s2','zero'))
 a.branch('beq','s1','zero','context_next');a.call('b15_token_send',('addu','a0','s2','zero'))
 a.label('context_next');a.emit('addiu','s2','s2',1);a.emit('sltiu','t0','s2',4);a.branch('bne','t0','zero','context_loop',('sll','s3','s3',1));a.jump('capture_exit')
 # Replay wrapper: tokens/bulk before stock, END after. Raw wrappers only invalidate
 # locally before replacement and request display-only refresh after. No gates.
 a.func('b15_worker');regs=['ra','s0','s1','s2','s3','s4','s5','s6'];n=a.save(regs,8)
 for d,s in zip(('s0','s1','s2','s3','s5','s6'),('a0','a1','a2','a3','t6','t7')):a.move(d,s)
 for off in (16,20):a.emit('lw','t0','sp',n+off);a.emit('sw','t0','sp',off)
 a.li('s4',15);a.branch('beq','s6','zero','worker_invalidate');a.li('s4',3);a.li('t0',2);a.branch('beq','s6','t0','worker_bulk');a.li('s4',15);a.branch('beq','s0','t0','worker_bulk');a.li('s4',3);a.emit('sll','t0','s0',1);a.emit('sllv','s4','s4','t0')
 a.label('worker_bulk');a.state();a.li('t0',1);a.emit('sw','t0','t9',44)
 a.label('worker_invalidate');a.move('a0','s4');a.call('b15_context',('addu','a1','s6','zero'));a.branch('beq','s6','zero','worker_stock')
 a.emit('lui','a0',0x404f);a.call('transport_original',('or','a0','a0','s4'))
 a.label('worker_stock')
 for d,s in zip(('a0','a1','a2','a3'),('s0','s1','s2','s3')):a.move(d,s)
 a.emit('jalr','s5');a.emit('nop');a.emit('sw','v0','sp',16);a.branch('bne','s6','zero','worker_end')
 # Raw replacement invalidated local epoch before stock; synchronize tokens now
 # WITHOUT advancing it a second time. Refresh cannot write parameter arrays.
 a.li('s2',0)
 a.label('worker_refresh_loop');a.call('b15_token_send',('addu','a0','s2','zero'));a.emit('addiu','s2','s2',1);a.emit('sltiu','t0','s2',4);a.branch('bne','t0','zero','worker_refresh_loop')
 a.emit('lui','a0',0x4057);a.jump('worker_send',('ori','a0','a0',15))
 a.label('worker_end');a.state();a.emit('sw','zero','t9',44);a.emit('lui','a0',0x4050);a.emit('or','a0','a0','s4')
 a.label('worker_send');a.call('transport_original');a.emit('lw','v0','sp',16);a.restore(regs,n);a.ret()
 hooks=[]
 for name,pc,mode in [('replay',0x9d07c368,1),('load',0x9d040418,0),('import',0x9d0744cc,0),('edit_apply',0x9d046e4c,0),('defaults',0x9d04cd14,0),('reset',0x9d07c2ac,2),('compare',0x9d04feb4,0),('restore',0x9d04ffc4,0)]:
  a.func('b15_'+name);a.emit('label_hi','t6','stock_'+name);a.emit('label_lo','t6','stock_'+name);a.jump('b15_worker',('addiu','t7','zero',mode))
  a.label('stock_'+name)
  words=struct.unpack_from('<III',stock,pc-BASE+0x2a0)
  if words[1]>>26==21: # leaf compare/copy starts BNE likely; preserve annulment
   a.emit('raw',words[0]);w=words[1];rs=h.R
   names={v:k for k,v in rs.items()};im=w&65535;im=im if im<32768 else im-65536
   target=pc+8+4*im
   a.branch('beq',names[(w>>21)&31],names[(w>>16)&31],'stock_'+name+'_false')
   a.emit('raw',words[2]);a.jump(target);a.label('stock_'+name+'_false');a.jump(pc+12)
  else:
   a.emit('raw',words[0]);a.jump(pc+8,('raw',words[1]))
  hooks.append({'name':name,'pc':hex(pc),'target':'b15_'+name,'mode':mode,'expected_words':[hex(w) for w in words[:2]]})
 # Explicit cold startup call bypasses runtime notifications, but initializes all
 # owned state before stock defaults. Only the verified052d0c call uses this.
 a.func('b15_cold_defaults');a.move('t5','ra');a.call('b15_pic_init');a.move('ra','t5');a.jump('stock_defaults')
 # SampleVel/legacy-velocity dynamic clamp must use the setter bank for explicit
 # A/B edits, while bank2 keeps stock UI-selected-bank semantics.
 a.func('b15_setter_bank');a.li('t0',2);a.branch('beq','s2','t0','setter_ui');a.emit('andi','v0','s2',1);a.ret();a.label('setter_ui');a.jump(0x9d031b70)
 # Atomic immediate SampleVel store+send; unrelated setters retain stock entry.
 a.func('b15_setter');a.li('t0',0x1c);a.branch('beq','a2','t0','setter_atomic',('addiu','t0','zero',0x5d));a.branch('bne','a2','t0','setter_original')
 a.label('setter_atomic');regs=['ra','s0'];n=a.save(regs);a.emit('di','s0');a.emit('ehb');a.call('setter_original');a.emit('mtc0_status','s0');a.emit('ehb');a.restore(regs,n);a.ret()
 a.label('setter_original');a.emit('addiu','sp','sp',-48);a.emit('sw','ra','sp',44);a.jump(0x9d04dad4)
 # Display-only unknown sentinel. Both fresh and cached field redraws call
 # the common append formatter, so FFFF is handled for SampleVel IDs only.
 # Reuse stock strcat and the last two dashes of verified literal611bc "---".
 a.func('b15_format');a.emit('ori','t0','zero',65535)
 a.branch('bne','a1','t0','format_original',('addiu','t0','zero',0x1c))
 a.branch('beq','a0','t0','format_pending',('addiu','t0','zero',0x5d))
 a.branch('bne','a0','t0','format_original')
 a.label('format_pending');a.emit('lui','a1',0x9d06);a.emit('ori','a1','a1',0x11bd);a.jump(0x9d08169c,('addu','a0','a2','zero'))
 a.label('format_original');a.emit('addiu','sp','sp',-48);a.jump(0x9d05f7fc,('sw','ra','sp',44))
 a.compact();code=a.bytes();end=BASE+len(code)
 report={'status':'UNPLACED_FULL_HELPER_PLAN','bytes':len(code),'cave_bytes':2400,'shortfall':max(0,len(code)-2400),'fits':end<=0x9d000c00,'complete_hook_installation_verified':False,'sha256':hashlib.sha256(code).hexdigest(),'functions':{n:(a.labels[a.functions[i+1]] if i+1<len(a.functions) else end)-a.labels[n] for i,n in enumerate(a.functions)},'hooks':hooks,'state_bytes':64,'limits':'Full emitted helper plan including lifecycle/raw/replay adapters; exact hook installation/caller routing still requires validation. No payload produced.'}
 (O/'pic_absolute_unplaced.bin').write_bytes(code);(O/'pic_absolute_assembly.json').write_text(json.dumps({'base':hex(BASE),'labels':{k:hex(v) for k,v in a.labels.items()},'rows':a.rows,'functions':a.functions},indent=2)+'\n');(O/'pic_absolute_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':build()

#!/usr/bin/env python3
"""Emit bounded B15 PIC helper work. No input payload is modified or packaged.
Some caller adapters remain unresolved; emission is not firmware approval.
"""
from pathlib import Path
import struct,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'b14_ui_candidate_work'));from build_display import enc as inherited_enc
sys.path.insert(0,str(ROOT/'b14_candidate_work'));from build_b14 import R
BASE=0x9d0002a0;LIMIT=0x9d000c00;STATE=0x80057aa0
class Asm:
 def __init__(self):self.rows=[];self.labels={};self.functions=[]
 def label(self,n):assert n not in self.labels;self.labels[n]=BASE+4*len(self.rows)
 def emit(self,*r):self.rows.append(r)
 def block(self,rows):
  for r in rows:self.emit(*r)
 def state(self,r='t9'):self.emit('lui',r,0x8005);self.emit('ori',r,r,0x7aa0)
 def move(self,d,s):self.emit('addu',d,s,'zero')
 def li(self,d,n):self.emit('addiu',d,'zero',n)
 def branch(self,op,r,s,target,delay=('nop',)):self.emit(op,r,s,target);self.emit(*delay)
 def jump(self,name,delay=('nop',)):self.emit('j',name);self.emit(*delay)
 def call(self,name,delay=('nop',)):self.emit('jal',name);self.emit(*delay)
 def ret(self):self.emit('jr','ra');self.emit('nop')
 def func(self,name,rows=None):self.functions.append(name);self.label(name);self.block(rows or [])
 def save(self,regs,extra=0):
  n=((16+extra+4*len(regs)+7)//8)*8;self.emit('addiu','sp','sp',-n)
  for i,r in enumerate(regs):self.emit('sw',r,'sp',n-4*(i+1))
  return n
 def restore(self,regs,n):
  for i,r in enumerate(regs):self.emit('lw',r,'sp',n-4*(i+1))
  self.emit('addiu','sp','sp',n)
 def compact(self):
  before=len(self.rows);labels={k:(v-BASE)//4 for k,v in self.labels.items()}
  i=1
  while i+1<len(self.rows):
   control=self.rows[i];prev=self.rows[i-1];op=control[0]
   entries=set(labels.values())
   if op not in ('j','jal','jr','beq','bne') or self.rows[i+1]!=('nop',) or any(j in entries for j in (i-1,i,i+1)):
    i+=1;continue
   if i>1 and self.rows[i-2][0] in ('j','jal','jr','beq','bne'):
    i+=1;continue
   if prev[0] not in ('addu','subu','sll','srl','slt','sltu','xor','or','and','addiu','lui','ori','andi','sltiu','sw','sh','sb','lw','lhu','lbu'):
    i+=1;continue
   written=set() if prev[0] in ('sw','sh','sb') else {prev[1]}
   readcond=set(control[1:3]) if op in ('beq','bne') else ({control[1]} if op=='jr' else set())
   if written&readcond or (op=='jal' and 'ra' in prev[1:]):
    i+=1;continue
   self.rows[i-1:i+2]=[control,prev]
   labels={k:(v-1 if v>=i else v) for k,v in labels.items()}
   i=max(1,i-1)
  self.labels={k:BASE+4*v for k,v in labels.items()}
  return before-len(self.rows)
 def bytes(self):
  result=bytearray()
  for i,row in enumerate(self.rows):
   pc=BASE+4*i;op,*a=row
   if op in ('j','jal'):row=(op,self.labels.get(a[0],a[0]))
   if op=='jalr':w=R[a[0]]<<21|31<<11|9
   elif op=='label_hi':w=15<<26|R[a[0]]<<16|(self.labels[a[1]]>>16)
   elif op=='label_lo':w=13<<26|R[a[0]]<<21|R[a[0]]<<16|(self.labels[a[1]]&65535)
   elif op in ('ori','xori','sltiu'):
    w={'ori':13,'xori':14,'sltiu':11}[op]<<26|R[a[1]]<<21|R[a[0]]<<16|(a[2]&65535)
   elif op in ('or','and','xor','sltu'):
    w=R[a[1]]<<21|R[a[2]]<<16|R[a[0]]<<11|{'or':37,'and':36,'xor':38,'sltu':43}[op]
   elif op=='sllv':w=R[a[2]]<<21|R[a[1]]<<16|R[a[0]]<<11|4
   elif op=='srl':w=R[a[1]]<<16|R[a[0]]<<11|a[2]<<6|2
   elif op=='raw':w=a[0]
   elif op=='mfc0_status':w=0x40006000|R[a[0]]<<16
   elif op=='mfc0_count':w=0x40004800|R[a[0]]<<16
   else:w=inherited_enc(pc,row,self.labels)
   result.extend(struct.pack('<I',w))
  return bytes(result)

def build():
 a=Asm()
 # Leaf cold initializer; safe to call before ordinary default initialization.
 a.func('b15_pic_init');a.state('t0');a.li('t1',16)
 a.label('init_loop');a.emit('sw','zero','t0',0);a.emit('addiu','t0','t0',4)
 a.emit('addiu','t1','t1',-1);a.branch('bne','t1','zero','init_loop');a.ret()
 # pair address in t9 from a0. Uses t0,t1 only; no stack frame.
 a.func('b15_pair');a.emit('sll','t0','a0',3);a.emit('sll','t1','a0',2)
 a.emit('addu','t0','t0','t1');a.state();a.emit('addu','t9','t9','t0');a.ret()
 # Effective display getter: original (bank,id) ABI, ordinary getter tail fallback.
 a.func('b15_effective_get');a.li('t0',0x1c)
 a.branch('beq','a1','t0','get_inst0');a.li('t0',0x5d)
 a.branch('bne','a1','t0','get_stock');a.li('t1',1);a.jump('get_pair')
 a.label('get_inst0');a.li('t1',0)
 a.label('get_pair');a.emit('andi','t0','a0',1);a.emit('sll','t0','t0',1);a.emit('addu','t0','t0','t1')
 a.emit('sll','t2','t0',3);a.emit('sll','t3','t0',2);a.emit('addu','t2','t2','t3');a.state()
 a.emit('addu','t9','t9','t2');a.emit('lbu','v0','t9',4)
 a.branch('beq','v0','zero','get_stock')
 # Read enable parameter directly: SampleVel ID minus10h.
 a.emit('addiu','t1','a1',-10);a.li('t2',0x6b7)
 a.emit('andi','t3','a0',1);a.branch('beq','t3','zero','get_enable_a');a.emit('addu','t1','t1','t2')
 a.label('get_enable_a');a.emit('sll','t1','t1',1);a.emit('lui','t2',0x8000)
 a.emit('addiu','t2','t2',0x46c);a.emit('addu','t2','t2','t1');a.emit('lhu','t2','t2',0)
 a.branch('beq','t2','zero','get_stock');a.ret()
 a.label('get_stock');a.jump(0x9d04d300)
 # Register one outgoing edit under IRQ exclusion. a0=pair, return1 accepted.
 a.func('b15_pic_edit');a.emit('sltiu','t0','a0',4);a.branch('beq','t0','zero','edit_no');a.state();a.emit('lbu','t0','t9',54)
 a.branch('bne','t0','zero','edit_no')
 a.emit('sll','t0','a0',3);a.emit('sll','t1','a0',2);a.emit('addu','t0','t0','t1');a.emit('addu','t9','t9','t0')
 a.emit('di','t8');a.emit('ehb',);a.emit('lhu','t0','t9',0);a.emit('lhu','t1','t9',2)
 a.emit('subu','t1','t0','t1');a.emit('andi','t1','t1',65535);a.emit('sltiu','t1','t1',32767)
 a.branch('beq','t1','zero','edit_unlock_no');a.emit('addiu','t0','t0',1);a.emit('sh','t0','t9',0)
 a.emit('mtc0_status','t8');a.emit('ehb',);a.li('v0',1);a.ret()
 a.label('edit_unlock_no');a.emit('mtc0_status','t8');a.emit('ehb',)
 a.label('edit_no');a.li('v0',0);a.ret()
 # Receive adapter callable from ISR: a0=cmd,a1=payload. NO draw or parameter setter.
 a.func('b15_pic_receive');a.li('t0',0x4052);a.branch('beq','a0','t0','rx_barrier')
 a.li('t0',0x404a);a.branch('beq','a0','t0','rx_pair');a.li('t0',0x4051)
 a.branch('bne','a0','t0','rx_no')
 a.label('rx_pair');a.emit('srl','t0','a1',7);a.emit('andi','t0','t0',3)
 a.emit('sll','t1','t0',3);a.emit('sll','t2','t0',2);a.emit('addu','t1','t1','t2');a.state()
 a.move('t7','t9');a.emit('addu','t9','t9','t1');a.emit('srl','t1','a1',9)
 a.emit('lbu','t2','t9',6);a.branch('bne','t1','t2','rx_no')
 a.emit('andi','t1','a1',31);a.emit('sltiu','t2','t1',17);a.branch('beq','t2','zero','rx_no')
 a.li('t2',0x404a);a.branch('beq','a0','t2','rx_actual')
 a.emit('andi','t2','a1',0x40);a.branch('bne','t2','zero','rx_snapshot')
 a.emit('lhu','t2','t9',0);a.emit('lhu','t3','t9',2);a.branch('beq','t2','t3','rx_no')
 a.emit('addiu','t3','t3',1);a.emit('sh','t3','t9',2);a.jump('rx_setting')
 a.label('rx_snapshot');a.emit('lbu','t2','t7',54);a.li('t3',1);a.branch('bne','t2','t3','rx_no')
 # Exact pair-mask membership using the architectural variable shift.
 a.li('t3',1);a.emit('sllv','t3','t3','t0');a.emit('lbu','t2','t7',55);a.emit('and','t2','t2','t3');a.branch('beq','t2','zero','rx_no')
 a.li('t2',1);a.emit('sb','t2','t9',9)
 a.label('rx_setting');a.emit('sb','t1','t9',5);a.emit('lbu','t2','t9',7);a.emit('ori','t2','t2',2)
 a.jump('rx_success',('sb','t2','t9',7))
 a.label('rx_actual');a.emit('sb','t1','t9',4);a.emit('lbu','t2','t9',7);a.emit('ori','t2','t2',1)
 a.jump('rx_success',('sb','t2','t9',7))
 a.label('rx_barrier');a.state();a.emit('lbu','t0','t9',54);a.li('t1',1)
 a.branch('bne','t0','t1','rx_no');a.emit('lhu','t0','t9',52);a.emit('sll','t0','t0',9)
 a.emit('lbu','t1','t9',55);a.emit('or','t0','t0','t1');a.branch('bne','t0','a1','rx_no')
 a.move('t7','t9');a.li('t0',4);a.move('t2','t1')
 a.label('rx_check_loop');a.emit('andi','t3','t2',1);a.branch('beq','t3','zero','rx_check_next')
 a.emit('lbu','t3','t9',9);a.branch('beq','t3','zero','rx_no')
 a.label('rx_check_next');a.emit('addiu','t9','t9',12);a.emit('srl','t2','t2',1);a.emit('addiu','t0','t0',-1)
 a.branch('bne','t0','zero','rx_check_loop');a.move('t9','t7');a.li('t0',4)
 a.label('rx_complete_loop');a.emit('andi','t3','t1',1);a.branch('beq','t3','zero','rx_complete_next')
 a.emit('lhu','t3','t9',0);a.emit('sh','t3','t9',2)
 a.label('rx_complete_next');a.emit('addiu','t9','t9',12);a.emit('srl','t1','t1',1);a.emit('addiu','t0','t0',-1)
 a.branch('bne','t0','zero','rx_complete_loop');a.li('t0',2);a.emit('sb','t0','t7',54)
 a.label('rx_success');a.li('v0',1);a.ret()
 a.label('rx_no');a.li('v0',0);a.ret()
 # Main consumer: atomically snapshot mailbox, then private non-echo store and redraw.
 a.func('b15_pic_service');regs=['ra','s0','s1','s2','s3'];n=a.save(regs);a.li('s0',0);a.state('s1')
 a.label('service_loop');a.emit('di','t8');a.emit('ehb',);a.emit('lbu','s2','s1',7)
 a.emit('lbu','s3','s1',5);a.emit('sb','zero','s1',7);a.emit('mtc0_status','t8');a.emit('ehb',)
 a.branch('beq','s2','zero','service_next')
 a.emit('andi','t0','s0',1);a.emit('sll','t1','t0',6);a.emit('addu','t0','t0','t1');a.emit('addiu','t0','t0',0x1c)
 a.emit('andi','t1','s2',2);a.branch('beq','t1','zero','service_dirty')
 a.move('t1','t0');a.emit('sltiu','t2','s0',2);a.branch('bne','t2','zero','service_bank_a')
 a.emit('addiu','t1','t1',0x6b7)
 a.label('service_bank_a');a.emit('sll','t1','t1',1);a.emit('lui','t2',0x8000);a.emit('addiu','t2','t2',0x46c)
 a.emit('addu','t1','t1','t2');a.emit('sh','s3','t1',0)
 a.label('service_dirty');a.emit('lui','a0',0x8005);a.emit('addiu','a0','a0',0x2fcc);a.move('a1','t0')
 a.call(0x9d03dcd8);a.branch('beq','v0','zero','service_next')
 a.emit('lui','a0',0x8005);a.emit('addiu','a0','a0',0x2fcc);a.call(0x9d036a38,('addu','a1','v0','zero'))
 a.label('service_next');a.emit('addiu','s0','s0',1);a.emit('sltiu','t0','s0',4)
 a.branch('bne','t0','zero','service_loop',('addiu','s1','s1',12));a.jump('capture_exit')
 # A fence starts a snapshot query. The caller must freeze edits and defer the
 # WHOLE operation, not return from a synchronous loader and continue its caller.
 a.func('b15_pic_fence_start');a.state();a.emit('di','t8');a.emit('ehb',)
 a.emit('addiu','t0','a0',-1);a.emit('sltiu','t0','t0',15)
 a.branch('beq','t0','zero','edit_unlock_no')
 a.emit('lbu','t0','t9',54);a.emit('addiu','t0','t0',-1);a.emit('sltiu','t0','t0',2)
 a.branch('bne','t0','zero','edit_unlock_no')
 a.li('t0',1);a.emit('sb','t0','t9',54);a.emit('sb','a0','t9',55)
 a.emit('lhu','t0','t9',52);a.emit('addiu','t0','t0',1);a.emit('andi','t0','t0',127);a.emit('sh','t0','t9',52)
 a.emit('sw','a1','t9',48);a.emit('sw','zero','t9',56)
 for off in (9,21,33,45):a.emit('sb','zero','t9',off)
 a.emit('sll','t0','t0',9);a.emit('or','a0','a0','t0');a.emit('mtc0_status','t8');a.emit('ehb',)
 a.emit('lui','t0',0x4052);a.jump(0x9d075c1c,('or','a0','a0','t0'))
 a.func('b15_pic_fence_poll');a.state();a.emit('lbu','v0','t9',54);a.li('t0',1)
 a.branch('bne','v0','t0','poll_return');a.emit('lw','t0','t9',48);a.emit('subu','t0','a0','t0');a.emit('slt','t0','t0','zero')
 a.branch('bne','t0','zero','poll_return');a.li('v0',3);a.emit('sb','v0','t9',54);a.li('t0',1);a.emit('sw','t0','t9',56)
 a.label('poll_return');a.ret()
 # Capture entries share one framed packet loop and epilogue. s3 is command.
 a.func('b15_capture_prepare');regs=['ra','s0','s1','s2','s3'];n=a.save(regs)
 a.move('s2','s1');a.move('s1','a0');a.li('t0',128)
 a.branch('beq','s2','t0','capture_exit');a.li('s3',0x4048)
 a.emit('lhu','s0','s0',6);a.emit('sltu','s0','zero','s0')
 a.emit('sll','t0','a0',1);a.emit('andi','t0','t0',2)
 a.jump('capture_start',('addu','s0','s0','t0'))
 a.func('b15_capture_commit');n=a.save(regs)
 a.move('s1','a1');a.li('s3',0x4049);a.li('t0',0x54)
 a.emit('xor','t0','a2','t0');a.emit('sltiu','s0','t0',1)
 a.emit('sll','t0','a1',1);a.emit('andi','t0','t0',2)
 a.emit('addu','s0','s0','t0')
 a.label('capture_start');a.li('t0',0x4048)
 a.branch('beq','s3','t0','capture_pair')
 a.emit('srl','a0','s0',1);a.emit('andi','a1','s0',1)
 a.emit('sll','t0','a1',6);a.emit('addu','a1','a1','t0')
 a.call(0x9d04d300,('addiu','a1','a1',0x14));a.move('s2','v0')
 a.label('capture_pair');a.move('a0','s0');a.call('b15_pair')
 a.emit('lbu','t0','t9',8);a.li('t1',0x4049)
 a.branch('beq','s3','t1','capture_pack')
 a.emit('addiu','t0','t0',1);a.emit('andi','t0','t0',127);a.emit('sb','t0','t9',8)
 a.label('capture_pack');a.emit('sll','t0','t0',9)
 a.emit('sll','t1','s0',7);a.emit('or','t0','t0','t1')
 a.emit('or','a0','t0','s2');a.emit('sll','t0','s3',16)
 a.call(0x9d075c1c,('or','a0','a0','t0'))
 a.li('t0',2);a.branch('bne','s1','t0','capture_exit')
 a.emit('sltiu','t0','s0',2);a.branch('beq','t0','zero','capture_exit')
 a.jump('capture_start',('addiu','s0','s0',2))
 a.label('capture_exit');a.restore(regs,n);a.li('v0',0);a.ret()
 # Relative encoder entry guard; active pairs use QNX base, disabled pairs stock.
 a.func('b15_encoder');a.branch('bne','a0','zero','encoder_original');a.li('t0',0x1c)
 a.branch('beq','a2','t0','encoder_special');a.li('t0',0x5d)
 a.branch('bne','a2','t0','encoder_original')
 a.label('encoder_special');regs=['ra','s0','s1','s2','s3','s4'];n=a.save(regs,8)
 a.move('s0','a1');a.move('s1','a2');a.move('s2','a3');a.emit('lw','s4','sp',n+16)
 a.emit('andi','s3','a1',1);a.label('encoder_loop')
 a.move('a0','s3');a.call(0x9d04d300,('addiu','a1','s1',-10));a.branch('beq','v0','zero','encoder_stock_pair')
 a.emit('sll','a0','s3',1);a.li('t0',0x5d);a.branch('bne','s1','t0','encoder_inst')
 a.emit('addiu','a0','a0',1)
 a.label('encoder_inst');a.emit('sw','a0','sp',20);a.call('b15_pic_edit');a.branch('beq','v0','zero','encoder_sent')
 a.li('t0',16);a.emit('slt','t1','t0','s2');a.branch('beq','t1','zero','encoder_low');a.move('s2','t0')
 a.label('encoder_low');a.li('t0',-16);a.emit('slt','t1','s2','t0');a.branch('beq','t1','zero','encoder_pack');a.move('s2','t0')
 a.label('encoder_pack');a.emit('lw','t2','sp',20);a.emit('addiu','a0','t2',0x404b);a.emit('sll','a0','a0',16)
 a.emit('andi','t0','s2',65535);a.call(0x9d075c1c,('or','a0','a0','t0'));a.jump('encoder_sent')
 a.label('encoder_stock_pair');a.li('a0',0);a.move('a1','s3');a.move('a2','s1');a.move('a3','s2')
 a.emit('sw','s4','sp',16);a.call('encoder_original')
 a.label('encoder_sent');a.li('t0',2);a.branch('bne','s0','t0','encoder_exit');a.branch('bne','s3','zero','encoder_exit')
 a.jump('encoder_loop',('addiu','s3','zero',1))
 a.label('encoder_exit');a.restore(regs,n);a.ret()
 a.label('encoder_original');a.emit('addiu','sp','sp',-32);a.emit('sw','ra','sp',28);a.jump(0x9d04fa74)
 # ISR interior wrapper: preserve o32 caller registers touched by receive helper.
 a.func('b15_rx_entry');regs=['ra','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','t8','t9'];n=a.save(regs)
 a.emit('lw','a0','sp',n+20);a.emit('lw','a1','sp',n+16);a.call('b15_pic_receive')
 a.restore(regs,n);a.branch('bne','v0','zero','rx_entry_handled')
 a.emit('lw','v0','sp',20);a.jump(0x9d0511ac,('addiu','v1','zero',0x402e))
 a.label('rx_entry_handled');a.jump(0x9d05153c)
 # Main function entry wrapper preserves its arguments and original prologue.
 a.func('b15_main_entry');regs=['ra','a0','a1'];n=a.save(regs);a.call('b15_pic_service');a.restore(regs,n)
 a.emit('addiu','sp','sp',-56);a.emit('sw','ra','sp',52);a.jump(0x9d029120)
 # Account at the central packed transport, covering both A and direct B setters.
 a.func('b15_absolute_account');a.emit('srl','t0','a0',16);a.emit('sltiu','t2','t0',0x9b7);a.branch('beq','t2','zero','account_original');a.emit('andi','t1','t0',0x7ff)
 a.li('t2',0x1c);a.branch('beq','t1','t2','account_special');a.li('t2',0x5d)
 a.branch('bne','t1','t2','account_original')
 a.label('account_special');a.state();a.emit('lw','t2','t9',60);a.branch('bne','t2','zero','account_original')
 regs=['ra','s0'];n=a.save(regs);a.move('s0','a0');a.emit('srl','a0','t0',11);a.emit('andi','a0','a0',1)
 a.emit('sll','a0','a0',1);a.li('t2',0x5d);a.branch('bne','t1','t2','account_inst')
 a.emit('addiu','a0','a0',1)
 a.label('account_inst');a.call('b15_pic_edit');a.move('a0','s0');a.restore(regs,n)
 a.branch('beq','v0','zero','account_refused')
 a.label('account_original');a.emit('addiu','sp','sp',-24);a.emit('sw','ra','sp',20);a.jump(0x9d075c24)
 a.label('account_refused');a.ret()
 # Emit ordered context command per pair, carrying that pair's epoch.
 # a0=4-bit pair mask,a1=0 BEGIN / 1 END. Whole-operation fence precedes raw replacement.
 a.func('b15_context_send');regs=['ra','s0','s1','s2','s3'];n=a.save(regs)
 a.move('s0','a0');a.move('s1','a1');a.state();a.li('t0',1);a.emit('subu','t0','t0','a1');a.emit('sw','t0','t9',60);a.li('s2',0);a.li('s3',1)
 a.label('context_loop');a.emit('and','t0','s0','s3');a.branch('beq','t0','zero','context_next')
 a.move('a0','s2');a.call('b15_pair');a.emit('lbu','t0','t9',6);a.emit('sll','t0','t0',9)
 a.emit('or','a0','t0','s3');a.emit('addiu','t0','s1',0x404f);a.emit('sll','t0','t0',16)
 a.call(0x9d075c1c,('or','a0','a0','t0'))
 a.label('context_next');a.emit('addiu','s2','s2',1);a.emit('sltiu','t0','s2',4)
 a.branch('bne','t0','zero','context_loop',('sll','s3','s3',1));a.jump('capture_exit')
 # Finish only after the main consumer applied all fenced snapshots. a0=replace.
 a.func('b15_pic_fence_finish');a.state();a.emit('di','t8');a.emit('ehb',)
 a.emit('lbu','t0','t9',54);a.li('t1',2);a.branch('bne','t0','t1','finish_no')
 a.move('t7','t9');a.emit('lbu','t0','t9',55);a.li('t1',4)
 a.label('finish_check');a.emit('andi','t2','t0',1);a.branch('beq','t2','zero','finish_check_next')
 a.emit('lbu','t2','t9',7);a.branch('bne','t2','zero','finish_no')
 a.label('finish_check_next');a.emit('addiu','t9','t9',12);a.emit('srl','t0','t0',1);a.emit('addiu','t1','t1',-1)
 a.branch('bne','t1','zero','finish_check');a.move('t9','t7');a.emit('lbu','t0','t9',55);a.li('t1',4)
 a.label('finish_apply');a.emit('andi','t2','t0',1);a.branch('beq','t2','zero','finish_apply_next')
 a.branch('beq','a0','zero','finish_keep_epoch');a.emit('lbu','t2','t9',6)
 a.emit('addiu','t2','t2',1);a.emit('andi','t2','t2',127);a.emit('sb','t2','t9',6);a.emit('sb','zero','t9',4)
 a.label('finish_keep_epoch');a.emit('sb','zero','t9',9)
 a.label('finish_apply_next');a.emit('addiu','t9','t9',12);a.emit('srl','t0','t0',1);a.emit('addiu','t1','t1',-1)
 a.branch('bne','t1','zero','finish_apply');a.emit('sb','zero','t7',54);a.emit('sb','zero','t7',55)
 a.emit('mtc0_status','t8');a.emit('ehb',);a.li('v0',1);a.ret()
 a.label('finish_no');a.emit('mtc0_status','t8');a.emit('ehb',);a.li('v0',0);a.ret()
 compacted_words=a.compact();code=a.bytes();end=BASE+len(code)
 (OUT/'pic_helpers_unplaced.bin').write_bytes(code)
 (OUT/'pic_helpers_assembly.json').write_text(json.dumps({'base':hex(BASE),'functions':a.functions,'labels':{k:hex(v) for k,v in a.labels.items()},'rows':a.rows},indent=2)+'\n')
 result={'status':'EMITTED_COMPONENT_NOT_INTEGRATED','ready_for_hardware':False,'helper_bytes':len(code),
 'helper_sizes':{k:((a.labels[a.functions[i+1]] if i+1<len(a.functions) else end)-a.labels[k]) for i,k in enumerate(a.functions)},
 'audited_code_budget':LIMIT-BASE,'fits':end<=LIMIT,'end_if_placed':hex(end),'code_sha256':hashlib.sha256(code).hexdigest(),
 'delay_slots_filled':compacted_words,'PIC_state_bytes':64,'reservation':[hex(STATE),hex(STATE+64)],
 'missing':['bulk replay entry/exit and raw replacement hook installation','synchronous save/load/import whole-operation deferral and error routing'],
 'limits':'Unplaced bytes only. No payload written. Fit does not include missing adapters.'}
 (OUT/'pic_emission_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':build()

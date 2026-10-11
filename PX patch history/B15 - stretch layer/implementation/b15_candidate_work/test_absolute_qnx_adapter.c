#include "b15_absolute_core.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
typedef unsigned long uptr;
_Alignas(16) unsigned char b15_test_runtime[768];
static _Alignas(16) unsigned char loop[0x2100],group[4][0x690],handlers[4][16][0x248];
static unsigned params[2][0x1b7],mutex_depth,reloads,mirrors,statuses,last_setting,last_actual;
#define AT(p,o,t) (*(t *)((unsigned char *)(p)+(o)))
int b15_qnx_before(void*,unsigned,unsigned);
void b15_qnx_after(void*,unsigned,unsigned);
void b15_qnx_group_clear(void*,unsigned);
void b15_qnx_note_attempt(void*,unsigned,unsigned,unsigned);
void b15_qnx_note_accepted(void*,unsigned,unsigned,unsigned,void*);
static int mutex_lock(void *p) { (void)p;assert(!mutex_depth);return ++mutex_depth; }
static int mutex_unlock(void *p) { (void)p;assert(mutex_depth==1);return --mutex_depth; }
static void param_set(void *p,int ab,int id,int n) { (void)p;assert(mutex_depth==1);params[ab][id]=n; }
#ifdef B15_PAIR_TEST
void (*b15_pair_feedback)(unsigned,unsigned);
#endif
static unsigned frame_epoch,frame_phase,last_epoch,last_pair;
static void send(void *p,unsigned cmd,unsigned data) {
    assert(p==loop && !mutex_depth);
    if(cmd==0x4058) { frame_epoch=data;frame_phase=1; }
    else if(cmd==0x4059) { assert(frame_phase==1);frame_epoch|=data<<16;frame_phase=2; }
    else if(cmd==0x404a) { assert(frame_phase==2);frame_phase=0;statuses++;last_actual=data&31;last_pair=data>>7;last_epoch=frame_epoch; }
    else { mirrors++;assert(0); }
#ifdef B15_PAIR_TEST
    if(b15_pair_feedback)b15_pair_feedback(cmd,data);
#endif
}
static void *find(void *g,int key,int velocity,int target,int unused,int stretch,int ab,int inst) {
    void *h=AT(g,0x680,void*),*answer=0;int d,best_distance=1000,best_layer=1000,lo,hi;
    (void)velocity;(void)unused;assert(stretch==1 && mutex_depth==1);
    for(;h;h=AT(h,0x240,void*)) {
        lo=AT(h,0x200,int);hi=AT(h,0x204,int);
        d=lo>key?lo-key:(key>hi?key-hi:0);if(d<best_distance)best_distance=d;
    }
    for(h=AT(g,0x680,void*);h;h=AT(h,0x240,void*)) {
        int layer=AT(h,0x218,int),ld=abs(layer-target);
        lo=AT(h,0x200,int);hi=AT(h,0x204,int);d=lo>key?lo-key:(key>hi?key-hi:0);
        if(d==best_distance && AT(h,0x238+2*ab+inst,unsigned char) && ld<best_layer) {
            best_layer=ld;answer=h;
        }
    }
    return answer;
}
static const char *path(void *p) { assert(p && mutex_depth);return "test-group"; }
static void enqueue(const char *p,void *h,int ab,int inst) { assert(p && h && !mutex_depth && ab<2 && inst<2);reloads++; }
void *b15_test_address(uptr addr) {
    switch(addr) {
    case 0x7a10:return (void*)mutex_lock;
    case 0x79a0:return (void*)mutex_unlock;
    case 0x9700:return (void*)param_set;
    case 0x1d7f0:return (void*)send;
    case 0x35940:return (void*)find;
    case 0x36180:return (void*)path;
    case 0x3ed50:return (void*)enqueue;
    default:assert(0);return 0;
    }
}
static unsigned packet(unsigned p,unsigned epoch,unsigned n) { return epoch<<9|p<<7|n; }
static struct b15_state *core(void) { return (struct b15_state*)b15_test_runtime; }

static void token(unsigned p,unsigned e) {
 assert(b15_qnx_before(loop,0x404b+p,e&65535));
 assert(b15_qnx_before(loop,0x4053+p,e>>16));
}
int main(void) {
 unsigned p,k,before; unsigned counts[4]={3,4,6,8};
 for(p=0;p<4;p++) {
  AT(loop,0x2000+8*p,void*)=group[p];AT(group[p],0x680,void*)=handlers[p][0];
  for(k=0;k<16;k++) {
   void *h=handlers[p][k];AT(h,0x200,int)=0;AT(h,0x204,int)=127;
   AT(h,0x218,int)=k;AT(h,0x238+p,unsigned char)=k<counts[p];AT(h,0x240,void*)=k==15?0:handlers[p][k+1];
  }
 }
 token(0,0x12340001);assert(!b15_qnx_before(loop,0x12,1));b15_qnx_after(loop,0x12,1);
 assert(last_actual==3 && last_epoch==0x12340001 && !mirrors);
 for(k=0;k<20000;k++) { unsigned n=(k%3)+1;assert(b15_qnx_before(loop,0x1c,n));assert(params[0][0x1c]==n && last_actual==n); }
 before=reloads;b15_qnx_before(loop,0x1c,0);assert(params[0][0x1c]==0 && reloads==before && last_actual==2);
 b15_qnx_note_attempt(loop,0,0,64);b15_qnx_note_accepted(loop,0,0,64,handlers[0][1]);
 b15_qnx_before(loop,0x4048,packet(0,7,64));b15_qnx_note_attempt(loop,0,0,64);
 token(0,0x12340002);before=reloads;b15_qnx_before(loop,0x14,69);assert(reloads==before);
 b15_qnx_before(loop,0x4049,packet(0,7,69));assert(last_actual==2 && last_epoch==0x12340002 && core()->pair[0].key==69);
 assert(params[0][0x1c]==0); /* Capture feedback never stores captured setting. */
 b15_qnx_before(loop,0x14,70);assert(core()->pair[0].target==2 && last_actual==2);
 for(k=0;k<16;k++) AT(handlers[0][k],0x238,unsigned char)=k==0;
 b15_qnx_before(loop,0x14,71);assert(last_actual==1 && core()->pair[0].target==2);
 AT(handlers[0][1],0x238,unsigned char)=1;b15_qnx_before(loop,0x14,72);assert(last_actual==2);
 /* A+B are independent absolute requests; QNX never copies a pair's target. */
 token(2,200);assert(!b15_qnx_before(loop,0x812,1));b15_qnx_after(loop,0x812,1);
 assert(last_actual==6 && last_pair==2);b15_qnx_before(loop,0x81c,5);assert(last_actual==5 && core()->pair[0].target==2);
 /* Loaded values are stores only inside BEGIN/END, highest at loaded key. */
 token(3,0xfeedabcd);b15_qnx_before(loop,0x404f,8);before=reloads;
 b15_qnx_before(loop,0x855,73);b15_qnx_before(loop,0x85d,1);
 assert(!b15_qnx_before(loop,0x853,1));b15_qnx_after(loop,0x853,1);assert(reloads==before);
 b15_qnx_before(loop,0x4050,8);assert(last_actual==8 && last_epoch==0xfeedabcd && params[1][0x5d]==1);
 /* Disable/re-enable has no history; highest at existing key, even after edits. */
 assert(!b15_qnx_before(loop,0x853,0));b15_qnx_after(loop,0x853,0);assert(last_actual==0);
 b15_qnx_before(loop,0x853,1);b15_qnx_after(loop,0x853,1);assert(last_actual==8 && params[1][0x55]==73);
 before=reloads;b15_qnx_before(loop,0x4057,15);assert(reloads==before && !mirrors);
 /* Group replacement drops invalid handler and preserves numeric target. */
 b15_qnx_group_clear(loop,2);AT(loop,0x1fb8+8*2,void*)=0;
 for(k=0;k<16;k++) AT(handlers[2][k],0x238+2,unsigned char)=0;
 b15_qnx_after(loop,0x824,1);assert(last_actual==0 && core()->pair[2].target==5);
 before=params[1][0x55];b15_qnx_before(loop,0x4049,packet(3,7,11));assert(params[1][0x55]==before);
 assert(!mutex_depth && !mirrors && !frame_phase && !last_setting);
 puts("PASS: absolute adapter20000 edits; display-only full32 frames; highest/held/On/key target/A+B/bulk/reenable/group failure and refresh without parameter mirrors");
 return 0;
}

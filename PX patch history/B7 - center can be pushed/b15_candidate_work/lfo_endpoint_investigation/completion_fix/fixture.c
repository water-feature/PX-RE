// SPDX-License-Identifier: GPL-2.0-or-later
/* Focused independent endpoint-bank fixtures around emitted code bytes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "../../../b5_candidate_work/b5_core.generated.h"
#include "../b5_offsets.generated.h"
#define U32(p,o) (*(u32 *)((unsigned char *)(p)+(o)))
#define U64(p,o) (*(u64 *)((unsigned char *)(p)+(o)))
#define PTR(p,o) (*(void **)((unsigned char *)(p)+(o)))
#define INT(p,o) (*(int *)((unsigned char *)(p)+(o)))
typedef struct { unsigned char xmm[256];u64 r15,r14,r13,r12,rbp,rbx,r11,r10,r9,r8,rdi,rsi,rdx,rcx,rax,flags; } Capture;
typedef struct {u32 held_start,held_end,latest_start,latest_end;u64 rate_slot;Key published_key;int published_boundary;u64 staged_reader;int staged_start,published_start;u32 sequence,published_sequence,requested_rate,packed;} Bridge;
enum {FORWARD,REVERSE,GEOM,PREPARE,NOTE,RESET,RETURN,EOF_ZONE,READ,LOAD,FILTER,PUBLISH};
#define PUBLISHED (1u<<24)
#define ACTIVE (1u<<22)
#define OK (1u<<23)
#define OPAQUE (1u<<28)
extern unsigned char b5_image[];
#define FN(name,type) ((type)(b5_image+OFF_##name))
static void dispatch(Capture *c,unsigned event,unsigned char *frame){FN(b5_dispatch,void(*)(Capture*,unsigned,unsigned char*))(c,event,frame);}
static unsigned checks=0,groups=0;
#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static unsigned char scheduler[0x200],pool[0x4c00],reader[128][0x1c8],banks[128][0x500],raw[128][0x1100];
static unsigned char osc[0x100],left[0x2200],right[0x2200],params[64*0x34];
static float audioL[1088],audioR[1088],workL[32],workR[32];
static void *audio[2]={audioL,audioR},*work[2]={workL,workR};
static unsigned char frame[256];static State *s;static Bridge *b;
static u32 bits(float f){FloatBits v;v.f=f;return v.u;}
static Key key(int a,int z,float r,int rev,int loop){Key k={a,z,bits(r),rev,loop};return k;}
static unsigned char *producer(void *r){return PTR(r,0x1a8)+(U32(r,0x1b0)&1)*0x280;}
static unsigned char *consumed(void *r){return PTR(r,0x1a8)+((U32(r,0x1b0)+1)&1)*0x280;}
static void endpoints(void *r,float a,float z){U32(producer(r),0)=bits(a);U32(producer(r),0x180)=bits(z);}
static int test_slot=0,test_channels=2,test_reverse=0;
static void init(void){
 memset(scheduler,0,sizeof scheduler);memset(pool,0,sizeof pool);memset(reader,0,sizeof reader);memset(banks,0,sizeof banks);memset(osc,0,sizeof osc);memset(frame,0,sizeof frame);memset(left,0,sizeof left);memset(right,0,sizeof right);memset(params,255,sizeof params);
 PTR(scheduler,0)=b5_image+OFF_b5_ram_vtable;PTR(scheduler,8)=pool;PTR(scheduler,0x10)=params;
 for(int j=0;j<128;++j){PTR(pool+j/2*0x30,j%2?16:8)=reader[j];PTR(reader[j],0x1a8)=banks[j];PTR(reader[j],0xb8)=raw[j];INT(reader[j],0xa0)=10001;*(unsigned short *)(reader[j]+0xa8)=2;INT(reader[j],0x24)=-1;endpoints(reader[j],.1f,.9f);U32(reader[j],0x198)=U32(reader[j],0x19c)=bits(1);}
 Capture c={0};c.rdi=(uintptr_t)scheduler;dispatch(&c,RESET,frame);
 PTR(pool+test_slot*0x30,0)=audio;pool[test_slot*0x30+0x2c]=1;U32(osc,8)=test_slot;PTR(osc,0x30)=scheduler;PTR(osc,0x10)=left;PTR(osc,0x18)=right;
 s=(State *)(pool+0xc00+test_slot*0x100);b=(Bridge *)(s->bytes+sizeof(Fields));s->d.effective=key(1000,9000,1,0,0);s->d.timeline_key=s->d.effective;
 U32(left,0)=U32(right,0)=bits(1);*(float *)(left+4)=*(float *)(right+4)=32;
}
static Capture context(void){Capture c={0};c.r15=(uintptr_t)osc;c.r13=(uintptr_t)scheduler;c.rbx=(uintptr_t)(pool+test_slot*0x30);c.rdi=(uintptr_t)reader[test_slot*2];c.rsi=96;return c;}
static void prepare(float r){Capture c=context();U32(&c,0)=bits(r);U32(frame,0x14)=bits(r);dispatch(&c,PREPARE,frame);}
/* Independent stock-fixture bank transaction: UpdateLoc first uses consumed;
 * Read flips the bank and takes working geometry from the new consumed bank.
 * Observed frame arguments stand for stock Read's actual clamped geometry.
 */
static void read_batch(void *r,int a,int z,int rev,int count,int prefix,int eof){
 Capture c=context();c.rdi=(uintptr_t)r;c.rsi=count;((unsigned char *)r)[8]=prefix?1:0;dispatch(&c,READ,frame);
 U32(r,0x1b0)++;INT(r,0x58)=INT(r,0x28);U32(r,0x198+4*((U32(r,0x1b0)+1)&1))=U32(frame,0x14)?U32(frame,0x14):bits(1);
 unsigned char rf[176]={0};PTR(rf,168)=b5_image+OFF_b5_read_original_return;INT(rf,0x24)=a;INT(rf,0x10)=z;rf[0x1c]=rev;
 dispatch(&c,GEOM,rf);c.rbx=(uintptr_t)r;c.r13=4;c.r12=count-prefix;c.r15=(uintptr_t)PTR(r,0xb8)+4*prefix;
 INT(r,0x90)=rev?z-prefix-(count-prefix):a+prefix;
 if(eof){c.r15=(uintptr_t)PTR(r,0xb8)+4*prefix;dispatch(&c,EOF_ZONE,rf);}else dispatch(&c,rev?REVERSE:FORWARD,rf);
 c=context();c.rax=0;dispatch(&c,READ|128,frame);
}
static void publish(void *r,void *output,int count){Capture c=context();c.rdi=(uintptr_t)r;c.rsi=count;c.rdx=(uintptr_t)output;dispatch(&c,PUBLISH,frame);dispatch(&c,PUBLISH|128,frame);}
static void actual_load(int offset,int n,int avail){
 unsigned char callframe[256]={0};INT(callframe+8,0x2c)=avail;
 Capture c=context();c.rdi=(uintptr_t)left;c.rsi=(uintptr_t)(audioL+offset);c.rbp=offset;
 dispatch(&c,LOAD,callframe);*(double *)(left+16)+=n;c.rax=n;dispatch(&c,LOAD|128,callframe);
}
static void hold_tests(void){
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=32;
 b->held_start=bits(.1f);b->held_end=bits(.9f);endpoints(reader[0],.2f,.95f);prepare(2);
 CHECK(s->d.effective.b==9000 && s->d.has_pending);CHECK(U32(frame,0x14)==bits(1));
 read_batch(reader[0],1000,9000,0,96,0,0);
 CHECK(U32(consumed(reader[0]),0)==bits(.1f));CHECK(U32(consumed(reader[0]),0x180)==bits(.9f));
 CHECK(U32(producer(reader[0]),0)==bits(.2f));CHECK(U32(producer(reader[0]),0x180)==bits(.95f));
 /* Independent UpdateLoc snapshot: must retain held range before second Read. */
 int update_start=(int)(*(float *)consumed(reader[0])*10000.f);CHECK(update_start==1000);
 endpoints(reader[0],.3f,.99f);s->d.clock=224;prepare(.5f);read_batch(reader[0],1000,9000,0,96,0,0);
 CHECK(U32(consumed(reader[0]),0)==bits(.1f));CHECK(U32(producer(reader[0]),0)==bits(.3f));
 s->d.clock=240;prepare(.5f);CHECK(s->d.effective.a==3000&&s->d.effective.b==9900);CHECK(U32(frame,0x14)==bits(.5f));
 CHECK(U32(consumed(reader[0]),0)==bits(.1f));/* completion does not rewrite prior consumed geometry */
 read_batch(reader[0],3000,9900,0,96,0,0);CHECK(U32(consumed(reader[0]),0)==bits(.3f));++groups;
}
static void swap_tests(void){
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=64;b->held_start=bits(.1f);b->held_end=bits(.9f);
 endpoints(reader[0],.4f,.98f);INT(scheduler,0x24)=1;prepare(2);
 /* Actual CloneEndpointData ordering, not the adapter: rate pairs, both banks,
  * selector; then swap and Close old. Different pending data would expose use
  * of the un-cloned pending producer. */
 memset(banks[1],0x5a,sizeof banks[1]);memcpy(banks[1],banks[0],0x500);memcpy(reader[1]+0x198,reader[0]+0x198,8);U32(reader[1],0x1b0)=U32(reader[0],0x1b0);
 PTR(pool,8)=reader[1];PTR(pool,16)=reader[0];INT(scheduler,0x24)=0;
 read_batch(reader[1],1000,9000,0,96,0,0);
 CHECK(PTR(reader[1],0x1b8)==s);CHECK(U32(consumed(reader[1]),0)==bits(.1f));CHECK(U32(producer(reader[1]),0)==bits(.4f));
 CHECK(b->staged_reader==(uintptr_t)reader[1]);CHECK(s->d.effective.a==1000);
 /* Fractions cannot retain old integer geometry against a new file length. */
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=64;INT(scheduler,0x24)=1;INT(reader[1],0xa0)=20001;
 prepare(2);CHECK(!s->d.has_fade&&s->d.effective.a==2000);CHECK(U32(frame,0x14)==bits(2));
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=64;INT(scheduler,0x24)=1;*(unsigned short *)(reader[1]+0xa8)=1;
 prepare(2);CHECK(!s->d.has_fade);CHECK(U32(frame,0x14)==bits(2));++groups;
}
static void identity_tests(void){
 init();prepare(1);read_batch(reader[0],1000,9000,0,96,0,0);publish(reader[0],audio,96);
 CHECK(b->packed&PUBLISHED);u32 seq=b->published_sequence;CHECK(b->published_boundary==8000 && b->published_start==-1);
 /* A new opaque raw batch, not normalized, must not relabel old float audio. */
 read_batch(reader[0],2000,7000,0,96,20,0);CHECK(b->published_sequence==seq);CHECK(b->packed&OPAQUE);
 actual_load(0,33,96);CHECK(s->d.endpoint_valid&&s->d.endpoint==8000);CHECK(s->d.timeline_key.a==1000);
 void *foreign[2]={workL,workR};publish(reader[0],foreign,96);CHECK(b->packed&PUBLISHED);CHECK(b->published_sequence==seq);
 publish(reader[0],audio,95);CHECK(!(b->packed&PUBLISHED));/* own destination wrong count invalidates */
 publish(reader[0],audio,96);CHECK(b->packed&PUBLISHED);CHECK(b->published_key.a==2000&&b->published_start==20);CHECK(b->published_sequence!=seq);
 *(double *)(left+16)=0;actual_load(0,33,10);CHECK(!s->d.endpoint_valid);/* entirely opaque prefix */
 *(double *)(left+16)=0;actual_load(20,33,76);CHECK(s->d.endpoint_valid&&s->d.timeline_key.a==2000);
 publish(reader[1],audio,96);CHECK(!(b->packed&PUBLISHED));/* wrong reader into owned output */
 publish(reader[0],audio,96);CHECK(b->packed&PUBLISHED);
 unsigned char cf[256]={0};INT(cf+8,0x2c)=76;Capture c=context();c.rdi=(uintptr_t)left;c.rsi=(uintptr_t)(audioL+21);c.rbp=20;
 dispatch(&c,LOAD,cf);*(double *)(left+16)=33;c.rax=33;dispatch(&c,LOAD|128,cf);CHECK(!s->d.endpoint_valid);/* pointer and offset disagree */
 ++groups;
}
static void geometry_tests(void){
 for(int rev=0;rev<2;rev++)for(int prefix=0;prefix<2;prefix++){
 init();INT(reader[0],0x30)=rev;prepare(1);read_batch(reader[0],1000,9000,rev,96,prefix?20:0,0);publish(reader[0],audio,96);
 CHECK(b->published_key.reverse==(u32)rev);CHECK(b->published_boundary==8000);/* prefix distance cancel for cursor advanced by prefix */
 CHECK(b->published_start==(prefix?20:-1));
 }
 init();prepare(1);read_batch(reader[0],1000,9000,0,96,0,1);CHECK(s->d.read_valid&&s->d.read_boundary==0);
 init();prepare(1);read_batch(reader[0],1000,9000,0,96,20,1);CHECK(!s->d.read_valid);/* no ordinary span mapping yet */
 init();Capture c={0};unsigned char rf[176]={0};c.rdi=1;c.rbx=1;dispatch(&c,GEOM,rf);dispatch(&c,EOF_ZONE,rf);CHECK(1);/* unauthorized global hooks never dereference reader */
 ++groups;
}
static void mode_tests(void){
 for(int mode=0;mode<3;mode++){
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=32;b->held_start=bits(.1f);b->held_end=bits(.9f);endpoints(reader[0],.2f,.95f);
 if(mode==0)INT(reader[0],0x28)=1;if(mode==1)INT(reader[0],0x30)=1;if(mode==2)INT(reader[0],0x24)=2000;
 prepare(2);CHECK(!s->d.has_fade);CHECK(U32(frame,0x14)==bits(2));
 }
 /* Pending WriteParams can change mode between Prepare and Read. No deferral. */
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=32;b->held_start=bits(.1f);b->held_end=bits(.9f);prepare(2);
 INT(reader[0],0x30)=1;Capture c=context();dispatch(&c,READ,frame);CHECK(!s->d.has_fade);CHECK(U32(frame,0x14)==bits(2));CHECK(c.rsi==128&&c.rbp==128);
 /* Dirty prospective parameters and pending target length are honored before clone. */
 init();INT(scheduler,0x24)=1;INT(reader[1],0xa0)=20001;scheduler[0x124]=1;INT(params,0x10)=1;prepare(1);CHECK(s->d.effective.reverse==1 && s->d.effective.a==2000 && s->d.effective.b==18000);
 /* follows-center in noncustom remains forward; custom comparison drives reverse. */
 init();INT(reader[0],0x50)=1;INT(reader[0],0x30)=1;prepare(1);CHECK(!s->d.effective.reverse);
 INT(reader[0],0x40)=1;U32(producer(reader[0]),0x80)=bits(.8f);U32(producer(reader[0]),0x84)=bits(.2f);prepare(1);CHECK(s->d.effective.reverse);
 ++groups;
}
static void ramp_boundary_tests(void){
 const u64 clocks[]={0,1,239,240,241};
 for(int j=0;j<5;j++){
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=clocks[j];b->held_start=bits(.1f);b->held_end=bits(.9f);
 endpoints(reader[0],.2f,.95f);prepare(2);int audible=clocks[j]>0&&clocks[j]<240;
 CHECK((U32(frame,0x14)==bits(1))==audible);CHECK((s->d.effective.a==1000)==audible);
 }
 /* Same completion stays zero; endpoint extension is accepted and can render. */
 init();s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=240;prepare(1);
 for(int j=0;j<32;j++)workL[j]=workR[j]=1;
 unsigned char cf[256]={0};INT(cf+8,0x28)=1;Capture c=context();c.rbx=(uintptr_t)work;dispatch(&c,FILTER|128,cf);
 CHECK(workL[0]==0&&workL[31]==0);endpoints(reader[0],.1f,1.f);prepare(1);CHECK(!s->d.has_fade&&s->d.effective.b==10000);
 for(int j=0;j<32;j++)workL[j]=workR[j]=1;dispatch(&c,FILTER|128,cf);CHECK(workL[0]==1&&workL[31]==1);
 ++groups;
}
static void stereo_tests(void){
 init();s->d.clock=32;s->d.has_fade=1;s->d.start=0;s->d.end=240;
 for(int j=0;j<32;j++){workL[j]=1;workR[j]=2;}
 unsigned char cf[256]={0};INT(cf+8,0x28)=2;Capture c=context();c.rbx=(uintptr_t)work;dispatch(&c,FILTER|128,cf);
 CHECK(s->d.clock==64);for(int j=0;j<32;j++)CHECK(workR[j]==2*workL[j]);
 *(double *)(right+8)=.5;s->d.endpoint_valid=1;dispatch(&c,FILTER|128,cf);CHECK(!s->d.endpoint_valid&&!s->d.has_fade);
 init();s->d.clock=64;s->d.has_fade=1;s->d.start=0;s->d.end=240;prepare(2);c=context();c.rax=0;dispatch(&c,RETURN,frame);CHECK(s->d.clock==64&&!s->d.has_fade&&!b->rate_slot);++groups;
}
/* Wrapper original-function substitutes used only in the host binding area. */
extern unsigned long fixture_outputs(unsigned long);
static int owned_wrappers;
unsigned long fixture_read(void *r,unsigned long n,float rate){
 if(!owned_wrappers)return fixture_outputs(0x12345678);
 CHECK(r==PTR(pool,8)&&n==96&&bits(rate)==bits(1));
 U32(r,0x1b0)++;INT(r,0x58)=0;U32(r,0x198+4*((U32(r,0x1b0)+1)&1))=bits(rate);
 unsigned char rf[176]={0};PTR(rf,168)=b5_image+OFF_b5_read_original_return;INT(rf,0x24)=1000;INT(rf,0x10)=9000;
 Capture c=context();c.rdi=(uintptr_t)r;dispatch(&c,GEOM,rf);
 c.rbx=(uintptr_t)r;c.r13=4;c.r12=96;c.r15=(uintptr_t)PTR(r,0xb8);INT(r,0x90)=1000;
 dispatch(&c,FORWARD,rf);return 0;
}
unsigned long fixture_load(void *r,void *p,unsigned n){
 if(!owned_wrappers)return fixture_outputs(17);
 CHECK(r==left&&p==audioL&&n==96);*(double *)(left+16)=33;return 33;
}
unsigned long fixture_filter(void *a,void *b,unsigned n){(void)a;(void)b;(void)n;return fixture_outputs(19);}
unsigned long fixture_publish(void *a,unsigned n,void *p){(void)a;(void)n;(void)p;return fixture_outputs(23);}
extern void fixture_call(void *fn,Capture *input,Capture *output);
static void owned_wrapper_tests(void){
 init();prepare(1);owned_wrappers=1;Capture in=context(),out={0};U32(&in,0)=bits(1);
 fixture_call(b5_image+OFF_b5_wrap_read,&in,&out);CHECK(out.rax==0);CHECK(s->d.read_valid && !(b->packed&ACTIVE));
 in=context();in.rdx=(uintptr_t)audio;fixture_call(b5_image+OFF_b5_wrap_publish,&in,&out);
 CHECK(b->packed&PUBLISHED);CHECK(b->published_boundary==8000);
 in=context();in.rdi=(uintptr_t)left;in.rsi=(uintptr_t)audioL;in.rdx=96;in.rbp=0;
 fixture_call(b5_image+OFF_b5_wrap_load,&in,&out);CHECK(out.rax==33);CHECK(s->d.endpoint_valid&&s->d.endpoint==8000);
 owned_wrappers=0;++groups;
}
static void wrapper_tests(void){
 init();
 /* Non-owned contexts exercise transparent full preservation through real emitted
  * wrappers without inventing stock Read internals. Callee registers and all
  * XMM bytes checked against independent entry patterns, return against original. */
 unsigned offsets[]={OFF_b5_wrap_read,OFF_b5_wrap_load,OFF_b5_wrap_filter,OFF_b5_wrap_publish};
 unsigned returns[]={0x12345678,17,19,23};
 for(int n=0;n<4;n++){
 Capture in={0},out={0};for(int j=0;j<256;j++)in.xmm[j]=(unsigned char)(j*7+3);
 in.r15=(uintptr_t)osc;in.r13=(uintptr_t)scheduler;in.rbx=(uintptr_t)pool;in.rbp=0x1234567;in.r12=0x22334455;in.r14=0x88776655;in.rdi=(uintptr_t)reader[0];in.rsi=96;in.rdx=(uintptr_t)audio;in.flags=0x202;
 PTR(scheduler,0)=NULL;fixture_call(b5_image+offsets[n],&in,&out);
 CHECK(out.rax==returns[n]);CHECK(out.rbx==in.rbx&&out.rbp==in.rbp&&out.r12==in.r12&&out.r13==in.r13&&out.r14==in.r14&&out.r15==in.r15);
 CHECK(out.rcx==101&&out.rdx==202&&out.rsi==303&&out.rdi==404);
 CHECK(out.r8==505&&out.r9==606&&out.r10==707&&out.r11==808);
 for(int j=0;j<256;j++)CHECK(out.xmm[j]==(j<240?255:0));
 CHECK((out.flags&0x8d5)==0x44);
 }
 ++groups;
}
int main(void){hold_tests();swap_tests();identity_tests();geometry_tests();mode_tests();ramp_boundary_tests();stereo_tests();wrapper_tests();owned_wrapper_tests();printf("PASS %u focused checks in %u groups (emitted object bytes, host fixtures)\n",checks,groups);return 0;}

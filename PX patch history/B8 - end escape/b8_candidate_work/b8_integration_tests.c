/* Focused independent endpoint-bank fixtures around emitted code bytes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "../b5_candidate_work/b5_core.generated.h"
#include "b8_offsets.generated.h"
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
static unsigned char scheduler[0x200],pool[0x4c00],reader[128][0x1c8],banks[128][0x500],raw[128][0x2200];
static unsigned char osc[0x100],left[0x2200],right[0x2200],params[64*0x34],dirty[8];
static float audioL[1088],audioR[1088],workL[32],workR[32];
static void *audio[2]={audioL,audioR},*work[2]={workL,workR};
static unsigned char frame[256];static State *s;static Bridge *b;
static u32 bits(float f){FloatBits v;v.f=f;return v.u;}
static Key key(int a,int z,float r,int rev,int loop){Key k={a,z,bits(r),rev,loop};return k;}
static unsigned char *producer(void *r){return PTR(r,0x1a8)+(U32(r,0x1b0)&1)*0x280;}
static unsigned char *consumed(void *r){return PTR(r,0x1a8)+((U32(r,0x1b0)+1)&1)*0x280;}
static void endpoints(void *r,float a,float z){U32(producer(r),0)=bits(a);U32(producer(r),0x180)=bits(z);}
static void init(void){
 memset(scheduler,0,sizeof scheduler);memset(pool,0,sizeof pool);memset(reader,0,sizeof reader);memset(raw,0x5a,sizeof raw);memset(banks,0,sizeof banks);memset(osc,0,sizeof osc);memset(frame,0,sizeof frame);memset(left,0,sizeof left);memset(right,0,sizeof right);memset(params,255,sizeof params);
 PTR(scheduler,0)=b5_image+OFF_b5_ram_vtable;PTR(scheduler,8)=pool;PTR(scheduler,0x10)=params;PTR(scheduler,0x18)=dirty;memset(dirty,0,8);
 for(int j=0;j<128;++j){PTR(pool+j/2*0x30,j%2?16:8)=reader[j];PTR(reader[j],0x1a8)=banks[j];PTR(reader[j],0xb8)=raw[j];INT(reader[j],0xa0)=10001;*(unsigned short *)(reader[j]+0xa8)=2;INT(reader[j],0x24)=-1;endpoints(reader[j],.1f,.9f);U32(consumed(reader[j]),0)=bits(.1f);U32(consumed(reader[j]),0x180)=bits(.9f);U32(reader[j],0x198)=U32(reader[j],0x19c)=bits(1);}
 Capture c={0};c.rdi=(uintptr_t)scheduler;dispatch(&c,RESET,frame);
 PTR(pool,0)=audio;pool[0x2c]=1;PTR(osc,0x30)=scheduler;PTR(osc,0x10)=left;PTR(osc,0x18)=right;
 s=(State *)(pool+0xc00);b=(Bridge *)(s->bytes+sizeof(Fields));s->d.effective=key(1000,9000,1,0,0);s->d.timeline_key=s->d.effective;
 U32(left,0)=U32(right,0)=bits(1);*(float *)(left+4)=*(float *)(right+4)=32;
}
static Capture context(void){Capture c={0};c.r15=(uintptr_t)osc;c.r13=(uintptr_t)scheduler;c.rbx=(uintptr_t)pool;c.rdi=(uintptr_t)reader[0];c.rsi=96;return c;}
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
#include <time.h>
#define DONE(r) (*((unsigned char *)(r)+0x1c0))
extern void fixture_call(void *,Capture *,Capture *);
extern unsigned long fixture_outputs(unsigned long);
extern void fixture_jump_prepare(void),fixture_jump_gate(void),fixture_jump_reset(void),fixture_jump_note(void),fixture_jump_return(void);
extern void *fixture_jump_target;
extern unsigned fixture_branch_path;
extern void *fixture_prepare_route_target;
extern void fixture_stock_prepare(void),fixture_continue_prepare(void);
static unsigned current_slot,channels=2,delay_frames,trace[8],trace_n;
unsigned long fixture_open_slot_offset;
static void mark(unsigned x){if(trace_n<8)trace[trace_n++]=x;}
static u64 b8(Capture *c,unsigned event,unsigned char *f){
 unsigned char storage[400]={0};memcpy(storage,c,384);
 FN(b8_dispatch,void(*)(Capture*,unsigned,unsigned char*))( (Capture*)storage,event,f);
 memcpy(c,storage,384);return *(u64 *)(storage+384);
}
static void select_slot(unsigned i){
 current_slot=i;fixture_open_slot_offset=i*0x30;U32(osc,8)=i;s=(State *)(pool+0xc00+i*256);b=(Bridge *)(s->bytes+sizeof(Fields));PTR(pool+i*0x30,0)=audio;
}
static void *slot(void){return pool+current_slot*0x30;}
static Capture ctx(void){Capture c=context();c.rbx=(uintptr_t)slot();c.rdi=(uintptr_t)PTR(slot(),8);return c;}
static void fresh(void){init();select_slot(0);channels=2;delay_frames=0;trace_n=0;}
static void pre(float rate){
 Capture c=ctx();U32(&c,16)=bits(rate);b8(&c,0,frame);mark(1);
 U32(&c,0)=U32(&c,16);U32(frame,0x14)=U32(&c,16);dispatch(&c,PREPARE,frame);mark(2);
}
unsigned long fixture_read(void *r,unsigned count,float rate,void *aio,unsigned char *valid){
 (void)aio;CHECK(r==PTR(slot(),8));CHECK(count<=1088);mark(4);
 U32(r,0x1b0)=(U32(r,0x1b0)+1)&1;void *cb=consumed(r);
 memcpy((unsigned char *)r+0x54,(unsigned char *)r+0x24,0x30);INT(r,0x24)=-1;
 U32(r,0x198+4*((U32(r,0x1b0)+1)&1))=bits(rate);
 int last=INT(r,0xa0)-1,a=(int)(*(float *)cb*last),z=(int)(*(float *)((unsigned char *)cb+0x180)*last);
 if(a>=last+1-32)a=last+1-33;if(a<0)a=0;if(z<a+32)z=a+32;if(z>last)z=last;
 int rev=INT(r,0x60)!=0;
 if(INT(r,0x80))rev=INT(r,0x70)?!(*(float *)((unsigned char *)cb+0x84)*last>=*(float *)((unsigned char *)cb+0x80)*last):0;
 int p=INT(r,0xcc);if(p==-1)p=rev?z:a;INT(r,0x90)=INT(r,0x94)=p;
 unsigned char rf[176]={0};PTR(rf,168)=b5_image+OFF_b5_read_original_return;PTR(rf,0)=valid;INT(rf,0x24)=a;INT(rf,0x10)=z;rf[0x1c]=rev;
 Capture c=ctx();c.rdi=(uintptr_t)r;dispatch(&c,GEOM,rf);
 c.rbx=(uintptr_t)r;c.r13=channels*2;c.rbp=count;c.r15=(uintptr_t)PTR(r,0xb8);
 if(b8(&c,1,rf)==(uintptr_t)(b5_image+OFF_b8_zero)){
  memset(PTR(r,0xb8),0,count*channels*2);dispatch(&c,EOF_ZONE,rf);CHECK(*valid==1);return 0;
 }
 unsigned d=0;if(!*((unsigned char *)r+0x1a4)){
  float rem=*(float *)((unsigned char *)cb+0x200)-*(float *)((unsigned char *)r+0x1a0);
  if(rem>0)d=(unsigned)(rem*48000.f/1000.f*(rate>0?rate:1));if(d>count)d=count;
 }
 memset(PTR(r,0xb8),0,count*channels*2);
 unsigned distance=rev?(p>a?p-a:0):(z>p?z-p:0),copied=count-d;if(copied>distance)copied=distance;
 /* For loop-enabled fixture, model repeated valid input and no terminal anchor. */
 if(INT(r,0x58)){copied=count-d;distance=count+100;}
 short *pcm=PTR(r,0xb8);for(unsigned j=0;j<copied;j++)for(unsigned k=0;k<channels;k++)pcm[(d+j)*channels+k]=(short)(8000+k*4000+(rev?-1:1)*j);
 if(copied){c.r12=copied;c.r15=(uintptr_t)pcm+d*channels*2;INT(r,0x90)=rev?p-(int)copied:p;
  dispatch(&c,rev?REVERSE:FORWARD,rf);INT(r,0x90)=rev?p-(int)copied:p+(int)copied;
 }
 if(d+copied<count){c.r15=(uintptr_t)pcm+(d+copied)*channels*2;dispatch(&c,EOF_ZONE,rf);}
 if(valid)*valid=1;return 0;
}
unsigned long fixture_publish(void *r,unsigned n,void *buf){
 CHECK(buf==audio);short *pcm=PTR(r,0xb8);for(unsigned j=0;j<n;j++){
  audioL[j]=pcm[j*channels]/32768.f;audioR[j]=pcm[j*channels+(channels>1)]/32768.f;
 }return 0;
}
unsigned long fixture_load(void *r,void *p,unsigned n){(void)p;unsigned used=n>33?33:n;*(double *)((unsigned char *)r+16)+=used;return used;}
unsigned long fixture_filter(void *a,void *buf,unsigned n){(void)a;(void)buf;(void)n;return 0;}
unsigned long fixture_resampler_reset(void *r){memset((unsigned char *)r+8,0,16);return fixture_outputs(0);}
static int open_result;
unsigned long fixture_open(void *r,int x,int y,void *name,void *params_,int v,long arg1,long arg2){
 (void)x;(void)y;(void)name;(void)params_;(void)v;CHECK(arg1==0x1122&&arg2==0x3344);
 CHECK(r==PTR(slot(),16));if(!open_result){INT(r,0x90)=INT(r,0x94)=INT(r,0xcc)=-1;U32(r,0x1a0)=0;*((unsigned char *)r+0x1a4)=0;}
 return fixture_outputs(open_result);
}
static void client(unsigned count){
 void *r=PTR(slot(),8);unsigned index=current_slot;
 if(INT(scheduler,0x24+index*4)){
  void *pending=PTR(slot(),16);memcpy(PTR(pending,0x1a8),PTR(r,0x1a8),0x500);memcpy((unsigned char *)pending+0x198,(unsigned char *)r+0x198,8);U32(pending,0x1b0)=U32(r,0x1b0);
  PTR(slot(),8)=pending;PTR(slot(),16)=r;INT(scheduler,0x24+index*4)=0;r=pending;mark(3);
 }else{
  unsigned u=U32(slot(),0x24);if(u>U32(slot(),0x18))u=U32(slot(),0x18);void *cb=consumed(r);float rate=*(float *)((unsigned char *)r+0x198+4*((U32(r,0x1b0)+1)&1));
  if(rate<=0)rate=1;unsigned d=0;
  if(!*((unsigned char *)r+0x1a4)){
   float rem=*(float *)((unsigned char *)cb+0x200)-*(float *)((unsigned char *)r+0x1a0);if(rem>0)d=(unsigned)(rem*48.f*rate);
   if(d<=u){*((unsigned char *)r+0x1a4)=1;U32(r,0x1a0)=0;u-=d;}
   else{*(float *)((unsigned char *)r+0x1a0)+=u/rate/48.f;u=0;}
  }
  int p=INT(r,0x94);if(p!=-1)INT(r,0xcc)=p+(INT(r,0x60)?-(int)u:(int)u);mark(3);
 }
 if(scheduler[0x124+(index>>3)]&(1u<<(index&7))){
  void *p=params+index*0x34;for(unsigned j=0;j<0x34;j+=4){
   if(j==4||j==0x2c)continue;
   int off=j==0?0x24:j<=0x10?0x20+j:j==0x30?0x50:0x24+j;
   if(INT(p,j)>=0)INT(r,off)=INT(p,j);
  }
 }
 U32(slot(),0x2c)=1;Capture in=ctx(),out={0};in.rsi=count;in.rdx=0;in.rcx=(uintptr_t)((unsigned char *)slot()+0x2c);U32(&in,0)=U32(frame,0x14);
 fixture_call(b5_image+OFF_b5_wrap_read,&in,&out);CHECK(out.rax==0);
 in=ctx();in.rsi=count;in.rdx=(uintptr_t)audio;fixture_call(b5_image+OFF_b5_wrap_publish,&in,&out);U32(slot(),0x18)=count;mark(5);
}
unsigned long fixture_client_process(void *sched,unsigned index,float rate){
 CHECK(sched==scheduler&&index==current_slot);mark(2);U32(frame,0x14)=bits(rate);
 unsigned n=((unsigned)rate+2)*32;if(n>1088)n=1088;client(n);return 0;
}
static void record(int rev,int terminal,unsigned n,unsigned prefix,int loop){
 fresh();INT(reader[0],0x94)=INT(reader[0],0xcc)=rev?1000+terminal:9000-terminal;INT(reader[0],0x30)=rev;INT(reader[0],0x28)=loop;
 if(prefix){U32(producer(reader[0]),0x200)=U32(consumed(reader[0]),0x200)=bits(prefix/48.f);}
 pre(1);client(n);
 if(b->published_boundary!=terminal+(int)prefix && !loop)fprintf(stderr,"record rev=%d terminal=%d n=%u prefix=%u published=%d packed=%x start=%d key=%d/%d/%u read=%lld\n",rev,terminal,n,prefix,b->published_boundary,b->packed,b->published_start,b->published_key.a,b->published_key.b,b->published_key.reverse,s->d.read_boundary);
 CHECK(b->published_boundary==terminal+(int)prefix || loop);CHECK(!DONE(reader[0]));
}
static void consumption_tests(void){
 for(int rev=0;rev<2;rev++)for(int term=1;term<=32;term++)for(unsigned consumed_n=0;consumed_n<=40;consumed_n++){
  record(rev,term,96,0,0);U32(slot(),0x24)=consumed_n;endpoints(reader[0],.05f,1.f);pre(2);
  CHECK((DONE(reader[0])!=0)==(consumed_n>=(unsigned)term));
  if(consumed_n<(unsigned)term){CHECK(s->d.effective.b==10000);CHECK(U32(frame,0x14)==bits(2));}
  else {CHECK(s->d.effective.b==9000);CHECK(U32(frame,0x14)==bits(1));}
 }
 ++groups;
}
static void delay_tiny_tests(void){
 /* Exact whole-batch reads have no EOF suffix; the inherited span descriptor
  * must still permit completion at the last consumed frame. */
 for(int rev=0;rev<2;rev++){
  record(rev,96,96,0,0);U32(slot(),0x24)=95;pre(1);CHECK(!DONE(reader[0]));U32(slot(),0x24)=96;pre(1);CHECK(DONE(reader[0]));
  record(rev,66,96,30,0);U32(slot(),0x24)=95;pre(1);CHECK(!DONE(reader[0]));U32(slot(),0x24)=96;pre(1);CHECK(DONE(reader[0]));
  record(rev,100,32,0,0);U32(slot(),0x24)=200;pre(1);CHECK(!DONE(reader[0]));
 }
 for(int rev=0;rev<2;rev++)for(unsigned u=0;u<=65;u++){
  record(rev,20,96,30,0);U32(slot(),0x24)=u;endpoints(reader[0],.01f,1);pre(4);CHECK((DONE(reader[0])!=0)==(u>=50));
 }
 /* Delay consumes the entire batch: no ordinary anchor, no completion. */
 record(0,20,16,30,1); /* no published descriptor expected on loop */
 CHECK(!(b->packed&PUBLISHED));U32(slot(),0x24)=16;pre(1);CHECK(!DONE(reader[0]));
 for(int rev=0;rev<2;rev++){
  record(rev,0,96,0,0);U32(slot(),0x24)=0;pre(1);CHECK(!DONE(reader[0]));U32(slot(),0x24)=1;pre(1);CHECK(DONE(reader[0]));
  fresh();INT(reader[0],0xa0)=34;endpoints(reader[0],0,1);pre(4);client(96);CHECK(b->published_boundary==33);U32(slot(),0x24)=33;pre(4);CHECK(DONE(reader[0]));CHECK(!s->d.has_fade);
 }
 ++groups;
}
static void zero_controls_and_order(void){
 for(unsigned index=0;index<64;index+=31)for(unsigned ch=1;ch<=2;ch++){
  fresh();select_slot(index);channels=ch;void *r=PTR(slot(),8);INT(r,0x94)=INT(r,0xcc)=8980;pre(1);client(96);U32(slot(),0x24)=20;
  /* Existing 5ms fade in progress when consumed completion is recognized. */
  s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=0;s->d.effective=key(1000,9000,1,0,0);b->held_start=bits(.1f);b->held_end=bits(.9f);
  for(int iteration=0;iteration<12;iteration++){
   endpoints(r,.4f,1);void *p=params+index*0x34;INT(p,8)=1;INT(p,0x10)=1;INT(p,0x1c)=1;INT(p,0x30)=1;
   scheduler[0x124+(index>>3)]|=1u<<(index&7);dirty[index>>3]|=1u<<(index&7);U32(producer(r),0x80)=bits(.9f);U32(producer(r),0x84)=bits(.1f);
   trace_n=0;pre(4);client(96);CHECK(trace_n==5&&trace[0]==1&&trace[1]==2&&trace[2]==3&&trace[3]==4&&trace[4]==5);
   CHECK(DONE(r));CHECK(INT(r,0x58)==0&&INT(r,0x60)==0);CHECK(s->d.has_fade&&s->d.end==240&&s->d.start==0);
   for(int j=0;j<96;j++)CHECK(audioL[j]==0&&audioR[j]==0);
   for(int j=0;j<32;j++){workL[j]=1;workR[j]=2;}
   unsigned char cf[256]={0};INT(cf+8,0x28)=ch;Capture c=ctx();c.rbx=(uintptr_t)work;u64 old=s->d.clock;dispatch(&c,FILTER|128,cf);
   for(int j=0;j<32;j++){float expected=old+j>=240?0:(240.f-old-j)/240.f;CHECK(workL[j]>expected-1e-6&&workL[j]<expected+1e-6);CHECK(workR[j]==2*workL[j]);}
  }
 }
 ++groups;
}
static void lifecycle_tests(void){
 record(0,20,96,0,0);U32(slot(),0x24)=20;pre(1);CHECK(DONE(reader[0]));DONE(reader[1])=1;
 Capture in=ctx(),out={0};in.rdi=(uintptr_t)reader[1];in.rbp=(uintptr_t)scheduler;in.flags=0x202;
 open_result=1;fixture_call(b5_image+OFF_b8_wrap_open,&in,&out);CHECK(out.rax==1&&DONE(reader[1]));CHECK(DONE(reader[0]));
 open_result=0;fixture_call(b5_image+OFF_b8_wrap_open,&in,&out);CHECK(out.rax==0&&!DONE(reader[1])&&DONE(reader[0]));CHECK(out.rbx==in.rbx&&out.r12==in.r12&&out.r13==in.r13&&out.r14==in.r14&&out.r15==in.r15);
 CHECK(out.rcx==101&&out.rdx==202&&out.rsi==303&&out.rdi==404&&out.r8==505&&out.r9==606&&out.r10==707&&out.r11==808);
 CHECK((out.flags&0x8d5)==0x44);for(unsigned j=0;j<256;j++)CHECK(out.xmm[j]==(j<240?255:0));
 /* Successful Open supplied the deferred inherited initialization. */
 CHECK(DONE(reader[0]));CHECK(!(b->packed&PUBLISHED));
 INT(scheduler,0x24)=1;pre(2);client(96);CHECK(PTR(slot(),8)==reader[1]);CHECK(!DONE(reader[1]));CHECK(audioL[0]!=0);
 for(int i=0;i<128;i++)DONE(reader[i])=1;
 in=ctx();in.rdi=(uintptr_t)scheduler;dispatch(&in,RESET,frame);b8(&in,2,frame);
 for(int i=0;i<128;i++)CHECK(!DONE(reader[i]));
 /* Slot reuse in oscillator 2's range and another stereo note. */
 select_slot(32);INT(PTR(slot(),8),0xcc)=-1;pre(1);client(96);CHECK(audioL[0]!=0&&!DONE(PTR(slot(),8)));
 ++groups;
}
static void loop_identity_tests(void){
 for(int rev=0;rev<2;rev++){
  record(rev,20,96,0,1);U32(slot(),0x24)=96;pre(2);CHECK(!DONE(reader[0]));client(96);CHECK(audioL[0]!=0);
 }
 record(0,20,96,0,0);U32(slot(),0x24)=20;++b->sequence;pre(1);CHECK(!DONE(reader[0]));
 record(0,20,96,0,0);U32(slot(),0x24)=20;b->published_key.loop=1;pre(1);CHECK(!DONE(reader[0]));
 record(0,20,96,0,0);U32(slot(),0x24)=20;b->published_start=30;pre(1);CHECK(!DONE(reader[0]));
 /* Pending replacement bypasses old terminal count even if it has just reached EOF. */
 record(0,20,96,0,0);U32(slot(),0x24)=20;INT(scheduler,0x24)=1;pre(1);CHECK(!DONE(reader[0]));
 /* Unowned readers are rejected before extension access. */
 fresh();PTR(scheduler,0)=NULL;Capture c=ctx();b8(&c,0,frame);CHECK(!DONE(reader[0]));
 ++groups;
}
static void jump_contract_tests(void){
 fresh();Capture in=ctx(),out={0};in.flags=0x246;
 for(unsigned j=0;j<256;j++)in.xmm[j]=(unsigned char)(j*17+3);
 in.rsi=901;in.rdx=902;in.rcx=903;in.rax=904;in.r8=905;in.r9=906;in.r10=907;in.r11=908;
 fixture_jump_target=b5_image+OFF_b8_hook_prepare;fixture_call(fixture_jump_prepare,&in,&out);
 CHECK(out.rdi==(uintptr_t)scheduler&&out.r15==in.r15&&out.r11==in.r11&&out.rax==in.rax&&out.rcx==in.rcx);
 CHECK(!memcmp(out.xmm,in.xmm+16,16)&&!memcmp(out.xmm+16,in.xmm+16,240));CHECK((out.flags&0x8d5)==(in.flags&0x8d5));
 unsigned char valid=0;b->staged_reader=(uintptr_t)reader[0];b->packed|=ACTIVE;
 in=ctx();in.flags=0x246;in.rax=1234;in.rcx=(uintptr_t)&valid;in.rbp=96;in.r13=4;in.r15=(uintptr_t)raw[0];
 fixture_jump_target=b5_image+OFF_b8_hook_gate;fixture_call(fixture_jump_gate,&in,&out);
 CHECK(INT(reader[0],0x94)==1234&&out.rax==1234);CHECK((out.flags&0x8d5)==(in.flags&0x8d5));CHECK(valid==0);
 DONE(reader[0])=1;memset(raw[0],0x55,384);fixture_call(fixture_jump_gate,&in,&out);CHECK(valid==1);for(int j=0;j<384;j++)CHECK(raw[0][j]==0);
 /* Completed NoteOn defers B5 reset; failed Open leaves envelope and latch. */
 s->d.has_fade=1;s->d.start=0;s->d.end=240;s->d.clock=32;DONE(reader[0])=3;
 in=ctx();in.rbp=(uintptr_t)osc;fixture_jump_target=b5_image+OFF_b8_hook_note;fixture_call(fixture_jump_note,&in,&out);
 CHECK(fixture_branch_path==1&&s->d.has_fade&&s->d.end==240&&DONE(reader[0]));
 Capture oc=ctx();oc.rdi=(uintptr_t)reader[1];oc.rbp=(uintptr_t)scheduler;DONE(reader[1])=1;open_result=1;
 fixture_call(b5_image+OFF_b8_wrap_open,&oc,&out);CHECK(s->d.has_fade&&s->d.end==240&&DONE(reader[0])&&DONE(reader[1]));
 /* Real inherited unavailable dispatch, then B8 common epilogue repair. */
 in=ctx();in.rax=0;dispatch(&in,RETURN,frame);CHECK(!s->d.has_fade);
 in.rcx=0x12345678;fixture_jump_target=b5_image+OFF_b8_hook_return;fixture_call(fixture_jump_return,&in,&out);
 CHECK(s->d.has_fade&&s->d.start==0&&s->d.end==240&&s->d.clock==32);CHECK(out.rcx==in.rcx);
 open_result=0;fixture_call(b5_image+OFF_b8_wrap_open,&oc,&out);CHECK(!DONE(reader[1])&&!s->d.has_fade&&!s->d.end);
 DONE(reader[0])=0;in=ctx();in.rbp=(uintptr_t)osc;fixture_jump_target=b5_image+OFF_b8_hook_note;fixture_call(fixture_jump_note,&in,&out);CHECK(fixture_branch_path==0);
 /* Reset follows the real inherited attach, with both original prologue saves. */
 for(int j=0;j<128;j++)DONE(reader[j])=1;in=ctx();in.rdi=(uintptr_t)scheduler;dispatch(&in,RESET,frame);
 fixture_jump_target=b5_image+OFF_b8_hook_reset;fixture_call(fixture_jump_reset,&in,&out);for(int j=0;j<128;j++)CHECK(!DONE(reader[j]));
 ++groups;
}
static void transition_tests(void){
 for(int rev=0;rev<2;rev++){
  record(rev,20,96,0,1);U32(slot(),0x24)=0;INT(params,8)=0;scheduler[0x124]=dirty[0]=1;pre(1);client(96);
  if(b->published_key.loop || b->published_boundary!=20)fprintf(stderr,"transition rev=%d loop=%u pub=%d cc=%d origin=%d pendingloop=%d snapshot=%d\n",rev,b->published_key.loop,b->published_boundary,INT(reader[0],0xcc),INT(reader[0],0x94),INT(reader[0],0x28),INT(reader[0],0x58));
  if(!(b->packed&PUBLISHED))fprintf(stderr,"packed=%x valid=%u rb=%lld seq=%u pseq=%u count=%u\n",b->packed,s->d.read_valid,s->d.read_boundary,b->sequence,b->published_sequence,b->packed&0x7ff);
  CHECK(!DONE(reader[0])&&b->published_key.loop==0&&b->published_boundary==20);
  U32(slot(),0x24)=20;INT(params,8)=1;scheduler[0x124]=dirty[0]=1;pre(4);client(96);CHECK(DONE(reader[0])&&audioL[0]==0&&INT(reader[0],0x58)==0);
  record(rev,20,96,0,0);U32(slot(),0x24)=10;INT(params,8)=1;scheduler[0x124]=dirty[0]=1;pre(1);client(96);CHECK(!DONE(reader[0])&&INT(reader[0],0x58)==1&&audioL[0]!=0);
 }
 record(0,20,16,30,1);INT(reader[0],0x28)=0;U32(slot(),0x24)=16;pre(1);client(96);CHECK(b->packed&PUBLISHED);int e=b->published_boundary;
 CHECK(e>=33&&e<=34);U32(slot(),0x24)=e-1;pre(4);CHECK(!DONE(reader[0]));U32(slot(),0x24)=e;pre(4);CHECK(DONE(reader[0]));
 record(0,20,96,0,0);b->published_start=12;b->published_boundary=32;U32(slot(),0x24)=12;pre(1);CHECK(!DONE(reader[0]));U32(slot(),0x24)=31;pre(1);CHECK(!DONE(reader[0]));U32(slot(),0x24)=32;pre(1);CHECK(DONE(reader[0]));
 /* New Prepare JMP -> saved stock instructions -> real inherited B5 Prepare
  * -> virtual Client -> actual inherited Read/Publish CALL wrappers. */
 record(0,20,96,0,0);U32(slot(),0x24)=20;endpoints(reader[0],.1f,1);Capture in=ctx(),out={0};U32(&in,16)=bits(4);
 fixture_prepare_route_target=fixture_stock_prepare;fixture_jump_target=b5_image+OFF_b8_hook_prepare;trace_n=0;
 fixture_call(fixture_jump_prepare,&in,&out);fixture_prepare_route_target=fixture_continue_prepare;
 CHECK(DONE(reader[0])&&audioL[0]==0&&s->d.effective.b==9000);CHECK(trace_n==4&&trace[0]==2&&trace[1]==3&&trace[2]==4&&trace[3]==5);
 ++groups;
}
static void slot_and_direction_tests(void){
 for(unsigned i=0;i<64;i++){
  fresh();select_slot(i);void *a=PTR(slot(),8),*p=PTR(slot(),16);DONE(a)=DONE(p)=1;
  s->d.has_fade=1;s->d.start=10;s->d.end=250;Capture in=ctx(),out={0};in.rbp=(uintptr_t)scheduler;in.rdi=(uintptr_t)p;
  open_result=1;fixture_call(b5_image+OFF_b8_wrap_open,&in,&out);CHECK(DONE(a)&&DONE(p)&&s->d.has_fade);
  open_result=0;fixture_call(b5_image+OFF_b8_wrap_open,&in,&out);CHECK(DONE(a)&&!DONE(p)&&!s->d.has_fade);
  INT(scheduler,0x24+4*i)=1;pre(1);client(96);CHECK(PTR(slot(),8)==p&&!DONE(p)&&audioL[0]!=0);
 }
 /* Read's fractional follows-center reverse is authoritative even though
  * stock UpdateLoc's truncated-center comparison can select forward. */
 fresh();INT(reader[0],0x94)=INT(reader[0],0xcc)=1020;INT(reader[0],0x40)=INT(reader[0],0x50)=1;
 U32(producer(reader[0]),0x80)=bits(.010075f);U32(producer(reader[0]),0x84)=bits(.010050f);
 pre(1);client(96);CHECK(b->published_key.reverse==1&&b->published_boundary==20&&INT(reader[0],0x60)==0);
 U32(slot(),0x24)=19;pre(2);CHECK(!DONE(reader[0]));U32(slot(),0x24)=20;pre(2);CHECK(DONE(reader[0]));
 ++groups;
}
static double now(void){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return ts.tv_sec+ts.tv_nsec*1e-9;}
static void bench(void){
 fresh();pre(1);client(96);U32(slot(),0x24)=0;const unsigned n=200000;Capture c=ctx();U32(&c,16)=bits(1);
 double a=now();for(unsigned j=0;j<n;j++)b8(&c,0,frame);double elapsed=now()-a;
 printf("B8 preflight host %.3f us/call (%u iterations, includes fixture capture copy)\n",elapsed*1e6/n,n);
}
int main(void){consumption_tests();delay_tiny_tests();zero_controls_and_order();lifecycle_tests();loop_identity_tests();jump_contract_tests();transition_tests();slot_and_direction_tests();bench();printf("PASS %u focused checks in %u groups (actual inherited B5 + new B8 emitted adapters/wrappers, stock reader/scheduler fixtures)\n",checks,groups);return 0;}

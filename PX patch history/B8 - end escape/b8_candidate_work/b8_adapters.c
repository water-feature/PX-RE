// SPDX-License-Identifier: GPL-2.0-or-later
/* B8 interposers: inherited B1/B5 instructions and helpers stay byte-identical.
 * Only new persistent state is one byte per owned CWavReader at +0x1c0.
 */
#include "../b5_candidate_work/b5_core.generated.h"
#define FN __attribute__((visibility("hidden"),noinline))
#define PTR(p,o) (*(void **)((unsigned char *)(p)+(o)))
#define U32(p,o) (*(u32 *)((unsigned char *)(p)+(o)))
#define INT(p,o) (*(int *)((unsigned char *)(p)+(o)))
#define DONE(p) (*((unsigned char *)(p)+0x1c0))
typedef struct { unsigned char xmm[256];u64 r15,r14,r13,r12,rbp,rbx,r11,r10,r9,r8,rdi,rsi,rdx,rcx,rax,flags; } Capture;
typedef struct {
 u32 held_start,held_end,latest_start,latest_end;u64 rate_slot;
 Key published_key;int published_boundary;u64 staged_reader;
 int staged_start,published_start;u32 sequence,published_sequence,requested_rate,packed;
} Bridge;
_Static_assert(sizeof(Capture)==384,"capture ABI");
_Static_assert(sizeof(Fields)+sizeof(Bridge)==256,"inherited sidecar ABI");
#define COUNT 0x7ffu
#define OK (1u<<23)
#define PUBLISHED (1u<<24)
#define OPAQUE (1u<<28)
#define SPAN (1u<<27)
#define ACTIVE (1u<<22)
extern __attribute__((visibility("hidden"))) unsigned char b5_ram_vtable[],b5_read_original_return[];
extern __attribute__((visibility("hidden"))) unsigned char b8_continue_gate[],b8_zero[];
extern __attribute__((visibility("hidden"))) unsigned char b8_continue_note[],b8_note_skip[];
static State *owned(void *scheduler,void *slot) {
 if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable)return (State *)0;
 unsigned char *base=PTR(scheduler,8);u64 diff=(u64)(unsigned long)slot-(u64)(unsigned long)base;
 if(diff>=0xc00 || diff%0x30)return (State *)0;
 State *s=(State *)(base+0xc00+(diff/0x30)*256);
 return s->d.owner==(u64)(unsigned long)scheduler?s:(State *)0;
}
static Bridge *bridge(State *s){return (Bridge *)(s->bytes+sizeof(Fields));}
static void *bank(void *r,unsigned n){return (unsigned char *)PTR(r,0x1a8)+(n&1)*0x280;}
FN void b8_dispatch(Capture *c,unsigned event,unsigned char *frame) {
 if(event==0){
  void *osc=(void *)(unsigned long)c->r15;
  if(!osc || U32(osc,8)>=64)return;
  unsigned index=U32(osc,8);void *scheduler=PTR(osc,0x30);
  if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable)return;
  void *slot=(unsigned char *)PTR(scheduler,8)+index*0x30;
  State *s=owned(scheduler,slot);if(!s)return;
  void *r=PTR(slot,8);if(PTR(r,0x1b8)!=s)return;
  /* Exactly Client's replacement decision; old data cannot complete a new reader. */
  if(INT(scheduler,0x24+4*index))return;
  Bridge *d=bridge(s);int n=INT(slot,0x18),u=INT(slot,0x24);if(u>n)u=n;
  int e=d->published_boundary;
  if(!DONE(r) && (d->packed&(OK|PUBLISHED))==(OK|PUBLISHED)
     && d->staged_reader==(u64)(unsigned long)r
     && d->published_sequence==d->sequence && d->published_sequence
     && (int)(d->packed&COUNT)==n && n>0 && u>0
     && !d->published_key.loop && e>=0 && e<=n && u>=e
     && (d->published_start<0 || (e>=d->published_start && u>d->published_start)))DONE(r)=1;
  if(!DONE(r))return;
  if(s->d.has_fade)DONE(r)|=2; /* retain existing envelope across unavailable returns */
  s->d.has_pending=0;
  /* No new audible configuration exists for a completed reader. Keep the old
   * B5 key/envelope; requested UI values remain in CParams and scheduler packet.
   * The next legitimate Open/NoteOn reads them normally. No new shadow state.
   */
  unsigned consumed=(U32(r,0x1b0)+1)&1;void *old=bank(r,consumed),*next=bank(r,U32(r,0x1b0));
  for(unsigned o=0;o<=0x200;o+=0x80)U32(next,o)=U32(old,o);
  U32(next,0x84)=U32(old,0x84);
  for(unsigned o=4;o<0x30;o+=4)U32(r,0x24+o)=U32(r,0x54+o);
  INT(r,0x24)=-1;
  unsigned mask=1u<<(index&7);*((unsigned char *)scheduler+0x124+(index>>3))&=~mask;
  *((unsigned char *)PTR(scheduler,0x18)+(index>>3))&=~mask;
  u32 bits=s->d.effective.rate_bits;FloatBits rate;rate.u=bits;
  if(!(rate.f>0))bits=U32(r,0x198+4*consumed);
  U32(c,16)=bits; /* displaced MOVAPS XMM0,XMM1 and saved rate use this */
  return;
 }
 if(event==1){
  *(u64 *)((unsigned char *)c+384)=(u64)(unsigned long)b8_continue_gate;
  /* Original Read's caller marker is checked before any extension read. */
  if(PTR(frame,168)!=(void *)b5_read_original_return)return;
  void *r=(void *)(unsigned long)c->rdi;State *s=PTR(r,0x1b8);
  if(!s || bridge(s)->staged_reader!=(u64)(unsigned long)r || !(bridge(s)->packed&ACTIVE) || !DONE(r))return;
  if(PTR(frame,0))*((unsigned char *)PTR(frame,0))=1;
  bridge(s)->packed&=~OPAQUE; /* all of this batch is synthetic terminal input */
  s->d.read_valid=1;s->d.read_boundary=0;
  *(u64 *)((unsigned char *)c+384)=(u64)(unsigned long)b8_zero;
  return;
 }
 if(event==2){
  void *scheduler=(void *)(unsigned long)c->rdi;
  if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable)return;
  for(unsigned i=0;i<64;i++){
   void *slot=(unsigned char *)PTR(scheduler,8)+i*0x30;State *s=owned(scheduler,slot);if(!s)continue;
   void *a=PTR(slot,8),*b=PTR(slot,16);
   if(PTR(a,0x1b8)==s)DONE(a)=0;if(PTR(b,0x1b8)==s)DONE(b)=0;
  }
  return;
 }
 if(event==3){*(u64 *)((unsigned char *)c+384)=c->rdi;return;}
 if(event==4 || event==5){
  if(event==4)*(u64 *)((unsigned char *)c+384)=(u64)(unsigned long)b8_continue_note;
  void *osc=(void *)(unsigned long)(event==4?c->rbp:c->r15);
  if(!osc || U32(osc,8)>=64)return;
  void *scheduler=PTR(osc,0x30);
  if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable)return;
  void *slot=(unsigned char *)PTR(scheduler,8)+U32(osc,8)*0x30;
  State *s=owned(scheduler,slot);if(!s)return;
  void *r=PTR(slot,8);if(PTR(r,0x1b8)!=s || !DONE(r))return;
  if(event==4){
   /* Failed NoteOn/OpenStream must not erase a completed instance's B5 tail.
    * Successful Open below supplies the deferred normal B5 initialization. */
   *(u64 *)((unsigned char *)c+384)=(u64)(unsigned long)b8_note_skip;
  }else if((DONE(r)&2) && s->d.end>s->d.start){
   s->d.has_fade=1;s->d.has_pending=s->d.no_opportunity=0;
  }
  return;
 }
 if(event==131 && (int)c->rax==0){
  void *scheduler=(void *)(unsigned long)c->rbp;
  if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable)return;
  unsigned off=U32(frame,0x28);if(off>=0xc00 || off%0x30)return;
  void *slot=(unsigned char *)PTR(scheduler,8)+off;State *s=owned(scheduler,slot);if(!s)return;
  void *r=(void *)(unsigned long)*(u64 *)((unsigned char *)c+384);
  if(r==PTR(slot,16) && PTR(r,0x1b8)==s){
   void *active=PTR(slot,8);
   if(PTR(active,0x1b8)==s && DONE(active)){
    Key key={0,0,0,0,0};b5_note_on(s,&key,s->d.owner);
   }
   DONE(r)=0;
  }
 }
}

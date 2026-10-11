/* Standalone B5 endpoint-bank integration. No ELF writer or new audio buffers.
 * Raw object offsets are the previously recovered QNX contracts.
 */
#include "b5_core.generated.h"
#define FN __attribute__((visibility("hidden"),noinline))
#define U32(p,o) (*(u32 *)((unsigned char *)(p)+(o)))
#define U64(p,o) (*(u64 *)((unsigned char *)(p)+(o)))
#define PTR(p,o) (*(void **)((unsigned char *)(p)+(o)))
#define INT(p,o) (*(int *)((unsigned char *)(p)+(o)))
typedef struct {
    unsigned char xmm[256];
    u64 r15,r14,r13,r12,rbp,rbx,r11,r10,r9,r8,rdi,rsi,rdx,rcx,rax,flags;
} Capture;
typedef struct {
    u32 held_start,held_end,latest_start,latest_end;
    u64 rate_slot;
    Key published_key;
    int published_boundary;
    u64 staged_reader;
    int staged_start,published_start;
    u32 sequence,published_sequence,requested_rate,packed;
} Bridge;
_Static_assert(sizeof(Capture)==384,"capture ABI");
_Static_assert(sizeof(Fields)+sizeof(Bridge)==256,"owned sidecar ABI");
#define PUB_COUNT 0x7ffu
#define STAGE_COUNT (0x7ffu<<11)
#define ACTIVE (1u<<22)
#define OK (1u<<23)
#define PUBLISHED (1u<<24)
#define HELD (1u<<25)
#define GEOMETRY (1u<<26)
#define SPAN (1u<<27)
#define OPAQUE (1u<<28)
#define LOAD_ARMED (1u<<29)
#define PREPARED (1u<<30)
#define PUBLISH_ARMED (1u<<31)
enum { FORWARD,REVERSE,GEOM,PREPARE,NOTE,RESET,RETURN,EOF_ZONE,READ,LOAD,FILTER,PUBLISH };
extern __attribute__((visibility("hidden"))) unsigned char b5_ram_vtable[],b5_read_original_return[];
static Bridge *bridge(State *s) { return (Bridge *)(s->bytes+sizeof(Fields)); }
static unsigned char *bank(void *reader,unsigned which) {
    return (unsigned char *)PTR(reader,0x1a8)+(which&1)*0x280;
}
static int ramp(State *s) { return s->d.has_fade && s->d.start<s->d.clock && s->d.clock<s->d.end; }
static int equal(const Key *a,const Key *b) {
    return a->a==b->a && a->b==b->b && a->rate_bits==b->rate_bits && a->reverse==b->reverse && a->loop==b->loop;
}
static State *slot_state(void *scheduler,void *slot) {
    if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable) return (State *)0;
    unsigned char *base=PTR(scheduler,8);
    u64 diff=(u64)(unsigned long)slot-(u64)(unsigned long)base;
    if(diff>=0xc00 || diff%0x30) return (State *)0;
    State *s=(State *)(base+0xc00+(diff/0x30)*0x100);
    return s->d.owner==(u64)(unsigned long)scheduler ? s : (State *)0;
}
static State *osc_state(void *osc,void **slot_out) {
    if(!osc || U32(osc,8)>=64) return (State *)0;
    void *scheduler=PTR(osc,0x30);
    if(!scheduler || PTR(scheduler,0)!=(void *)b5_ram_vtable) return (State *)0;
    void *slot=(unsigned char *)PTR(scheduler,8)+U32(osc,8)*0x30;
    if(slot_out) *slot_out=slot;
    return slot_state(scheduler,slot);
}
static int cvttf(float f) { int v;__asm__("cvttss2si %1,%0":"=r"(v):"x"(f));return v; }
static int cvttd(double f) { int v;__asm__("cvttsd2si %1,%0":"=r"(v):"x"(f));return v; }
static float fvalue(u32 bits) { FloatBits f;f.u=bits;return f.f; }
static int pending(void *reader,int offset,void *params,int param_offset) {
    return params && INT(params,param_offset)>=0 ? INT(params,param_offset) : INT(reader,offset);
}
/* Both loop-disabled Read branches use these outer clamps. Read's observed
 * frame values remain authoritative; loop working geometry is never faded.
 */
static Key requested_key(void *reader,void *producer,void *params,u32 rate_bits) {
    int n=INT(reader,0xa0);float last=(float)(n-1);
    int a=cvttf(fvalue(U32(producer,0))*last);
    if(a>=n-32) a=n-33;
    if(a<0) a=0;
    int b=cvttf(fvalue(U32(producer,0x180))*last);
    if(b<a+32) b=a+32;
    if(b>n-1) b=n-1;
    int custom=pending(reader,0x40,params,0x1c);
    int follows=pending(reader,0x50,params,0x30);
    int reverse=pending(reader,0x30,params,0x10)!=0;
    if(follows) reverse=custom ? !(fvalue(U32(producer,0x84))*last>=fvalue(U32(producer,0x80))*last) : 0;
    Key key={a,b,rate_bits,(u32)reverse,(u32)(pending(reader,0x28,params,8)!=0)};
    return key;
}
static void cancel(State *s) {
    s->d.has_fade=s->d.has_pending=s->d.no_opportunity=0;
}
static State *reader_state(Capture *c,unsigned char *frame,int geometry) {
    /* Global CWavReader shims must not dereference an extension in an unrelated
     * reader instance. Only our owned scheduler CALL wrapper authorizes it.
     */
    if(PTR(frame,168)!=(void *)b5_read_original_return) return (State *)0;
    void *reader=(void *)(unsigned long)(geometry ? c->rdi : c->rbx);
    State *s=PTR(reader,0x1b8);
    if(!s || !(bridge(s)->packed&ACTIVE) || bridge(s)->staged_reader!=(u64)(unsigned long)reader) return (State *)0;
    return s;
}

FN void b5_dispatch(Capture *c,unsigned event,unsigned char *frame) {
    int after=(event&128)!=0;event&=127;
    void *slot=(void *)0;State *s=(State *)0;Bridge *d=(Bridge *)0;
    if(event==RESET) { b5_attach((void *)(unsigned long)c->rdi);return; }
    if(event==PREPARE || event==RETURN || event==NOTE || event==LOAD || event==FILTER) {
        void *osc=(void *)(unsigned long)(event==NOTE ? c->rbp : c->r15);
        s=osc_state(osc,&slot);if(!s)return;d=bridge(s);
        if(event==NOTE) { Key key={0,0,0,0,0};b5_note_on(s,&key,s->d.owner);return; }
        if(event==PREPARE) {
            void *scheduler=(void *)(unsigned long)s->d.owner;
            int index=U32(osc,8);
            void *active=PTR(slot,8);
            void *target=INT(scheduler,0x24+index*4) ? PTR(slot,16) : active;
            unsigned char *producer=bank(active,U32(active,0x1b0));
            void *params=(*((unsigned char *)scheduler+0x124+(index>>3))&(1u<<(index&7))) ? (unsigned char *)PTR(scheduler,0x10)+index*0x34 : (void *)0;
            d->latest_start=U32(producer,0);d->latest_end=U32(producer,0x180);
            d->requested_rate=U32(c,0);
            Key request=requested_key(target,producer,params,d->requested_rate);
            /* Clone copies endpoint fractions, not the pending file's length or
             * channels. A changed geometry basis is a new reader context and
             * cannot carry this region's hold. Release before Client runs. */
            if(INT(target,0xa0)!=INT(active,0xa0)
               || *(unsigned short *)((unsigned char *)target+0xa8)!=*(unsigned short *)((unsigned char *)active+0xa8)) cancel(s);
            if(INT(target,0x24)>=0 || (params && (INT(params,0)>=0 || fvalue(U32(params,4))>=0))) cancel(s);
            b5_begin(s,&request);
            if(!ramp(s)) { d->held_start=d->latest_start;d->held_end=d->latest_end; }
            if(ramp(s)) { U32(c,0)=s->d.effective.rate_bits;U32(frame,0x14)=s->d.effective.rate_bits; }
            d->rate_slot=(u64)(unsigned long)(frame+0x14);d->packed|=PREPARED;
            return;
        }
        if(event==RETURN) {
            if((int)c->rax!=32) b5_unavailable(s);
            d->rate_slot=0;d->packed&=~(PREPARED|LOAD_ARMED);
            return;
        }
        if(event==LOAD) {
            void *resampler=PTR(osc,0x10);
            if(!after) {
                s->d.phase=*(double *)((unsigned char *)resampler+8);
                s->d.write=*(double *)((unsigned char *)resampler+16);
                void **buffers=PTR(slot,0);
                u64 diff=c->rsi-(u64)(unsigned long)buffers[0];
                if(c->rdi==(u64)(unsigned long)resampler && (d->packed&PUBLISHED)
                   && !(diff&3) && diff/4==(u32)c->rbp && diff/4<=(d->packed&PUB_COUNT)) d->packed|=LOAD_ARMED;
                else d->packed&=~LOAD_ARMED;
            } else {
                double pre=s->d.write,phase=s->d.phase;
                int needed=cvttd(((double)*(float *)((unsigned char *)resampler+4)+phase)-pre+1.0);
                int copied=(int)c->rax;int available=INT(frame+8,0x2c);
                if(copied>available)copied=available;
                if(copied<0)copied=0;
                int offset=(int)c->rbp;
                int valid=(d->packed&LOAD_ARMED) && offset>=0
                    && offset+copied<=(int)(d->packed&PUB_COUNT)
                    && (d->published_start<0 || offset+copied>d->published_start);
                /* Read's staging fields may describe a newer raw read. Only the
                 * descriptor committed with the normalized slot buffers is used.
                 */
                Key staged=s->d.read_key;i64 staged_boundary=s->d.read_boundary;u32 staged_valid=s->d.read_valid;
                b5_read_descriptor(s,&d->published_key,d->published_boundary,valid);
                b5_loaded(s,offset,copied,needed,pre,phase,*(double *)((unsigned char *)resampler+16));
                s->d.read_key=staged;s->d.read_boundary=staged_boundary;s->d.read_valid=staged_valid;
                d->packed&=~LOAD_ARMED;
            }
            return;
        }
        if(event==FILTER && after) {
            void *left=PTR(osc,0x10),*right=PTR(osc,0x18);
            if(INT(frame+8,0x28)>1 && (*(double *)((unsigned char *)left+8)!=*(double *)((unsigned char *)right+8)
                 || *(double *)((unsigned char *)left+16)!=*(double *)((unsigned char *)right+16)
                 || U32(left,0)!=U32(right,0))) { b5_unavailable(s);s->d.endpoint_valid=0; }
            float **work=(float **)(unsigned long)c->rbx;
            b5_render(s,work[0],work[1]);return;
        }
        return;
    }
    if(event==READ || event==PUBLISH) {
        s=slot_state((void *)(unsigned long)c->r13,(void *)(unsigned long)c->rbx);
        if(!s)return;d=bridge(s);slot=(void *)(unsigned long)c->rbx;
        if(event==READ && !after) {
            void *reader=(void *)(unsigned long)c->rdi;
            if(reader!=PTR(slot,8) || PTR(reader,0x1b8)!=s)return;
            ++d->sequence;if(!d->sequence)++d->sequence;
            d->staged_reader=c->rdi;d->staged_start=0;
            d->packed=(d->packed&~(STAGE_COUNT|ACTIVE|OK|GEOMETRY|SPAN|HELD))
                |ACTIVE|(((u32)c->rsi&0x7ff)<<11);
            if(U32(reader,8)&255)d->packed|=OPAQUE;else d->packed&=~OPAQUE;
            s->d.read_valid=0;s->d.read_boundary=-1;
            unsigned char *producer=bank(reader,U32(reader,0x1b0));
            if((d->packed&PREPARED) && d->rate_slot && ramp(s)) {
                Key actual=requested_key(reader,producer,(void *)0,d->requested_rate);
                if(actual.loop!=s->d.effective.loop || actual.reverse!=s->d.effective.reverse || INT(reader,0x24)>=0) {
                    cancel(s);b5_begin(s,&actual);
                    U32(c,0)=d->requested_rate;U32((void *)(unsigned long)d->rate_slot,0)=d->requested_rate;
                    int n=cvttf(fvalue(d->requested_rate));
                    if(fvalue(d->requested_rate)!=(float)n)n=cvttf(fvalue(d->requested_rate)+1.0f);
                    n=(n+2)*32;if(n>0x440 || n<0)n=0x440;
                    c->rsi=(u32)n;c->rbp=(u32)n;
                    d->packed=(d->packed&~STAGE_COUNT)|((u32)n<<11);
                } else {
                    U32(producer,0)=d->held_start;U32(producer,0x180)=d->held_end;d->packed|=HELD;
                }
            }
        } else if(event==READ) {
            d->packed&=~ACTIVE;
            if((int)c->rax==0 && U32(slot,0x2c)&255)d->packed|=OK;else d->packed&=~OK;
            if(d->packed&HELD) {
                void *reader=(void *)(unsigned long)d->staged_reader;
                /* Do not restore the just-consumed bank. UpdateLoc still needs
                 * its held endpoints on the next block, even at completion.
                 */
                unsigned char *next=bank(reader,U32(reader,0x1b0));
                U32(next,0)=d->latest_start;U32(next,0x180)=d->latest_end;
            }
        } else if(!after) {
            void **buffers=PTR(slot,0);
            /* ACTIVE is reused here as publication-match only after Read ends. */
            d->packed&=~(PUBLISH_ARMED|ACTIVE);
            if(c->rdx==(u64)(unsigned long)buffers) {
                d->packed|=PUBLISH_ARMED;
                if(c->rdi==d->staged_reader && c->rsi==((d->packed&STAGE_COUNT)>>11)) d->packed|=ACTIVE;
            }
        } else {
            if(d->packed&PUBLISH_ARMED) d->packed&=~PUBLISHED;
            if((d->packed&PUBLISH_ARMED) && (d->packed&ACTIVE) && (d->packed&OK) && s->d.read_valid) {
                d->published_key=s->d.read_key;d->published_boundary=(int)s->d.read_boundary;
                d->published_start=(d->packed&OPAQUE)?d->staged_start:-1;d->published_sequence=d->sequence;
                d->packed=(d->packed&~PUB_COUNT)|((d->packed&STAGE_COUNT)>>11)|PUBLISHED;
            }
            d->packed&=~(PUBLISH_ARMED|ACTIVE);
        }
        return;
    }
    s=reader_state(c,frame,event==GEOM);if(!s)return;d=bridge(s);
    void *reader=(void *)(unsigned long)d->staged_reader;
    if(event==GEOM) {
        unsigned consumed=(U32(reader,0x1b0)+1)&1;
        Key observed={INT(frame,0x24),INT(frame,0x10),U32(reader,0x198+4*consumed),
                      (u32)(frame[0x1c]!=0),(u32)(INT(reader,0x58)!=0)};
        s->d.read_key=observed;d->packed|=GEOMETRY;
        if((d->packed&PREPARED) && !observed.loop && !equal(&observed,&s->d.effective)) {
            cancel(s);b5_begin(s,&observed);
        }
        return;
    }
    if(!(d->packed&GEOMETRY) || s->d.read_key.loop || !(int)c->r13) return;
    i64 offset=((i64)c->r15-(i64)(unsigned long)PTR(reader,0xb8))/(int)c->r13;
    if(offset<0 || offset>((d->packed&STAGE_COUNT)>>11))return;
    if(event==EOF_ZONE) {
        if(!(d->packed&OPAQUE) || d->packed&SPAN) { s->d.read_boundary=offset;s->d.read_valid=1; }
    } else if(event==FORWARD || event==REVERSE) {
        i64 p=INT(reader,0x90);
        if(event==REVERSE)p+=(int)c->r12;
        i64 distance=event==REVERSE ? p-s->d.read_key.a : s->d.read_key.b-p;
        if(distance<0)return;
        if(!(d->packed&SPAN))d->staged_start=(int)offset;
        d->packed|=SPAN;s->d.read_boundary=offset+distance;s->d.read_valid=1;
    }
}

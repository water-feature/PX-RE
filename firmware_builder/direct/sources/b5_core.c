// SPDX-License-Identifier: GPL-2.0-or-later
/* Freestanding B5 core, staged implementation. Object adapters are not yet
 * installed. Never equate this core's successful tests with a QNX candidate.
 * The generated policy header comes from b5_fade_prototype.FADE_DURATION_MS.
 */
#include "b5_policy.generated.h"
typedef unsigned int u32;
typedef unsigned long long u64;
typedef long long i64;
typedef struct { int a,b; u32 rate_bits,reverse,loop; } Key;
typedef union { float f; u32 u; } FloatBits;
typedef struct {
    u64 owner,epoch,clock,start,end;
    i64 endpoint,read_boundary;
    double phase,write;
    Key effective,pending,read_key,timeline_key;
    u32 has_pending,has_fade,no_opportunity,endpoint_valid,terminal_seen,read_valid;
} Fields;
typedef union { Fields d; unsigned char bytes[256]; } State;
_Static_assert(sizeof(Fields)<=256,"B5 per-stream state reservation exceeded");
_Static_assert(sizeof(State)==256,"B5 state stride");
_Static_assert(sizeof(Key)==20,"B5 key ABI");
#define EXPORT __attribute__((visibility("hidden"),noinline))
static int same(const Key *a,const Key *b) {
    return a->a==b->a && a->b==b->b && a->rate_bits==b->rate_bits
        && a->reverse==b->reverse && a->loop==b->loop;
}
static float rate(const Key *k) { FloatBits r; r.u=k->rate_bits; return r.f; }
static int cvtt(double x) { int n; __asm__("cvttsd2si %1,%0":"=r"(n):"x"(x)); return n; }
static int eligible(const Key *k) {
    float r=rate(k);
    return !k->loop && r>0 && r<=0x1.fffffep127f && k->b>k->a
        && (double)((i64)k->b-k->a)>(double)B5_FADE_INTERVALS*r;
}

EXPORT int b5_predict(double phase,float r,i64 endpoint,double loaded_w) {
    double phi=phase,w=loaded_w,rd=r,r32=(float)(r*32.0f);
    if (!(r>0 && r<=0x1.fffffep127f)) return -1;
    /* Constant horizon is guarded just as in the proven host fast check. */
    if (B5_PREDICTION_HORIZON<=4096 && phase>=0 && phase<0x1p30
        && w>=0 && w<0x1p30 && w==(double)cvtt(w) && r<=32) {
        double bound=phase+((B5_PREDICTION_HORIZON-1)/32*32)*rd+r32+4.0;
        if (bound<0x1p30) {
            i64 upper=(i64)bound; if ((double)upper<bound) ++upper;
            i64 current=(i64)w-1; if (upper<current) upper=current;
            if (endpoint>upper) return -1;
        }
    }
    for (int j=0;j<B5_PREDICTION_HORIZON;++j) {
        if(j && !(j&31)) {
            int n=cvtt(((r32+phi)-w)+1.0);
            if(n<0 || n>1038) return -1;
            w+=(double)n;
        }
        i64 latest=(i64)w-1;
        int first=cvtt(phi-14.0)&1023;
        for(int tap=0;tap<13;++tap) {
            int slot=(first+tap)&1023;
            i64 newest=latest-((latest-slot)&1023);
            if(newest>=0 && newest>=endpoint) return j;
        }
        phi=rd+phi;
    }
    return -1;
}

EXPORT void b5_reset(State *s,u64 owner) {
    volatile unsigned char *p=s->bytes;
    for(int j=0;j<256;++j) p[j]=0;
    s->d.owner=owner;
}
EXPORT void b5_note_on(State *s,const Key *k,u64 owner) {
    u64 epoch=s->d.epoch+1;
    b5_reset(s,owner);
    s->d.epoch=epoch;
    s->d.effective=*k;
}
static void apply(State *s,const Key *k) {
    if(!same(&s->d.effective,k)) {
        s->d.effective=*k;
        s->d.has_fade=0;
        s->d.no_opportunity=0;
    }
}
EXPORT const Key *b5_begin(State *s,const Key *request) {
    if(request && (request->loop!=s->d.effective.loop || request->reverse!=s->d.effective.reverse)) {
        s->d.has_pending=0;
        apply(s,request);
    } else if(s->d.has_fade && s->d.start<s->d.clock && s->d.clock<s->d.end) {
        if(request) { s->d.pending=*request; s->d.has_pending=1; }
    } else {
        const Key *k=request ? request : s->d.has_pending ? &s->d.pending : (const Key *)0;
        if(k) apply(s,k);
        s->d.has_pending=0;
    }
    return &s->d.effective;
}
/* Adapter supplies an ordinary Read descriptor. Opaque splices/errors do not
 * get an invented source mapping. boundary includes any start-delay prefix.
 */
EXPORT void b5_read_descriptor(State *s,const Key *k,i64 boundary,int valid) {
    s->d.read_key=*k; s->d.read_boundary=boundary; s->d.read_valid=valid;
}
EXPORT void b5_loaded(State *s,int offset,int copied,int needed,double pre_w,
                      double phase,double post_w) {
    s->d.phase=phase; s->d.write=post_w;
    if(!s->d.read_valid) { s->d.endpoint_valid=0; return; }
    if(!same(&s->d.timeline_key,&s->d.read_key)) {
        s->d.timeline_key=s->d.read_key;
        s->d.endpoint_valid=s->d.terminal_seen=0;
    }
    if(copied>0) {
        i64 relative=s->d.read_boundary-offset;
        i64 candidate=(i64)pre_w+relative;
        if(relative<copied) {
            i64 actual=(i64)pre_w+(relative>0 ? relative : 0);
            if(!s->d.terminal_seen || actual<s->d.endpoint) s->d.endpoint=actual;
            s->d.endpoint_valid=s->d.terminal_seen=1;
        } else if(!s->d.terminal_seen) {
            s->d.endpoint=candidate; s->d.endpoint_valid=1;
        }
    }
    if(copied<needed && !s->d.terminal_seen) s->d.endpoint_valid=0;
}
EXPORT void b5_unavailable(State *s) {
    if(s->d.has_fade && s->d.start<s->d.clock && s->d.clock<s->d.end) {
        s->d.has_fade=s->d.no_opportunity=0;
        if(s->d.has_pending) apply(s,&s->d.pending);
        s->d.has_pending=0;
    }
}
EXPORT void b5_render(State *s,float *left,float *right) {
    if(!eligible(&s->d.effective)) s->d.has_fade=0;
    else if(!s->d.has_fade && !s->d.no_opportunity && s->d.endpoint_valid
             && same(&s->d.timeline_key,&s->d.effective)) {
        int offset=b5_predict(s->d.phase,rate(&s->d.effective),s->d.endpoint,s->d.write);
        if(offset>=0) {
            u64 z=(s->d.clock+(u64)offset)&~31ULL;
            u64 start=z>B5_FADE_INTERVALS ? z-B5_FADE_INTERVALS : 0;
            if(start<s->d.clock) start=s->d.clock;
            if(start<s->d.clock+32) {
                if(z<=s->d.clock) s->d.no_opportunity=1;
                else { s->d.start=start; s->d.end=z; s->d.has_fade=1; }
            }
        }
    }
    for(int j=0;j<32;++j) {
        u64 at=s->d.clock+(u64)j;
        if(s->d.has_fade && at>s->d.start) {
            if(at>=s->d.end) left[j]=right[j]=0;
            else {
                double gain=(double)(s->d.end-at)/(double)(s->d.end-s->d.start);
                left[j]=(float)(left[j]*gain); right[j]=(float)(right[j]*gain);
            }
        }
    }
    s->d.clock+=32;
}

/* Owned scheduler allocation, retaining original 64 * 0x30 slot layout. */
EXPORT void b5_attach(void *scheduler) {
    unsigned char *slots=*(unsigned char **)((unsigned char *)scheduler+8);
    for(int i=0;i<64;++i) {
        State *s=(State *)(slots+0xc00+i*0x100);
        b5_reset(s,(u64)(unsigned long)scheduler);
        *(State **)(*(unsigned char **)(slots+i*0x30+8)+0x1b8)=s;
        *(State **)(*(unsigned char **)(slots+i*0x30+16)+0x1b8)=s;
    }
}

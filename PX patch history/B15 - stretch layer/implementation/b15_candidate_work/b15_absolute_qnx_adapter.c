/* Exact 2.2.2.1.7 QNX adapter. Raw ELF VAs; SysV AMD64 ABI.
   Not a standalone application. Assembly supplies the firmware detours. */
#include "b15_absolute_core.h"
typedef unsigned long b15_uptr;
#ifdef B15_ADAPTER_TEST
extern void *b15_test_address(b15_uptr addr);
extern unsigned char b15_test_runtime[768];
#define FN(addr,type) ((type)b15_test_address(addr))
#else
/* ET_DYN: all stock entry points are link-resolved PC-relative symbols. */
extern int b15_stock_fn_0x7a10(void*);
extern int b15_stock_fn_0x79a0(void*);
extern void b15_stock_fn_0x9700(void*,int,int,int);
extern void b15_stock_fn_0x1d7f0(void*,unsigned,unsigned);
extern void *b15_stock_fn_0x35940(void*,int,int,int,int,int,int,int);
extern const char *b15_stock_fn_0x36180(void*);
extern void b15_stock_fn_0x3ed50(const char*,void*,int,int);
#define B15_STOCK_NAME(addr) b15_stock_fn_##addr
#define FN(addr,type) ((type)B15_STOCK_NAME(addr))
#endif
#define GET(obj,off,type) (*(type *)((b15_u8 *)(obj)+(off)))
struct b15_runtime { struct b15_state core; void *loop; b15_u32 magic; b15_u32 group_mask; b15_u16 epoch_low[4]; };
#ifdef B15_ADAPTER_TEST
#define RT ((struct b15_runtime *)b15_test_runtime)
#else
extern struct b15_runtime b15_runtime_storage __attribute__((visibility("hidden")));
#define RT (&b15_runtime_storage)
#endif
_Static_assert(sizeof(struct b15_runtime)<=0x300,"QNX reservation overflow");
#ifdef B15_ADAPTER_TEST
#define MUTEX ((void *)(b15_uptr)0x2a57a0)
#else
extern unsigned char b15_stock_mutex[] __attribute__((visibility("hidden")));
#define MUTEX ((void*)b15_stock_mutex)
#endif
static void lock(void) { FN(0x7a10,int(*)(void*))(MUTEX); }
static void unlock(void) { FN(0x79a0,int(*)(void*))(MUTEX); }
static void send(unsigned cmd,unsigned data) {
    FN(0x1d7f0,void(*)(void*,unsigned,unsigned))(RT->loop,cmd,data);
}
static void *params(void) { return GET(RT->loop,0x20c0,void*); }
static unsigned id_for(unsigned p,unsigned a) { return a+(p&1)*0x41; }
static void set(unsigned p,unsigned id,unsigned n) {
    FN(0x9700,void(*)(void*,int,int,int))(params(),p>>1,id,n);
}

static void *find(void *g,unsigned p,unsigned key,int target) {
    return FN(0x35940,void*(*)(void*,int,int,int,int,int,int,int))
        (g,key,0,target,0,1,p>>1,p&1);
}
/* Eligibility/key-distance ordering matches 35940 first and second passes.
   Use the same stock resolver for final handler/round-robin semantics. */
static int highest(void *group,unsigned p,unsigned key) {
    void *head=GET(group,0x680,void*), *h;
    int distance=1000, top=-1;
    /* Stock first pass chooses the nearest key region before eligibility. */
    for (h=head;h;h=GET(h,0x240,void*)) {
        int lo=GET(h,0x200,int),hi=GET(h,0x204,int);
        int d=lo>(int)key?lo-(int)key:((int)key>hi?(int)key-hi:0);
        if(d<distance) distance=d;
    }
    for (h=head;h;h=GET(h,0x240,void*)) {
        int lo=GET(h,0x200,int),hi=GET(h,0x204,int),layer=GET(h,0x218,int);
        int d=lo>(int)key?lo-(int)key:((int)key>hi?(int)key-hi:0);
        if(d==distance && GET(h,0x238+p,b15_u8) && layer>=0 && layer<16 && layer>top) top=layer;
    }
    return top;
}
static int resolve(void *unused,unsigned p,unsigned key,int target) {
    void *g,*h; const char *path; int layer;
    (void)unused;
    lock();
    g=GET(RT->loop,0x2000+8*p,void*);
    if (!g) { unlock();return 0; }
    if (target==B15_HIGHEST) target=highest(g,p,key);
    if (target<0) { unlock();return 0; }
    h=find(g,p,key,target);
    if (!h) { unlock();return 0; }
    layer=GET(h,0x218,int);
    if (layer<0 || layer>=16) { unlock();return 0; }
    GET(RT->loop,0x1fb8+8*p,void*)=h;
    path=FN(0x36180,const char*(*)(void*))(g);
    unlock();
    FN(0x3ed50,void(*)(const char*,void*,int,int))(path,h,p>>1,p&1);
    return layer+1;
}
/* Display feedback is a contiguous three-message frame. No parameter writes. */
static void publish(void *unused,unsigned p,unsigned epoch,unsigned actual) {
    (void)unused;
    if (RT->core.pair[p].bulk || RT->core.pair[p].prepared) return;
    send(0x4058,epoch&65535);send(0x4059,epoch>>16);
    send(0x404a,(p<<7)|actual);
}
static struct b15_io io(void) { return (struct b15_io){0,resolve,publish}; }
static void init(void *loop) {
    if (RT->magic!=0xb1500002u) {
        b15_init(&RT->core); RT->group_mask=0;RT->magic=0xb1500002u;
    }
    RT->loop=loop;
}
/* Return1 means dispatched; return0 means run the stock handler, then after(). */
int b15_qnx_before(void *loop,unsigned cmd,unsigned data) {
    struct b15_io i; unsigned p,n,e,id,bank;
    init(loop);i=io(); data&=65535;
    p=(data>>7)&3; n=data&127;e=data>>9;
    switch(cmd) {
    case 0x4048: b15_prepare(&RT->core,p,n,e);return 1;
    case 0x4049:
        /* Rejected capture packets must not rewrite the new context's key. */
        if (!RT->core.pair[p].prepared || RT->core.pair[p].tag!=e || RT->core.pair[p].bulk) return 1;
        lock();set(p,id_for(p,0x14),n);unlock();
        b15_commit(&RT->core,&i,p,n,e);return 1;
    case 0x404f:
    case 0x4050:
        for(p=0;p<4;p++) if(data&(1u<<p)) {
            e=RT->core.pair[p].epoch;
            if(cmd==0x404f) b15_context_begin(&RT->core,p,e);
            else b15_context_end(&RT->core,&i,p,e);
        }
        return 1;
    case 0x4057: /* Refresh only; never resolves/reloads or changes parameters. */
        for(p=0;p<4;p++) if(data&(1u<<p))
            publish(0,p,RT->core.pair[p].epoch,RT->core.pair[p].enabled?RT->core.pair[p].actual:0);
        return 1;
    }
    if(cmd>=0x404b && cmd<=0x404e) {
        RT->epoch_low[cmd-0x404b]=(b15_u16)data;return 1;
    }
    if(cmd>=0x4053 && cmd<=0x4056) {
        p=cmd-0x4053;RT->core.pair[p].epoch=((b15_u32)data<<16)|RT->epoch_low[p];return 1;
    }
    id=cmd&0x7ff;bank=(cmd>>11)&1;
    if(cmd>0x9b6 || id>0x1b6) return 0;
    p=bank*2+(id>=0x41); /* only use after testing the instrument-local IDs below */
    if(id==0x14 || id==0x55) {
        lock();set(p,id,data&127);unlock();
        b15_key(&RT->core,&i,p,data&127);return 1;
    }
    if(id==0x13 || id==0x54) {
        lock();set(p,id,data&127);unlock();
        /* Legacy velocity is stored during replay, but is not a new B15 user edit. */
        return 1;
    }
    if(id==0x1c || id==0x5d) {
        if(data>16) data=16;
        lock();set(p,id,data);unlock();
        b15_absolute(&RT->core,&i,p,data);return 1;
    }
    return 0;
}
void b15_qnx_after(void *loop,unsigned cmd,unsigned data) {
    unsigned id=cmd&0x7ff, bank=(cmd>>11)&1,p;
    struct b15_io i;
    init(loop);i=io();
    if(cmd<=0x9b6 && (id==0x12 || id==0x53)) {
        p=bank*2+(id==0x53);
        b15_enable(&RT->core,&i,p,!!data);
    }
    /* Actual group replacement detour records precisely which cache was cleared. */
    for(p=0;p<4;p++) if(RT->group_mask&(1u<<p)) {
        RT->group_mask&=~(1u<<p);
        b15_group_changed(&RT->core,&i,p);
    }
}
void b15_qnx_group_clear(void *loop,unsigned p) {
    init(loop);
    if(p<4) RT->group_mask|=1u<<p;
}
void b15_qnx_note_attempt(void *loop,unsigned bank,unsigned inst,unsigned key) {
    init(loop);
    if(bank<2 && inst<2 && key<128) b15_note_attempt(&RT->core,bank*2+inst,key);
}
void b15_qnx_note_accepted(void *loop,unsigned bank,unsigned inst,unsigned key,void *h) {
    init(loop);
    if(bank<2 && inst<2 && h) b15_note_accepted(&RT->core,bank*2+inst,key,GET(h,0x218,unsigned));
}

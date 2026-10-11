#pragma once
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
int b5_predict(double phase,float r,i64 endpoint,double loaded_w);
void b5_reset(State *s,u64 owner);
void b5_note_on(State *s,const Key *k,u64 owner);
const Key *b5_begin(State *s,const Key *request);
void b5_read_descriptor(State *s,const Key *k,i64 boundary,int valid);
void b5_loaded(State *s,int offset,int copied,int needed,double pre_w,
                      double phase,double post_w);
void b5_unavailable(State *s);
void b5_render(State *s,float *left,float *right);
void b5_attach(void *scheduler);

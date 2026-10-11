// SPDX-License-Identifier: GPL-2.0-or-later
typedef unsigned long U;
typedef unsigned char B;
typedef struct { unsigned flags; int origin,end,start; } State;
#define I(r,o) (*(int*)((B*)(r)+(o)))
#define P(r,o) (*(void**)((B*)(r)+(o)))
#define ACTIVE(r) (*((B*)(r)+8))
static State *state(void *r) { return (State*)((B*)P(r,0x1a8)+0x500); }
extern U original_read(void*,int,float,void*,void*);
extern U original_update(void*,int);
extern void original_fade(void*,const void*,int,int,int,int,int,int,int,int,int);
extern void *allocate(int);
void *entry_allocate(int n) {
 B *p=allocate(n+16);
 if(p) { State *s=(State*)(p+n);s->flags=0;s->origin=s->end=s->start=0; }
 return p;
}
U entry_read(void *r,int n,float rate,void *aio,void *ready) {
 State *s=state(r);
 /* A seek suppresses new entry correction. Retained splice ownership follows
  * the emitted consumption signature; a seek must not restart its envelope. */
 if(I(r,0x24)!=-1) s->flags&=~1u;
 s->flags=(s->flags&3u)|((unsigned)n<<4)|
   (((s->flags&1)&&!ACTIVE(r)&&I(r,0x24)==-1)?8:0);
 return original_read(r,n,rate,aio,ready);
}
U entry_update(void *r,int used) {
 State *s=state(r);unsigned f=s->flags;
 int end=I(r,0x14),instart=I(r,0x1c),inend=I(r,0x20);
 U result=original_update(r,used);
 if(result||used<=0||used>(int)(f>>4)) return result;
 s->flags=(s->flags&~3u)|1;
 if((f&4)&&ACTIVE(r)&&I(r,0x14)==s->end&&I(r,0x10)==s->start) {
  I(r,0x10)=s->origin;s->flags|=2;
 } else if((f&2)&&ACTIVE(r)&&I(r,0x14)==end&&I(r,0x1c)==instart&&I(r,0x20)==inend) s->flags|=2;
 return result;
}
static int absint(int n) { return n<0?-n:n; }
void entry_fade(B *d,const B *src,int start,int end,int cur,int last,int ping,int w,int channels,int en,int mode,void *r,U site) {
 State *s=state(r);int dir=end>start?1:-1,n=absint(last-cur);
 int retained=site==0x3fd79||site==0x41390;
 int fresh=!retained&&(s->flags&8)&&!ping&&en&&d==(B*)P(r,0xb8)&&
   (cur-start)*dir>0&&(end-cur)*dir>0;
 if(fresh) {s->origin=cur;s->end=end;s->start=start;s->flags|=4;}
 if(!fresh&&!(retained&&(s->flags&2))) {
  original_fade(d,src,start,end,cur,last,ping,w,channels,en,mode);return;
 }
 int origin=fresh?cur:start,N=absint(end-origin),k=absint(cur-origin),width=w*channels;
 if(N<=1) return;
 int count=N-1-k;if(count>n)count=n;
 if(count>0) original_fade(d,src,origin,end-dir,cur,cur+dir*count,ping,w,channels,en,mode);
 int final=N-1-k;
 if(final>=0&&final<n) for(int j=0;j<width;j++)d[final*width+j]=src[final*width+j];
}

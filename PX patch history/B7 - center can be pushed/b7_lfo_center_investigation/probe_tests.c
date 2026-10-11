// SPDX-License-Identifier: GPL-2.0-or-later
/* Executes isolated ELF probe bytes in a host-only memory fixture. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <sys/mman.h>
typedef struct { unsigned char xmm[256]; uint64_t r15,r14,r13,r12,rbp,rbx,r11,r10,r9,r8,rdi,rsi,rdx,rcx,rax,flags; } Context;
extern void fixture_call(void *,const Context *,Context *);
extern int probe_getter(void *);
static unsigned char *image;
static float map[1000],diffs[1000],mods[2][32][93][32];
static unsigned char engine[0x2200],modulation[24],params[16];
static void *slots[2*0x6b7],*vtable[4];
static struct {void **vtable;int value;} settings[2][2];
static int raw[2][2][8];
static float banks[2][2][160];
static uint64_t cases,pushes,bypasses,geometry_checks,abi_cases,retreats,stock_geometry_checks;
static unsigned rng=0x71311;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line %d case %llu: %s\n",__LINE__,(unsigned long long)cases,#x);exit(1);}}while(0)
static unsigned random32(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void ptr(void *p,void *v){memcpy(p,&v,8);}
static void load(const char *p,void *out,size_t n){FILE*f=fopen(p,"rb");CHECK(f);CHECK(fread(out,1,n,f)==n);CHECK(fgetc(f)==EOF);fclose(f);}
static float bounded(float x){return fminf(999,fmaxf(0,x));}
static float eff(int r,float m){volatile float product=m*999.0f;return bounded((float)r+product);}
static float lookup(float t){t=bounded(t);int i=(int)t;volatile float p=(t-i)*diffs[i];return map[i]+p;}
static float stock_map(int r,float m){float result;((void(*)(int,float*,float*))(image+0x18e60))(r,&m,&result);return result;}
static int derive(float start,float center,float end,float size,int n,int mode,float factor,float rate,int *out){
 int a=(int)(start*(n-1)),b=(int)(end*(n-1)),c=(int)(center*(n-1));
 int l;
 if(mode==1){l=(int)((int)(size*(n-1))/factor+0.5f)*factor;if(l<factor)l=factor;}
 else if(mode==2){l=(int)((int)size*(rate>0?rate:1));}
 else l=(int)(size*(n-1));
 if(a>=n-32)a=n-33;if(a<0)a=0;
 if(b<=a+31)b=a+32;if(b>=n)b=n-1;
 if(l<32)l=32;if(l>=b-a)l=b-a;
 if(c<=a)c=a;if(c>b)c=b;
 int ls=(int)(c-l*0.5f);if(ls>b-l)ls=b-l;if(ls<a)ls=a;
 int le=(int)(c+l*0.5f);if(le<ls+l)le=ls+l;if(le>b)le=b;
 out[0]=a;out[1]=b;out[2]=c;out[3]=ls;out[4]=le;out[5]=l;
 return l;
}
static float lane(const Context *c,int n){float f;memcpy(&f,c->xmm+n*16,4);return f;}
static void actual_geometry(float *bank,int n,int mode,int path,int *out){
 unsigned char reader[0x1c0]={0};int idx=1,repeat=-1;float factor=64,rate=0.75f;
 memcpy(reader+0xa0,&n,4);memcpy(reader+0x68,&mode,4);memcpy(reader+0x6c,&factor,4);
 memcpy(reader+0x78,&repeat,4);memcpy(reader+0x1b0,&idx,4);memcpy(reader+0x198,&rate,4);ptr(reader+0x1a8,bank);
 Context in={0},result;in.rdi=(uintptr_t)reader;in.flags=0x202;
 fixture_call(image+(path?0x418c7:0x3f91d),&in,&result);
 if(!path){out[0]=(int)result.r8;out[1]=(int)result.r14;out[2]=(int)lane(&result,2);out[3]=(int)result.r13;out[4]=(int)result.rbx;out[5]=(int)lane(&result,3);}
 else{out[0]=(int)result.r8;out[1]=(int)result.rcx;out[2]=(int)lane(&result,2);out[3]=(int)result.r13;out[4]=(int)result.r9;out[5]=(int)((lane(&result,0)-lane(&result,2))*2);}
 stock_geometry_checks++;
}
static void run(int part,int osc,int voice,int scheduler,int loop,int mode,int r0,int rc,int re,float sm,float cm,float em){
 cases++;mods[scheduler][voice][3+osc][0]=sm;mods[scheduler][voice][9+osc][0]=cm;mods[scheduler][voice][5+osc][0]=em;
 mods[scheduler][voice][9+osc][1]=(float)(int)(random32()%2001-1000)/999;
 memcpy(modulation+16,&scheduler,4);settings[part][osc].value=loop;
 int *r=raw[part][osc];r[0]=r0;r[1]=rc;r[2]=713;r[3]=re;r[4]=mode;
 float *bank=banks[part][osc];for(int i=0;i<160;i++)bank[i]=(float)(i+1)*0.001f;
 bank[0]=stock_map(r0,sm);bank[32]=stock_map(rc,cm);bank[33]=stock_map(rc,mods[scheduler][voice][9+osc][1]);bank[96]=stock_map(re,em);
 bank[64]=mode==2?24000:0.137f;
 float before[160],allbanks[2][2][160];memcpy(before,bank,sizeof before);memcpy(allbanks,banks,sizeof banks);
 int rcopy[2][2][8];memcpy(rcopy,raw,sizeof raw);
 unsigned char enginecopy[sizeof engine],modcopy[sizeof mods];memcpy(enginecopy,engine,sizeof engine);memcpy(modcopy,mods,sizeof mods);
 unsigned char frame[0x400];memset(frame,0x5a,sizeof frame);unsigned char *bp=frame+0x300;
 uint64_t object=0x123456789abc00;memcpy(bp-0x220,&object,8);memcpy(bp-0x258,&part,4);
 Context in={0},baseline,actual;
 for(unsigned i=0;i<sizeof in;i++)((unsigned char*)&in)[i]=(unsigned char)(random32());
 in.r15=(uintptr_t)engine;in.r14=voice;in.r13=osc;in.r12=(uintptr_t)r;in.rbp=(uintptr_t)bp;in.rbx=(uintptr_t)bank;in.flags=0x202|(random32()&0x8d5);
 unsigned char expected_hook[12]={0x41,0x83,0xc5,0x01,0x48,0x83,0x85,0xe0,0xfd,0xff,0xff,0x70};
 unsigned char patched_hook[12];memcpy(patched_hook,image+0x1a87b,12);
 memcpy(image+0x1a87b,expected_hook,12);fixture_call(image+0x104f00,&in,&baseline);
 unsigned char expected_frame[sizeof frame];memcpy(expected_frame,frame,sizeof frame);
 memcpy(bp-0x220,&object,8);memcpy(image+0x1a87b,patched_hook,12);fixture_call(image+0x104f00,&in,&actual);
 CHECK(!memcmp(&baseline,&actual,sizeof actual));abi_cases++;
 CHECK(!memcmp(frame,expected_frame,sizeof frame));
 CHECK(!memcmp(raw,rcopy,sizeof raw));CHECK(!memcmp(engine,enginecopy,sizeof engine));CHECK(!memcmp(mods,modcopy,sizeof mods));
 uint64_t changed;memcpy(&changed,bp-0x220,8);CHECK(changed==object+0x70);
 float s=eff(r0,sm),c=eff(rc,cm),e=eff(re,em);
 int push=loop&&cm!=0&&isfinite(cm)&&isfinite(sm)&&isfinite(em)&&s<=e&&(c<s||c>e);
 if(push){
  /* Independent double-precision translation of binary32 effective inputs. */
  double delta=c<s?(double)c-s:(double)c-e;
  double ds=(double)s+delta,de=(double)e+delta;
  CHECK(ds>=-0.0001&&de<=999.0001&&ds<=de);
  CHECK(fabs((de-ds)-((double)e-s))<0.000001);
  float want_s=lookup((float)ds),want_e=lookup((float)de);
  CHECK(fabsf(bank[0]-want_s)<=0.0000003f);CHECK(fabsf(bank[96]-want_e)<=0.0000003f);
  CHECK(c<s?bank[0]==bank[32]:bank[96]==bank[32]);
  pushes++;
 }else{CHECK(!memcmp(before,bank,sizeof before));bypasses++;}
 for(int i=0;i<160;i++)if(i!=0&&i!=96)CHECK(!memcmp(bank+i,before+i,4));
 for(int p=0;p<2;p++)for(int o=0;o<2;o++)if(p!=part||o!=osc)CHECK(!memcmp(banks[p][o],allbanks[p][o],sizeof before));
 CHECK((bank[32]<=bank[33])==(before[32]<=before[33]));
 for(int nidx=0;nidx<5;nidx++){
  int sizes[]={17,33,64,48001,192001};int n=sizes[nidx],g[6],ref[6];
  derive(bank[0],bank[32],bank[96],bank[64],n,mode,64,0.75f,g);
  for(int path=0;path<2;path++){
   int actual[6];actual_geometry(bank,n,mode,path,actual);
   for(int j=0;j<6;j++)CHECK(actual[j]==g[j]);
  }
  float es=before[0],ee=before[96];
  if(push){double delta=c<s?(double)c-s:(double)c-e;es=lookup((float)((double)s+delta));ee=lookup((float)((double)e+delta));}
  derive(es,before[32],ee,before[64],n,mode,64,0.75f,ref);
  /* Float cancellation may move frame truncation by one at a boundary. */
  for(int i=0;i<6;i++)CHECK(abs(g[i]-ref[i])<=1);
  if(n>=33){CHECK(g[0]>=0&&g[1]<n&&g[0]<=g[1]);CHECK(g[3]>=g[0]&&g[4]<=g[1]);}
  geometry_checks++;
 }
}
int main(int argc,char **argv){
 CHECK(argc==5);size_t payload_size=strtoul(argv[3],0,0);uintptr_t thunk=strtoul(argv[4],0,0);
 image=mmap(0,0x300000,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_ANON|MAP_PRIVATE,-1,0);CHECK(image!=MAP_FAILED);
 FILE*f=fopen(argv[1],"rb");CHECK(f);unsigned char b[0x110000];size_t count=fread(b,1,sizeof b,f);fclose(f);CHECK(count<sizeof b);
 /* Exact ELF file-backed PT_LOAD mappings. */
 uint64_t phoff;uint16_t phnum,phsize;memcpy(&phoff,b+32,8);memcpy(&phnum,b+56,2);memcpy(&phsize,b+54,2);
 for(int i=0;i<phnum;i++){unsigned char*p=b+phoff+i*phsize;uint32_t type;uint64_t off,va,size;memcpy(&type,p,4);memcpy(&off,p+8,8);memcpy(&va,p+16,8);memcpy(&size,p+32,8);if(type==1){CHECK(off+size<=count&&va+size<=0x300000);memcpy(image+va,b+off,size);}}
 load(argv[2],image+0x100f60,payload_size);
 image[0x1a87b]=0xe9;int32_t jump=(int32_t)(thunk-0x1a880);memcpy(image+0x1a87c,&jump,4);memset(image+0x1a880,0x90,7);
 /* Host-only entry normalizes a CALL to the original JMP site's rsp alignment. */
 unsigned char entry[]={0x48,0x8d,0x64,0x24,0xf8,0xe9,0,0,0,0};jump=0x1a87b-(0x104f00+10);memcpy(entry+6,&jump,4);memcpy(image+0x104f00,entry,10);
 unsigned char exit_stub[]={0x48,0x8d,0x64,0x24,0x08,0xc3};memcpy(image+0x1a887,exit_stub,6);
 /* Host-only stock geometry exit points, after complete loop-edge fitting.
    Read's stack output A is copied into r8d; UpdateLoc already leaves it there. */
 unsigned char read_exit[]={0x44,0x8b,0x44,0x24,0x24,0xc3};memcpy(image+0x104f20,read_exit,6);
 image[0x3fb18]=0xe9;jump=0x104f20-0x3fb1d;memcpy(image+0x3fb19,&jump,4);image[0x41a9b]=0xc3;
 for(int i=0;i<1000;i++)map[i]=i?(powf(1.005f,i)-1)*0.00690389844f:0;
 for(int i=0;i<999;i++)diffs[i]=map[i+1]-map[i];diffs[999]=0;
 ptr(image+0x2a5188,map);ptr(image+0x2a5180,diffs);
 ptr(engine+0x2a0,modulation);ptr(engine+0x20c0,params);ptr(modulation,mods);int stride=0x6b7;memcpy(params,&stride,4);ptr(params+8,slots);vtable[3]=(void*)probe_getter;
 for(int p=0;p<2;p++)for(int o=0;o<2;o++){settings[p][o].vtable=vtable;slots[p*stride+5+o*0x41]=&settings[p][o];}
 for(int p=0;p<2;p++)for(int o=0;o<2;o++)for(int mode=0;mode<3;mode++)for(int sch=0;sch<2;sch++){
  float sequence[]={0,-0.5f,-0.1f,0,0.5f,0.1f,0};
  for(unsigned i=0;i<sizeof sequence/sizeof *sequence;i++)run(p,o,p+o*2,sch,1,mode,200,450,600,0,sequence[i],0);retreats++;
  for(int cidx=0;cidx<7;cidx++)for(int l=0;l<2;l++)for(int smi=0;smi<3;smi++)for(int emi=0;emi<3;emi++){
   float cs[]={-2,-0.5f,-0.25025025f,0,0.15015015f,0.5f,2};float ms[]={-0.3f,0,0.3f};
   run(p,o,7,sch,l,mode,200,450,600,ms[smi],cs[cidx],ms[emi]);
  }
  run(p,o,0,sch,1,mode,600,450,200,0,0.2f,0);
  run(p,o,31,sch,1,mode,499,499,499,0,-1,0);
  run(p,o,31,sch,1,mode,499,499,499,0,1,0);
  run(p,o,1,sch,1,mode,0,499,999,0,-0.0f,0);
  /* Equality at rails with nonzero modulation, exact float equality. */
  run(p,o,1,sch,1,mode,0,499,999,0,-2,0);run(p,o,1,sch,1,mode,0,499,999,0,2,0);
  run(p,o,1,sch,1,mode,200,450,600,0,NAN,0);
  run(p,o,1,sch,1,mode,200,450,600,INFINITY,0.5f,0);
  run(p,o,2,sch,1,mode,200,200,900,0.5f,0.5f,0); /* c==s, nonzero Center mod */
  run(p,o,2,sch,1,mode,0,600,600,0,-0.5f,-0.5f); /* c==e */
  run(p,o,2,sch,1,mode,200,200,900,0.5f,nextafterf(0.5f,0),0);
  run(p,o,2,sch,1,mode,0,600,600,0,nextafterf(-0.5f,0),-0.5f);
  run(p,o,2,sch,1,mode,200,450,600,0,-2,0);CHECK(banks[p][o][0]==lookup(0)&&banks[p][o][96]==lookup(400));
  run(p,o,2,sch,1,mode,200,450,600,0,2,0);CHECK(banks[p][o][0]==lookup(599)&&banks[p][o][96]==lookup(999));
 }
 for(int i=0;i<40000;i++){
  int p=random32()%2,o=random32()%2,mode=random32()%3,sch=random32()%2,voice=random32()%32;
  int a=random32()%1000,c=random32()%1000,e=random32()%1000;
  float sm=(float)((int)(random32()%4001)-2000)/1000,cm=(float)((int)(random32()%4001)-2000)/1000,em=(float)((int)(random32()%4001)-2000)/1000;
  run(p,o,voice,sch,random32()%2,mode,a,c,e,sm,cm,em);
 }
 printf("{\"status\":\"PASS\",\"cases\":%llu,\"pushes\":%llu,\"bypasses\":%llu,\"geometry_model_checks\":%llu,\"actual_stock_geometry_checks\":%llu,\"ABI_comparisons\":%llu,\"retreat_sequences\":%llu}\n",cases,pushes,bypasses,geometry_checks,stock_geometry_checks,abi_cases,retreats);
}

// SPDX-License-Identifier: GPL-2.0-or-later
// Execute actual baseline/candidate ELF mapper bytes under isolated mappings.
// Only harness mappings receive a RET at the duration-conversion boundary.
#include <sys/mman.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>
#include <fstream>
#include <cmath>
#include <limits>
#include <algorithm>
struct EH {unsigned char id[16];uint16_t type,machine;uint32_t ver;uint64_t entry,phoff,shoff;uint32_t flags;uint16_t ehsize,phentsize,phnum,shentsize,shnum,shstr;};
struct PH {uint32_t type,flags;uint64_t off,va,pa,fs,ms,align;};
extern "C" float run_mapper(void*,int,float,void*,void*,void*);
std::vector<unsigned char> read(const char*p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
unsigned char* load(const char*p){auto b=read(p);auto*h=(EH*)b.data();auto*m=(unsigned char*)mmap(nullptr,0x400000,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANON,-1,0);if(m==MAP_FAILED)abort();for(int i=0;i<h->phnum;i++){auto*s=(PH*)(b.data()+h->phoff+i*h->phentsize);if(s->type==1){if(s->va+s->ms>0x400000)abort();memcpy(m+s->va,b.data()+s->off,s->fs);}}
 ((void(*)())(m+0x7bf0))(); // unchanged original initialization tail, no external calls
 auto*t=(float*)(m+0x2a5140);auto*d=(float*)(m+0x2a5100);for(int i=0;i<15;i++)d[i]=t[i+1]-t[i];d[15]=0;
 m[0x1aea6]=0xc3;return m;}
uint32_t bits(float f){uint32_t u;memcpy(&u,&f,4);return u;}
float call(unsigned char*m,int raw,float mod){alignas(16) unsigned char param[64]={},frame[1024]={},obj[0x2100]={};return run_mapper(m+0x1ae55,raw,mod,param,frame,obj);}
float expected(unsigned char*m,int r,float mod){float*t=(float*)(m+0x2a5140);float v=(float)(15-r)+15.0f*mod;if(!(v>=0)){float a,b;if(v>=-1.0f){a=v+1.0f;b=t[0]*0.5f;}else{a=v+2.0f;b=t[0]*0.25f;}if(!(a>0))a=0;return b+a*b;}if(v>=15)return t[15];int i=(int)v;float f=v-(float)i;return t[i]+f*(t[i+1]-t[i]);}
int main(int argc,char**argv){if(argc!=3)return 2;auto*a=load(argv[1]);auto*b=load(argv[2]);auto*t=(float*)(a+0x2a5140);if(t[0]!=720000.f){fprintf(stderr,"Unexpected S0: %g\n",t[0]);return 3;}
 std::vector<float> mods;for(int i=-16384;i<=16384;i++)mods.push_back((float)i/16384.f);mods.push_back(INFINITY);mods.push_back(-INFINITY);mods.push_back(NAN);mods.push_back(-0.f);for(float boundary:{-2.f,-1.f,0.f,15.f})for(int r:{16,17}){float m=(boundary-(15-r))/15.f;mods.push_back(m);mods.push_back(std::nextafter(m,-INFINITY));mods.push_back(std::nextafter(m,INFINITY));}
 uint64_t oldcases=0,newcases=0;for(int r=0;r<16;r++)for(float m:mods){float x=call(a,r,m),y=call(b,r,m);if(bits(x)!=bits(y)){fprintf(stderr,"OLD mismatch r=%d m=%a baseline=%a candidate=%a\n",r,m,x,y);return 4;}oldcases++;}
 for(int r:{16,17})for(float m:mods){float x=call(b,r,m),y=expected(b,r,m);if(bits(x)!=bits(y)){fprintf(stderr,"NEW mismatch r=%d m=%a actual=%a expected=%a\n",r,m,x,y);return 5;}newcases++;}
 for(int r:{16,17}){float duration=call(b,r,0);float want=720000.f/(r==16?2.f:4.f);if(duration!=want)return 6;for(float bpm:{30.f,60.f,120.f,240.f}){float frames=duration/bpm;float seconds=frames/48000.f;float beats=seconds*bpm/60.f;float target=r==16?0.125f:0.0625f;if(std::fabs(beats-target)>1e-6f)return 7;}}
 // Preserve the runtime table scale: sample-rate changes alter S0, not the helper constants.
 for(float scale:{0.5f,0.91875f,2.f}){for(int i=0;i<16;i++)((float*)(b+0x2a5140))[i]=t[i]*scale;auto*bt=(float*)(b+0x2a5140);auto*bd=(float*)(b+0x2a5100);for(int i=0;i<15;i++)bd[i]=bt[i+1]-bt[i];bd[15]=0;for(int r:{16,17})for(float m:{-1.f,0.f,0.01f,0.1f,1.f})if(bits(call(b,r,m))!=bits(expected(b,r,m)))return 8;}
 printf("{\"status\":\"PASS\",\"execution\":\"actual ELF mapper and helper instructions via x86_64 host harness (Rosetta)\",\"legacy_bit_exact_cases\":%llu,\"new_mapping_bit_exact_cases\":%llu,\"new_zero_modulation_BPM_cases\":8,\"runtime_S0_scale_cases\":30,\"hardware\":\"NOT VERIFIED\"}\n",oldcases,newcases);}

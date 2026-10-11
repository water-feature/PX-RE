// SPDX-License-Identifier: GPL-2.0-or-later
#define main inherited_test_main
#include "inherited_fixture.c"
#undef main
static void rate_case(float request,int expected){
 init();prepare(1);
 read_batch(reader[0],1000,9000,0,96,0,0);publish(reader[0],audio,96);
 /* Seed a later source batch 100 frames from selected endpoint. */
 b->published_boundary=100;
 endpoints(reader[0],.1f,.9f);prepare(request);
 *(double *)(left+8)=7900;*(double *)(left+16)=7900;
 actual_load(0,33,96);
 CHECK(s->d.endpoint_valid && s->d.endpoint==8000);

 unsigned char cf[256]={0};INT(cf+8,0x28)=1;
 for(int j=0;j<32;j++){workL[j]=1;workR[j]=-.5f;}
 Capture c=context();c.rbx=(uintptr_t)work;dispatch(&c,FILTER|128,cf);

 CHECK((int)s->d.has_fade==expected);
}
static void modulation_sequence(void){
 init();prepare(1);read_batch(reader[0],1000,9000,0,96,0,0);publish(reader[0],audio,96);b->published_boundary=100;
 float first=1.000001f;float previous=1;
 for(int block=0;block<3;block++){
  float requested=first+block*.000001f;
  endpoints(reader[0],.1f,.9f);prepare(requested);
  if(FIXED && block)CHECK(U32(frame,0x14)==bits(first) && s->d.has_pending);
  *(double *)(left+8)=7900+block*32*(double)first;*(double *)(left+16)=7900+block*32;
  actual_load(0,33,96);
  unsigned char cf[256]={0};INT(cf+8,0x28)=2;
  /* Both real resampler snapshots have matching clocks/rate after generation. */
  U32(left,0)=U32(right,0)=bits(FIXED?first:requested);
  *(double *)(right+8)=*(double *)(left+8);*(double *)(right+16)=*(double *)(left+16);
  for(int j=0;j<32;j++){workL[j]=1;workR[j]=-.5f;}
  Capture c=context();c.rbx=(uintptr_t)work;dispatch(&c,FILTER|128,cf);
  CHECK((int)s->d.has_fade==FIXED);
  for(int j=0;j<32;j++){
   CHECK(workR[j]==-.5f*workL[j]);
   if(FIXED){CHECK(workL[j]<=previous && workL[j]>=0);previous=workL[j];}
   else CHECK(workL[j]==1);
  }
 }
}
static void identity_checks(void){
 for(int field=0;field<4;field++){
  init();s->d.endpoint_valid=1;s->d.endpoint=8000;s->d.phase=7900;s->d.write=7933;
  if(field==0)s->d.timeline_key.a++;
  if(field==1)s->d.timeline_key.b++;
  if(field==2)s->d.timeline_key.reverse=1;
  if(field==3)s->d.timeline_key.loop=1;
  FN(b5_render,void(*)(State*,float*,float*))(s,workL,workR);CHECK(!s->d.has_fade);
 }
}
int main(void){
 rate_case(1.f,1);rate_case(1.000001f,FIXED);rate_case(.999999f,FIXED);
 for(int i=1;i<=32;i++){
  FloatBits up={.u=bits(1.f)+(u32)i},down={.u=bits(1.f)-(u32)i};
  rate_case(up.f,FIXED);rate_case(down.f,FIXED);
 }
 modulation_sequence();identity_checks();hold_tests();swap_tests();identity_tests();geometry_tests();mode_tests();ramp_boundary_tests();stereo_tests();
 printf("PASS %u checks, %u inherited groups, FIXED=%d; modeled reader/control dependencies\n",checks,groups,FIXED);return 0;
}

#define main inherited_test_main
#include "inherited_fixture.c"
#undef main
static void output_block(void){
 unsigned char cf[256]={0};INT(cf+8,0x28)=2;
 U32(right,0)=U32(left,0);*(double *)(right+8)=*(double *)(left+8);*(double *)(right+16)=*(double *)(left+16);
 for(int j=0;j<32;j++){workL[j]=1;workR[j]=-.5f;}
 Capture c=context();c.rbx=(uintptr_t)work;dispatch(&c,FILTER|128,cf);
}
static void completion(float next,int drifting){
 init();prepare(1);read_batch(reader[0],1000,9000,0,256,0,0);publish(reader[0],audio,256);b->published_boundary=100;
 *(double *)(left+8)=7900;*(double *)(left+16)=7900;actual_load(0,33,256);
 CHECK(s->d.endpoint_valid && s->d.endpoint==8000);
 output_block();CHECK(s->d.has_fade);int offset=33;u64 end=s->d.end;CHECK(end==96);
 while(s->d.clock<end){
  endpoints(reader[0],.1f,.9f);prepare(drifting?next:1);CHECK(s->d.has_fade);*(double *)(left+8)+=32;actual_load(offset,32,256-offset);offset+=32;output_block();
 }
 float last=workL[31];CHECK(last>0&&last<.02f);
 /* The resampler is still before its source endpoint: the deliberately early
  * fade finishes on the preceding 32-frame boundary. */
 *(double *)(left+8)+=32;actual_load(offset,32,256-offset);
 CHECK(*(double *)(left+8)<s->d.endpoint);
 endpoints(reader[0],.1f,.9f);prepare(next);int held=s->d.has_fade;output_block();
 printf("drifting=%d next_rate=%.9g completed=%llu phase=%.0f endpoint=%lld fade_after_prepare=%d last_ramp=%.9g next_first=%.9g no_opportunity=%u\n",drifting,next,end,*(double *)(left+8),s->d.endpoint,held,last,workL[0],s->d.no_opportunity);
 if(next==1){CHECK(held);CHECK(workL[0]==0&&workR[0]==0);}
 else {CHECK(!held);CHECK(workL[0]==1&&workR[0]==-.5f);}
}
int main(void){for(int drift=0;drift<2;drift++){completion(1,drift);completion(1.000001f,drift);completion(.999999f,drift);}printf("PASS %u checks: completed-fade rate-change regression reproduced; stock audio/loader modeled, hardware NOT VERIFIED\n",checks);}

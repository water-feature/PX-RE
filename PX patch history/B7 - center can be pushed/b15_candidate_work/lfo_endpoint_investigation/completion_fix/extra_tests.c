// SPDX-License-Identifier: GPL-2.0-or-later
static void geom_observe(float rate,int field){
 Capture c=context();dispatch(&c,READ,frame);
 U32(reader[0],0x198+4*((U32(reader[0],0x1b0)+1)&1))=bits(rate);
 unsigned char rf[176]={0};PTR(rf,168)=b5_image+OFF_b5_read_original_return;
 INT(rf,0x24)=1000+(field==1);INT(rf,0x10)=9000+(field==2);rf[0x1c]=field==3;
 INT(reader[0],0x58)=field==4;dispatch(&c,GEOM,rf);
}
static void geom_tests(void){
 for(int field=0;field<5;field++)for(int time=0;time<3;time++){
  init();s->d.has_fade=1;s->d.start=0;s->d.end=96;s->d.clock=time==0?0:time==1?32:96;
  if(field==4)INT(reader[0],0x28)=1;prepare(1);geom_observe(1.000001f,field);
  int retained=field==0 && time==2 && FIXED;
  /* Observed rate mismatches before completion retain original cancellation. */
  if(field==4){CHECK(!s->d.has_fade);/* mode change cancelled at PREPARE */}
  else CHECK((int)s->d.has_fade==retained);
  if(field!=4)CHECK(s->d.effective.rate_bits==bits(1.000001f));
  if(retained){output_block();CHECK(workL[0]==0&&workR[31]==0);}
 }
}
static void core_tests(void){
 for(int field=0;field<5;field++){
  init();s->d.has_fade=1;s->d.clock=s->d.end=96;s->d.start=0;
  Key k=s->d.effective;k.rate_bits=bits(1.000001f);
  if(field==1)k.a++;if(field==2)k.b++;if(field==3)k.reverse=1;if(field==4)k.loop=1;
  FN(b5_begin,const Key*(*)(State*,const Key*))(s,&k);
  CHECK((int)s->d.has_fade==(FIXED&&field==0));CHECK(s->d.effective.rate_bits==k.rate_bits);
 }
 init();prepare(1.000001f);CHECK(!s->d.has_fade&&s->d.effective.rate_bits==bits(1.000001f));
 init();s->d.has_fade=1;s->d.start=0;s->d.end=96;s->d.clock=32;prepare(1.000001f);
 CHECK(s->d.has_fade&&s->d.has_pending&&s->d.effective.rate_bits==bits(1));CHECK(U32(frame,0x14)==bits(1));
 for(int rep=0;rep<4;rep++){
  init();s->d.has_fade=1;s->d.clock=s->d.end=96;Capture c=context();c.rbp=(uintptr_t)osc;dispatch(&c,NOTE,frame);
  CHECK(!s->d.has_fade&&!s->d.has_pending&&s->d.clock==0);CHECK(s->d.epoch==1);
  s->d.has_fade=1;c=context();c.rdi=(uintptr_t)scheduler;dispatch(&c,RESET,frame);CHECK(!s->d.has_fade&&s->d.clock==0);
 }
 /* Tiny-region eligibility and 5ms maximum are unchanged. */
 for(int length=32;length<=241;length++){
  init();s->d.effective.b=s->d.effective.a+length;s->d.has_fade=1;s->d.start=0;s->d.end=240;output_block();
  CHECK((int)s->d.has_fade==(length>240));CHECK(s->d.end==240);
 }
}
#define B8_OFFSET (1015808-987136)
static void b8(Capture *c,unsigned event){FN(b5_predict,void(*)(Capture*,unsigned,unsigned char*));((void(*)(Capture*,unsigned,unsigned char*))(b5_image+B8_OFFSET))(c,event,frame);}
static void b8_tests(void){
 init();prepare(1);read_batch(reader[0],1000,9000,0,96,0,0);publish(reader[0],audio,96);
 unsigned char dirty[8]={0};PTR(scheduler,0x18)=dirty;
 b->published_boundary=64;INT(pool,0x18)=96;INT(pool,0x24)=64;
 s->d.has_fade=1;s->d.start=0;s->d.end=s->d.clock=96;
 Capture c=context();b8(&c,0);CHECK(reader[0][0x1c0]==3);CHECK(s->d.has_fade);
 endpoints(reader[0],.1f,.9f);prepare(1.000001f);CHECK((int)s->d.has_fade==FIXED);
 /* B8 unavailable-return restoration must still retain terminal silence. */
 s->d.has_fade=0;b8(&c,5);CHECK(s->d.has_fade);output_block();CHECK(workL[0]==0&&workR[31]==0);
 /* Successful Open of replacement after completion resets the B5 note. */
 unsigned char extended[sizeof(Capture)+8]={0};Capture *ec=(Capture *)extended;ec->rbp=(uintptr_t)scheduler;ec->rax=0;
 *(u64 *)(extended+sizeof(Capture))=(uintptr_t)reader[1];reader[1][0x1c0]=3;U32(frame,0x28)=0;b8(ec,131);
 CHECK(!reader[1][0x1c0]);CHECK(!s->d.has_fade&&s->d.clock==0);
}
int main(void){
 for(test_slot=0;test_slot<2;test_slot++)for(test_channels=1;test_channels<=2;test_channels++)for(test_reverse=0;test_reverse<2;test_reverse++)for(int drift=0;drift<2;drift++){completion(1,drift);completion(1.000001f,drift);completion(.999999f,drift);}
 test_slot=0;test_channels=2;test_reverse=0;
 fprintf(stderr,"core\n");core_tests();fprintf(stderr,"geom\n");geom_tests();fprintf(stderr,"b8\n");b8_tests();fprintf(stderr,"inherited\n");
 hold_tests();swap_tests();identity_tests();geometry_tests();mode_tests();ramp_boundary_tests();stereo_tests();fprintf(stderr,"wrappers\n");wrapper_tests();owned_wrapper_tests();
 printf("PASS %u checks; completion/core/GEOM/B8/lifecycle/tiny regions plus %u inherited groups, FIXED=%d; stock dependencies modeled\n",checks,groups,FIXED);
}

// SPDX-License-Identifier: GPL-2.0-or-later
#define B15_PAIR_TEST
#define main b15_adapter_selftest
#include "test_absolute_qnx_adapter.c"
#undef main
void b15_pair_init(void) {
 unsigned p,k,counts[]={3,4,6,8};
 memset(loop,0,sizeof loop);memset(group,0,sizeof group);memset(handlers,0,sizeof handlers);memset(b15_test_runtime,0,sizeof b15_test_runtime);
 mutex_depth=reloads=mirrors=statuses=frame_phase=0;
 for(p=0;p<4;p++) {
  AT(loop,0x2000+8*p,void*)=group[p];AT(group[p],0x680,void*)=handlers[p][0];
  for(k=0;k<16;k++) {
   void*h=handlers[p][k];AT(h,0x204,int)=127;AT(h,0x218,int)=k;
   AT(h,0x238+p,unsigned char)=k<counts[p];AT(h,0x240,void*)=k==15?0:handlers[p][k+1];
  }
 }
}
void b15_pair_command(unsigned cmd,unsigned data) {
 if(!b15_qnx_before(loop,cmd,data))b15_qnx_after(loop,cmd,data);
}
void b15_pair_note(unsigned p,unsigned key,unsigned layer) {
 b15_qnx_note_attempt(loop,p>>1,p&1,key);
 b15_qnx_note_accepted(loop,p>>1,p&1,key,handlers[p][layer-1]);
}
unsigned b15_pair_value(unsigned p,unsigned which) {
 struct b15_pair*r=&core()->pair[p];
 switch(which){case 0:return r->actual;case 1:return r->target;case 2:return r->key;case 3:return r->epoch;case 4:return r->bulk;case 5:return r->enabled;case 8:return r->prepared;case 9:return r->snapshot;case 6:return params[p>>1][0x1c+(p&1)*0x41];default:return reloads;}
}

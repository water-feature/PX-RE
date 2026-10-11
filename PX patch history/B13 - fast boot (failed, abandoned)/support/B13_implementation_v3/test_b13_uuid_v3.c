#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#include <sys/types.h>

extern int b13_fast_uuid_v3(void*, char*, char*, void**, char*, char*, float*, char*);
static int fallback_count, open_count, read_count, close_count;
static ssize_t last_read_req, last_read_got;

int b13_open(const char *p, int flags, ...) { open_count++; return open(p, flags); }
ssize_t b13_read(int fd, void *buf, size_t n) { read_count++; last_read_req=n; last_read_got=read(fd,buf,n); return last_read_got; }
int b13_close(int fd) { close_count++; return close(fd); }
static unsigned nib(char c){ if(c>='0'&&c<='9')return c-'0'; if(c>='A'&&c<='F')return c-'A'+10; if(c>='a'&&c<='f')return c-'a'+10; return 0; }
void b13_StrToGUID(char *s, unsigned char *out){ memset(out,0,17); if(!s||!out)return; for(int i=0;i<32 && s[i];i++) out[i/2]|=(unsigned char)(nib(s[i]) << ((i&1)?0:4)); }
int b13_GetGroupFileInfo(void* thiz,char*a,char*b,void**c,char*d,char*e,float*f,char*g){ (void)thiz;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f; fallback_count++; memset(g,0xA5,17); return 77; }

static void reset(void){ fallback_count=open_count=read_count=close_count=0; last_read_req=last_read_got=0; }
static void writef(const char* path,const char* data,size_t n){ int fd=open(path,O_CREAT|O_TRUNC|O_WRONLY,0600); if(fd<0){perror("open test");exit(2);} if(write(fd,data,n)!=(ssize_t)n){perror("write");exit(2);} close(fd); }
static int run(const char* name,const char* data,size_t n,const unsigned char* expect,int expect_rc,int expect_fallback){
 char path[256]; snprintf(path,sizeof path,"/tmp/%s.grp",name); writef(path,data,n); char uuid[17]; memset(uuid,0,17); reset(); int rc=b13_fast_uuid_v3((void*)0x11,path,(char*)"vel",NULL,NULL,NULL,NULL,uuid); int ok=(rc==expect_rc && fallback_count==expect_fallback && (!expect || memcmp(uuid,expect,17)==0));
 printf("%-20s %s rc=%d fb=%d open=%d read=%d close=%d req=%zd got=%zd uuid=",name,ok?"PASS":"FAIL",rc,fallback_count,open_count,read_count,close_count,last_read_req,last_read_got); for(int i=0;i<17;i++)printf("%02x",(unsigned char)uuid[i]); puts(""); unlink(path); return ok?0:1;
}
int main(void){
 unsigned char want[17]={0}; b13_StrToGUID("00112233445566778899AABBCCDDEEFF",want);
 int fail=0;
 const char *m1="File Path\tLow Midi Note\tUUID\r\nfoo.wav\t0\t00112233445566778899AABBCCDDEEFF\r\nsecond\t1\tFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF\r\n";
 fail+=run("normal-crlf",m1,strlen(m1),want,0,0);
 const char *m2="UUID\tFile Path\tInstrument Name\n00112233445566778899AABBCCDDEEFF\tfoo.wav\tGrand Piano\n";
 fail+=run("uuid-first",m2,strlen(m2),want,0,0);
 const char *m3="File Path\t\tUUID\tCategory\nfoo.wav\t\t00112233445566778899AABBCCDDEEFF\tPiano\n";
 fail+=run("empty-columns",m3,strlen(m3),want,0,0);
 const char *m4="File Path\tCategory\nfoo.wav\tPiano\n";
 unsigned char fb[17]; memset(fb,0xA5,17);
 fail+=run("no-uuid-header",m4,strlen(m4),fb,77,1);
 const char *m5="File Path\tUUID\n\n\r\nfoo.wav\t00112233445566778899AABBCCDDEEFF\n";
 fail+=run("blank-lines",m5,strlen(m5),want,0,0);
 char *huge=calloc(1,4000); memset(huge,'X',3000); huge[3000]='\n'; strcpy(huge+3001,"foo\t00112233445566778899AABBCCDDEEFF\n");
 fail+=run("oversize-header",huge,3040,fb,77,1); free(huge);
 const char *m7="File Path\tUUID\nfoo.wav\nbar.wav\t00112233445566778899AABBCCDDEEFF\n";
 fail+=run("missing-first-uuid",m7,strlen(m7),fb,77,1);
 printf("TOTAL %s (%d failures)\n", fail?"FAIL":"PASS",fail); return fail?1:0;
}

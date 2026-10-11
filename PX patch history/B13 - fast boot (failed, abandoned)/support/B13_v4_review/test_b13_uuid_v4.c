#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
extern int b13_fast_uuid_v4(void*,char*,char*,void**,char*,char*,float*,char*);
static int mode,opens,reads,closes,fallbacks,arg_errors;
static char *path_arg,*uuid_arg;
int b13_open(const char*p,int flags,...){opens++;if(strcmp(p,path_arg)||flags!=0)arg_errors++;return mode==1?-1:open(p,flags);}
ssize_t b13_read(int fd,void*b,size_t n){reads++;if(n!=511)arg_errors++;return mode==2?-1:mode==3?0:read(fd,b,n);}
int b13_close(int fd){closes++;return close(fd);}
int b13_GetGroupFileInfo(void*t,char*p,char*v,void**a,char*b,char*c,float*d,char*g){
 fallbacks++;if(t!=(void*)0x11||p!=path_arg||strcmp(v,"velocity")||a||b||c||d||g!=uuid_arg)arg_errors++;
 memset(g,0xa5,17);return 77;
}
static int test(const char*name,const char*data,size_t n,int m,int fallback){
 char path[]="/tmp/b13-v4-XXXXXX",uuid[19];int fd=mkstemp(path);if(fd<0)exit(2);
 if(write(fd,data,n)!=(ssize_t)n)exit(2);close(fd);
 mode=m;opens=reads=closes=fallbacks=arg_errors=0;path_arg=path;uuid_arg=uuid+1;memset(uuid,0x5a,sizeof uuid);
 int rc=b13_fast_uuid_v4((void*)0x11,path,"velocity",NULL,NULL,NULL,NULL,uuid+1);
 int ok=rc==(fallback?77:0)&&fallbacks==fallback&&!arg_errors&&opens==1&&reads==(m==1?0:1)&&closes==(m==1?0:1);
 for(int i=1;i<=17;i++)ok&=(unsigned char)uuid[i]==(fallback?0xa5:0);
 ok&=(unsigned char)uuid[0]==0x5a&&(unsigned char)uuid[18]==0x5a;
 unlink(path);printf("%s %s\n",ok?"PASS":"FAIL",name);return !ok;
}
#define T(name,data,mode,fb) fail+=test(name,data,strlen(data),mode,fb)
int main(void){int fail=0;
 T("no-uuid-cr", "File Path\tUSERFIELD\rfoo\t-1\r",0,0);
 T("no-uuid-crlf", "File Path\tMono Collapse\r\nfoo\tY\r\n",0,0);
 T("empty-columns", "\tFile Path\t\tUSERFIELD\t\nfoo\t-1\n",0,0);
 T("uuid-falls-back", "File Path\tUUID\nfoo\t01\n",0,1);
 T("duplicate-uuid-falls-back", "UUID\tUUID\n00\tff\n",0,1);
 T("exact-token-only", "File Path\tUUIDx\nfoo\t01\n",0,0);
 T("header-only-zero", "File Path\n",0,0);
 T("incomplete-header", "File Path",0,1);
 T("empty-file", "",0,1);
 T("open-failure", "File Path\n",1,1);
 T("read-failure", "File Path\n",2,1);
 T("zero-read", "File Path\n",3,1);
 T("mono-pitch-only", "File Path\tMono Pitch\nfoo\tY\n",0,0);
 T("mono-collapse-only", "File Path\tMono Collapse\nfoo\tY\n",0,0);
 T("both-mono-fields-conservative-fallback", "File Path\tMono Pitch\tMono Collapse\nfoo\tY\tY\n",0,1);
 T("similar-mono-token", "File Path\tMono Pitchx\tMono Collapse\nfoo\tY\tY\n",0,0);
 char boundary[512];memset(boundary,'X',sizeof boundary);boundary[510]='\n';boundary[511]=0;
 fail+=test("complete-at-byte-511",boundary,511,0,0);
 boundary[510]='X';boundary[511]='\n';fail+=test("newline-outside-read",boundary,512,0,1);
 printf("TOTAL: %d failures\n",fail);return fail!=0;
}

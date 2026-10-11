#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <stddef.h>
static void (*converter)(char*,void*);
int fallbacks;
void set_converter(void *p){converter=p;}
int b13_open(const char*p,int f,...){return open(p,f);}
ssize_t b13_read(int fd,void*b,size_t n){return read(fd,b,n);}
int b13_close(int fd){return close(fd);}
void b13_StrToGUID(char*s,void*out){converter(s,out);}
int b13_GetGroupFileInfo(void*t,char*p,char*v,void**a,char*b,char*c,float*d,char*g){fallbacks++;return 77;}

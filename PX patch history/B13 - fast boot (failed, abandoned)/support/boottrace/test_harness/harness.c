#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/mman.h>
#include "addrs.h"

struct regs { uint64_t rax,rbx,rcx,rdx,rsi,rdi,rbp,r8,r9,r10,r11,r12,r13,r14,r15,rsp; uint8_t xmm[8][16]; };
struct regs g_in, g_out;
uint64_t g_fn, g_rsp_before, g_rsp_after;

#define LD(reg,off) "mov " #reg ", QWORD PTR g_in[rip+" #off "]\n"
#define ST(reg,off) "mov QWORD PTR g_out[rip+" #off "], " #reg "\n"
#define LDX(n,off) "movups xmm" #n ", XMMWORD PTR g_in[rip+" #off "]\n"
#define STX(n,off) "movups XMMWORD PTR g_out[rip+" #off "], xmm" #n "\n"
__asm__(
".intel_syntax noprefix\n"
".globl call_target\n"
"call_target:\n"
"push rbp\npush rbx\npush r12\npush r13\npush r14\npush r15\nsub rsp, 8\n"
"mov QWORD PTR g_rsp_before[rip], rsp\n"
LDX(0,128) LDX(1,144) LDX(2,160) LDX(3,176) LDX(4,192) LDX(5,208) LDX(6,224) LDX(7,240)
LD(rbx,8) LD(rcx,16) LD(rdx,24) LD(rsi,32) LD(rdi,40) LD(rbp,48) LD(r8,56) LD(r9,64) LD(r10,72) LD(r11,80)
LD(r12,88) LD(r13,96) LD(r14,104) LD(r15,112) LD(rax,0)
"call QWORD PTR g_fn[rip]\n"
ST(rax,0) ST(rbx,8) ST(rcx,16) ST(rdx,24) ST(rsi,32) ST(rdi,40) ST(rbp,48) ST(r8,56) ST(r9,64) ST(r10,72) ST(r11,80)
ST(r12,88) ST(r13,96) ST(r14,104) ST(r15,112)
"mov QWORD PTR g_rsp_after[rip], rsp\n"
STX(0,128) STX(1,144) STX(2,160) STX(3,176) STX(4,192) STX(5,208) STX(6,224) STX(7,240)
"add rsp, 8\npop r15\npop r14\npop r13\npop r12\npop rbx\npop rbp\nret\n"
".att_syntax prefix\n"
);
extern void call_target(void);

static int fails = 0, checks = 0;
#define CHECK(c, ...) do { checks++; if (!(c)) { fails++; printf("FAIL: "); printf(__VA_ARGS__); printf("\n"); } } while (0)

static uint64_t vtable[4];
static void sentinels(struct regs *r) {
    r->rax=0xA0A0A0A0A0A0A0A0ULL; r->rbx=0xB1B1B1B1B1B1B1B1ULL; r->rcx=0xC2C2C2C2C2C2C2C2ULL;
    r->rdx=0xD3D3D3D3D3D3D3D3ULL; r->rsi=0xE4E4E4E4E4E4E4E4ULL; r->rdi=0xF5F5F5F5F5F5F5F5ULL;
    r->rbp=0x1616161616161616ULL; r->r8=0x2828282828282828ULL; r->r9=0x3939393939393939ULL;
    r->r10=0x4A4A4A4A4A4A4A4AULL; r->r11=0x5B5B5B5B5B5B5B5BULL; r->r12=0x6C6C6C6C6C6C6C6CULL;
    r->r13=0x7D7D7D7D7D7D7D7DULL; r->r14=0x8E8E8E8E8E8E8E8EULL; r->r15=0x9F9F9F9F9F9F9F9FULL;
    for (int i=0;i<8;i++) for (int j=0;j<16;j++) r->xmm[i][j]=(uint8_t)(0x10*(i+1)+j);
}
static void run(uint64_t fn) { g_fn = fn; call_target(); }
static void common_out(const char *n) {
    CHECK(g_rsp_before == g_rsp_after, "%s: rsp changed %llx -> %llx", n, (unsigned long long)g_rsp_before, (unsigned long long)g_rsp_after);
    CHECK(g_out.rbx==g_in.rbx && g_out.rbp==g_in.rbp && g_out.r12==g_in.r12 && g_out.r13==g_in.r13 &&
          g_out.r14==g_in.r14 && g_out.r15==g_in.r15, "%s: callee-saved register changed", n);
    CHECK(*(uint64_t*)A_misalign == 0, "%s: misaligned stack seen by a callee (%llu)", n, (unsigned long long)*(uint64_t*)A_misalign);
}
/* rec layout: [0]=count [8]=rdi [16]=rsi [24]=rdx [32]=rcx [40]=r8 [48]=r9 [56]=rax [64..191]=xmm0-7 */
static void check_target(const char *n, uint64_t rec, uint64_t exp_rdi, uint64_t exp_rax) {
    uint64_t *r = (uint64_t*)rec;
    CHECK(r[0]==1, "%s: original target called %llu times (want 1)", n, (unsigned long long)r[0]);
    CHECK(r[1]==exp_rdi, "%s: rdi at target %llx want %llx", n, (unsigned long long)r[1], (unsigned long long)exp_rdi);
    CHECK(r[2]==g_in.rsi, "%s: rsi at target changed", n);
    CHECK(r[3]==g_in.rdx, "%s: rdx at target changed", n);
    CHECK(r[4]==g_in.rcx, "%s: rcx at target changed", n);
    CHECK(r[5]==g_in.r8,  "%s: r8 at target changed", n);
    CHECK(r[6]==g_in.r9,  "%s: r9 at target changed", n);
    CHECK(r[7]==exp_rax,  "%s: rax at target %llx want %llx", n, (unsigned long long)r[7], (unsigned long long)exp_rax);
    CHECK(memcmp((uint8_t*)rec+64, g_in.xmm, 128)==0, "%s: xmm0-7 at target changed", n);
    CHECK(g_out.rax==0x1122334455667788ULL, "%s: return rax not preserved: %llx", n, (unsigned long long)g_out.rax);
    CHECK(g_out.rdx==0x0102030405060708ULL, "%s: return rdx not preserved: %llx", n, (unsigned long long)g_out.rdx);
    uint64_t x0 = *(uint64_t*)g_out.xmm[0];
    CHECK(x0==0x7777777777777777ULL, "%s: return xmm0 not preserved: %llx", n, (unsigned long long)x0);
}

int main(void) {
    if (mmap((void*)0x10000000, 0x10000, PROT_READ|PROT_WRITE|PROT_EXEC, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0) == MAP_FAILED) { perror("mmap code"); return 2; }
    if (mmap((void*)0x10100000, 0x1000, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0) == MAP_FAILED) { perror("mmap ts"); return 2; }
    if (mmap((void*)0x10200000, 0x10000, PROT_READ|PROT_WRITE|PROT_EXEC, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0) == MAP_FAILED) { perror("mmap stubs"); return 2; }
    FILE *f = fopen("trace_code.bin","rb"); size_t n = fread((void*)0x10000000,1,0x10000,f); fclose(f); printf("loaded %zu code bytes\n", n);
    f = fopen("stubs.bin","rb"); n = fread((void*)0x10200000,1,0x10000,f); fclose(f);
    unlink("out_trace.bin");
    *(uint32_t*)A_errno_var = 77;
    vtable[0]=A_vt0; vtable[1]=A_vt8; vtable[2]=A_vt10;

    struct { const char *name; uint64_t fn; uint64_t rec; int viaVt; } t[] = {
        {"w_main (tail)",   F_w_main,       A_rec_procmgr, 0},
        {"w_serial_beg",    F_w_serial_beg, A_rec_comopen, 0},
        {"w_serial_end",    F_w_serial_end, A_rec_comrts,  0},
        {"w_ctor",          F_w_ctor,       A_rec_ctor,    0},
        {"w_index",         F_w_index,      A_rec_index,   0},
        {"w_cache_beg",     F_w_cache_beg,  A_rec_cacheinfo,0},
        {"w_preload",       F_w_preload,    A_rec_preload, 0},
        {"w_select_end",    F_w_select_end, A_rec_newarr,  0},
        {"w_fpga_open",     F_w_fpga_open,  A_rec_vt0,     1},
        {"w_sched",         F_w_sched,      A_rec_vt8,     2},
        {"w_workers",       F_w_workers,    A_rec_workers, 0},
        {"w_stream",        F_w_stream,     A_rec_vt10,    1},
    };
    for (unsigned i = 0; i < sizeof t/sizeof t[0]; i++) {
        sentinels(&g_in);
        uint64_t exp_rdi = g_in.rdi, exp_rax = g_in.rax;
        if (!strcmp(t[i].name,"w_main (tail)")) { g_in.rax = 0; exp_rax = 0; }   /* variadic: al = 0 */
        if (t[i].viaVt) { g_in.rax = (uint64_t)vtable; exp_rax = g_in.rax; exp_rdi = g_in.r15; }
        if (t[i].viaVt == 2) { g_in.rax = (uint64_t)vtable; exp_rax = g_in.rax; exp_rdi = g_in.r13; g_in.rsi = 1; }
        run(t[i].fn);
        common_out(t[i].name);
        check_target(t[i].name, t[i].rec, exp_rdi, exp_rax);
        printf("ran %-14s ok so far (fails=%d)\n", t[i].name, fails);
    }
    /* flush, twice: first with no existing file (remove fails -> errno changes inside), then with one */
    for (int pass = 0; pass < 2; pass++) {
        sentinels(&g_in);
        *(uint32_t*)A_errno_var = 77;
        run(F_flush);
        common_out("flush");
        CHECK(*(uint32_t*)A_errno_var == 77, "flush pass %d: errno not restored (%u)", pass, *(uint32_t*)A_errno_var);
        CHECK(g_out.rax==g_in.rax && g_out.rcx==g_in.rcx && g_out.rdx==g_in.rdx && g_out.rsi==g_in.rsi && g_out.rdi==g_in.rdi &&
              g_out.r8==g_in.r8 && g_out.r9==g_in.r9 && g_out.r10==g_in.r10 && g_out.r11==g_in.r11,
              "flush pass %d: a caller-saved register was not preserved", pass);
        CHECK(memcmp(g_out.xmm, g_in.xmm, 128)==0, "flush pass %d: xmm0-7 not preserved", pass);
        uint64_t *o = (uint64_t*)A_last_open_rsi;
        CHECK(o[0]==0x101 && o[1]==0x1b6, "flush pass %d: open() flags/mode seen by stub %llx/%llx", pass, (unsigned long long)o[0], (unsigned long long)o[1]);
    }
    printf("TOTAL checks=%d fails=%d\n", checks, fails);
    return fails ? 1 : 0;
}

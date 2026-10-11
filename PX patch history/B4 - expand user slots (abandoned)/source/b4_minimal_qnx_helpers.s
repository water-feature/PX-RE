# Minimal B4 helper implementation; relocations resolved by patch_b4_minimal_qnx.py.
.text
# Each thunk uses tail jumps; no new calls, allocation or catch machinery.
.macro fn name
.globl \name
.type \name,@function
\name:
.endm
.macro endfn name
.size \name,.-\name
.endm
fn b4_cache_init
 leaq b4_size_extension(%rip),%rax
 leaq b4_size_extension_end(%rip),%rdx
1: movq $-1,(%rax)
 addq $8,%rax
 cmpq %rdx,%rax
 jne 1b
 leaq b4_stock_size_cache(%rip),%rax
 jmp b4_stock_init_continue
endfn b4_cache_init
fn b4_size_front
 cmpl $96,%esi
 ja 3f
 cmpl $1,%edi
 ja 3f
 testl %edi,%edi
 jne 2f
 leaq b4_stock_size_cache(%rip),%rax
 cmpl $64,%esi
 jbe 1f
 leaq b4_extension_bias(%rip),%rax
1: movslq %esi,%rcx
 jmp b4_stock_size_load
2: jmp b4_stock_size_miss
3: xorl %eax,%eax
 ret
endfn b4_size_front
fn b4_size_store_base
 leaq b4_stock_size_cache(%rip),%rdx
 cmpl $64,%r14d
 jbe 1f
 leaq b4_extension_bias(%rip),%rdx
1: jmp b4_stock_size_store
endfn b4_size_store_base
fn b4_copy_cache_base
 leaq b4_stock_size_cache(%rip),%rax
 cmpl $64,%r14d
 jbe 1f
 leaq b4_extension_bias(%rip),%rax
1: jmp b4_stock_copy_cache_continue
endfn b4_copy_cache_base
fn b4_delete_cache_base
 leaq b4_stock_size_cache(%rip),%rax
 cmpl $64,%r14d
 jbe 1f
 leaq b4_extension_bias(%rip),%rax
1: jmp b4_stock_delete_cache_continue
endfn b4_delete_cache_base
fn b4_direct_size_guard
 cmpl $96,%esi
 ja 1f
 cmpl $1,%edi
 ja 1f
 jmp b4_stock_size_backend
1: xorl %eax,%eax
 ret
endfn b4_direct_size_guard
fn b4_copy_group_guard
 cmpl $96,%r12d
 ja 1f
 leaq b4_stock_group_names(%rip),%rax
 jmp b4_stock_copy_group_continue
1: jmp b4_stock_copy_epilogue
endfn b4_copy_group_guard
# Mid-function guards retain original frames and tail-jump to stock paths.
fn b4_release_guard
 cmpl $-1,%esi
 je 1f
 cmpl $96,%esi
 ja 3f
 cmpl $-1,%edx
 je 2f
 cmpl $16,%edx
 ja 3f
 jmp b4_stock_release_scoped
1: jmp b4_stock_release_all
2: jmp b4_stock_release_group
3: jmp b4_stock_release_epilogue
endfn b4_release_guard
fn b4_index_guard
 cmpl $-1,%ebx
 je 1f
 cmpl $96,%ebx
 ja 3f
 cmpl $-1,%ebp
 je 2f
 cmpl $16,%ebp
 ja 3f
 jmp b4_stock_index_scoped
1: jmp b4_stock_index_all
2: jmp b4_stock_index_group
3: jmp b4_stock_index_epilogue
endfn b4_index_guard
fn b4_update_guard
 movq %rax,8(%rsp)
 cmpl $-1,%r15d
 je 1f
 cmpl $96,%r15d
 ja 2f
 cmpl $-1,%r13d
 je 1f
 cmpl $16,%r13d
 ja 2f
1: cmpl $96,%r15d
 jmp b4_stock_update_branch
2: jmp b4_stock_update_epilogue
endfn b4_update_guard
# Incoming eax is the full-width stock count. Preserve successful stock reply.
fn b4_count_reply_guard
 movl %eax,%edx
 movl $0x4012,%esi
 cmpl $255,%eax
 jbe 1f
 movl $0x403c,%esi
 xorl %edx,%edx
1: movq %r15,%rdi
 jmp b4_stock_count_send
endfn b4_count_reply_guard

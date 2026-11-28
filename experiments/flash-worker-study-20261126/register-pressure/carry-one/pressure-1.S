.global _start
.text
_start:
 mov $1, %rax
 mov $2, %rbx
 mov $1, %rcx
 mov $3, %rdx
 mov $4, %rsi
 mov $5, %rdi
 mov $6, %rbp
 mov $7, %r8
 mov $8, %r9
 mov $9, %r10
 mov $10, %r11
 mov $11, %r12
 mov $12, %r13
 mov $13, %r14
 mov $-1, %r15
 stc
again:
 adc %r15, %rbx
 dec %rcx
 jnz again
 cmp $1, %rax
 jne bad
 cmp $2, %rbx
 jne bad
 cmp $0, %rcx
 jne bad
 cmp $3, %rdx
 jne bad
 cmp $4, %rsi
 jne bad
 cmp $5, %rdi
 jne bad
 cmp $6, %rbp
 jne bad
 cmp $7, %r8
 jne bad
 cmp $8, %r9
 jne bad
 cmp $9, %r10
 jne bad
 cmp $10, %r11
 jne bad
 cmp $11, %r12
 jne bad
 cmp $12, %r13
 jne bad
 cmp $13, %r14
 jne bad
 cmp $-1, %r15
 jne bad
 mov $60, %eax
 xor %edi, %edi
 syscall
bad:
 mov $60, %eax
 mov $1, %edi
 syscall

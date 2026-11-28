.global _start
.text
_start:
 movl $1000000, %ecx
 xorl %eax, %eax
again:
 addl $1, %eax
 decl %ecx
 jnz again
 movl $60, %eax
 xorl %edi, %edi
 syscall

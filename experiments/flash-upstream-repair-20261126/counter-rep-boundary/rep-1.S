.global _start
.text
_start:
 movl $1, %ecx
 leaq source(%rip), %rsi
 leaq destination(%rip), %rdi
 rep movsb
 movl $60, %eax
 xorl %edi, %edi
 syscall
.bss
source: .space 1024
destination: .space 1024

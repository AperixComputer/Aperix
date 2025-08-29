include "riscv64.inc"

UART_BASE = 0x10000000
UART_REG_SHIFT = 2
UART_THR = 0
UART_LSR = 5
UART_LSR_THRE = 1 shl 5

entry:
csrr t0, mhartid
bnez t0, halt
la a0, hw
call uart_puts
la a0, welcome
call uart_puts
j halt

uart_puts:
mv s1, ra
mv s2, a0
.loop:
lb a0, s2, 0
beqz a0, .end
call uart_putc
addi s2, s2, 1
j .loop
.end:
mv ra, s1
ret

uart_putc:
li t0, UART_BASE
.wait_for_thr_enable:
lb t1, t0, UART_LSR shl UART_REG_SHIFT
andi t1, t1, UART_LSR_THRE
beqz t1, .wait_for_thr_enable
sb a0, t0, UART_THR shl UART_REG_SHIFT
ret

halt:
wfi
j halt

hw db "Hello, world!", 10, 13, 0
welcome db "Welcome to Aperix.", 10, 13, 0

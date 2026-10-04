.text
.global main
main:
    addi x5, x0, 0
    addi x6, x6, -1
    bne x6, x0, main

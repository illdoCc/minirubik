.text
.global main
main: 
    li x5, 0x10000000
    addi x6, x0, 0x100 # an arbitrary number
    # addi x7, x0, 0x400 # for 4 KiB, we need to sw 0x400(1024) times
loop:
    sw x6, 0(x5)
    addi x5, x5, 4
    addi x7, x7, -1
    bne x7, x0, loop


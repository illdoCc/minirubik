# Ripes LED practice: blue border, yellow diagonal, dark interior.
# Before assembling: I/O -> add LED Matrix -> Width 8, Height 8.
# Input type: Assembly. Processor: RV32I single-cycle is sufficient.
# The LED_MATRIX_0_* symbols are supplied by the GUI peripheral.

.text
.globl main
main:
    li t0, LED_MATRIX_0_BASE    # Address of the current LED
    li t1, LED_MATRIX_0_WIDTH   # Number of columns
    li t2, LED_MATRIX_0_HEIGHT  # Number of rows
    addi s0, t1, -1            # Rightmost x coordinate
    addi s1, t2, -1            # Bottom y coordinate
    li t4, 0                  # y = 0

row:
    li t3, 0                  # x = 0 at the start of each row

pixel:
    li t5, 0x00000000         # Default color: black (off)
    beq t3, zero, border      # Left edge: x == 0
    beq t3, s0, border        # Right edge: x == width - 1
    beq t4, zero, border      # Top edge: y == 0
    beq t4, s1, border        # Bottom edge: y == height - 1
    bne t3, t4, draw          # Interior: leave black unless x == y
    li t5, 0x00FFFF00         # Diagonal: yellow
    j draw

border:
    li t5, 0x000000FF         # Border: blue

draw:
    sw t5, 0(t0)             # Write RGB color to the current LED
    addi t0, t0, 4           # Next LED address (4 bytes per LED)
    addi t3, t3, 1           # x++
    blt t3, t1, pixel        # Continue until this row is complete
    addi t4, t4, 1           # y++
    blt t4, t2, row          # Continue until all rows are complete

    li a7, 10                # Ripes environment call: exit
    ecall

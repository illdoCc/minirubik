.data
input_state:
    .asciz "21345671111111"
cube_state:
    .zero 14                    # state_t: p[7], followed by o[7]
.align 2
permutation_rank:
    .half 0
orientation_rank:
    .half 0
search_path:
    .zero 11                    # path[MAX_DEPTH]
.align 4
solution_length:
    .word -1

# move_names[MOVES], in the same order as solver.c.
move_r:
    .asciz "R"
move_r2:
    .asciz "R2"
move_ri:
    .asciz "R'"
move_b:
    .asciz "B"
move_b2:
    .asciz "B2"
move_bi:
    .asciz "B'"
move_d:
    .asciz "D"
move_d2:
    .asciz "D2"
move_di:
    .asciz "D'"
.align 4
move_names:
    .word move_r, move_r2, move_ri, move_b, move_b2, move_bi
    .word move_d, move_d2, move_di
invalid_message:
    .asciz "invalid input: expected PPPPPPPOOOOOOO\n"
search_failed_message:
    .asciz "could not find a solution\n"

# Ripes .align specifies a byte boundary. Keep sp aligned to 16 bytes.
.align 16
call_stack:
    .zero 256                   # Room for nested search calls and DFS entries
call_stack_top:

.text
.globl main
main:
    la sp, call_stack_top
    la a0, input_state          # parse_state(input_state, &state)
    la a1, cube_state
    jal ra, parse_state        # DONE: parse_state (also calls valid)
    beq a0, zero, main_invalid  # if (!parse_state(...)) return 2;

    la a0, cube_state           # rank_components(&state, &p, &o)
    la a1, permutation_rank
    la a2, orientation_rank
    jal ra, rank_components    # DONE: rank_components

    la t0, permutation_rank    # length = search_optimal(p, o);
    lhu a0, 0(t0)
    la t0, orientation_rank
    lhu a1, 0(t0)
    jal ra, search_optimal     # DONE: search_optimal calls search_limited
    la t0, solution_length     # Keep the returned length for inspection
    sw a0, 0(t0)
    blt a0, zero, main_search_failed

    mv s0, a0                  # length; s1 = i
    li s1, 0                   # for (int i = 0; i < length; ++i)
main_print_loop:
    bge s1, s0, main_print_done
    beq s1, zero, main_print_move # No separator before the first move
    li a0, 32                  # Print the separator: ' '
    li a7, 11
    ecall
main_print_move:
    la t0, search_path         # move_names[search.path[i]]
    add t0, t0, s1
    lbu t1, 0(t0)
    slli t1, t1, 2             # Each string address occupies four bytes
    la t0, move_names
    add t0, t0, t1
    lw a0, 0(t0)
    li a7, 4                   # Print the move name
    ecall
    addi s1, s1, 1             # ++i;
    j main_print_loop
main_print_done:
    li a0, 10                  # putchar('\n');
    li a7, 11
    ecall
    li a0, 0                    # return 0;
    j main_exit
main_search_failed:
    la a0, search_failed_message # Report search failure
    li a7, 4
    ecall
    li a0, 1                    # return 1;
    j main_exit
main_invalid:
    la a0, invalid_message      # Report invalid input
    li a7, 4
    ecall
    li a0, 2                    # return 2;
main_exit:
    li a7, 93
    ecall

# parse_state(input, state): a0 = input, a1 = state; return boolean in a0.
# t0 = i, t1 = input[i], t2 = limit, t3/t4 = temporary values.
parse_state:
    addi sp, sp, -16            # Reserve stack space and save caller's ra
    sw ra, 12(sp)
    li t0, 0                    # i = 0;
parse_loop:
    li t2, 7                    # limit = i < 7 ? 7 : 3;
    blt t0, t2, parse_character
    li t2, 3
parse_character:
    add t3, a0, t0              # Read input[i]
    lbu t1, 0(t3)
    li t4, 49                   # if (input[i] < '1') return 0;
    bltu t1, t4, parse_invalid
    addi t4, t2, 48             # if (input[i] > '0' + limit) return 0;
    bltu t4, t1, parse_invalid
    addi t1, t1, -49            # value = input[i] - '1';
    # p[i] and o[i - 7] both reside at state + i in this layout.
    add t3, a1, t0              # Store value in p[i] or o[i - 7]
    sb t1, 0(t3)
    addi t0, t0, 1              # ++i;
    li t2, 14                   # Continue the loop while i < 14
    blt t0, t2, parse_loop
    lbu t1, 14(a0)              # if (input[14] != '\0') return 0;
    bne t1, zero, parse_invalid
    mv a0, a1                   # return valid(state);
    jal ra, valid
    j parse_return
parse_invalid:
    li a0, 0                    # return 0;
parse_return:
    lw ra, 12(sp)               # Restore caller's ra and release stack space
    addi sp, sp, 16
    ret

# valid(state): a0 = state; return boolean in a0.
# t0 = i, t1 = sum, t2 = p[i], t3 = o[i], t4 = j; t5/t6 are temporary.
valid:
    li t0, 0                    # i = 0;
    li t1, 0                    # sum = 0;
valid_loop:
    add t5, a0, t0              # Read state->p[i] and state->o[i]
    lbu t2, 0(t5)
    lbu t3, 7(t5)
    li t6, 7                    # if (state->p[i] >= CUBIES) return 0;
    bgeu t2, t6, valid_no
    li t6, 3                    # if (state->o[i] >= 3) return 0;
    bgeu t3, t6, valid_no
    li t4, 0                    # j = 0;
valid_duplicates:
    beq t4, t0, valid_next      # End the inner loop when j == i
    add t5, a0, t4              # if (state->p[j] == state->p[i]) return 0;
    lbu t6, 0(t5)
    beq t2, t6, valid_no
    addi t4, t4, 1              # ++j;
    j valid_duplicates
valid_next:
    add t1, t1, t3              # sum += state->o[i];
    addi t0, t0, 1              # ++i;
    li t6, 7                    # Continue the outer loop while i < CUBIES
    blt t0, t6, valid_loop

    # Match the conditional subtractions in valid().
    li t6, 12                   # if (sum >= 12) sum -= 12;
    bltu t1, t6, valid_reduce6
    addi t1, t1, -12
valid_reduce6:
    li t6, 6                    # if (sum >= 6) sum -= 6;
    bltu t1, t6, valid_reduce3
    addi t1, t1, -6
valid_reduce3:
    li t6, 3                    # if (sum >= 3) sum -= 3;
    bltu t1, t6, valid_remainder
    addi t1, t1, -3
valid_remainder:
    bne t1, zero, valid_no      # return sum == 0;
    li a0, 1
    ret
valid_no:
    li a0, 0                    # return 0;
    ret

# rank_components(state, &p, &o): a0 = state, a1/a2 = output addresses.
# t0 = i, t1 = p, t2 = smaller (then o), t3 = j, t4 = p[i].
# t5/t6 are temporary; a3 = CUBIES, a4 = CUBIES - i.
rank_components:
    li t0, 0                    # i = 0;
    li t1, 0                    # p = 0;
    li a3, 7                    # CUBIES = 7
rank_permutation:
    li t2, 0                    # smaller = 0;
    addi t3, t0, 1              # j = i + 1;
    add t5, a0, t0              # Read state->p[i]
    lbu t4, 0(t5)
rank_smaller:
    bge t3, a3, rank_factor     # End the inner loop when j >= CUBIES
    add t5, a0, t3              # if (state->p[j] < state->p[i]) ++smaller;
    lbu t6, 0(t5)
    bgeu t6, t4, rank_next_j
    addi t2, t2, 1
rank_next_j:
    addi t3, t3, 1              # ++j;
    j rank_smaller

rank_factor:
    sub a4, a3, t0              # switch (CUBIES - i)
    li t6, 7                    # case 7:
    beq a4, t6, rank_times7
    li t6, 6                    # case 6:
    beq a4, t6, rank_times6
    li t6, 5                    # case 5:
    beq a4, t6, rank_times5
    li t6, 4                    # case 4:
    beq a4, t6, rank_times4
    li t6, 3                    # case 3:
    beq a4, t6, rank_times3
    li t6, 2                    # case 2:
    beq a4, t6, rank_times2
    j rank_add_smaller          # case 1: no change
rank_times7:
    li t1, 0                    # p = 0;
    j rank_add_smaller
rank_times6:
    slli t5, t1, 2              # p = (p << 2) + (p << 1);
    slli t6, t1, 1
    add t1, t5, t6
    j rank_add_smaller
rank_times5:
    slli t5, t1, 2              # p = (p << 2) + p;
    add t1, t5, t1
    j rank_add_smaller
rank_times4:
    slli t1, t1, 2              # p <<= 2;
    j rank_add_smaller
rank_times3:
    slli t5, t1, 1              # p = (p << 1) + p;
    add t1, t5, t1
    j rank_add_smaller
rank_times2:
    slli t1, t1, 1              # p <<= 1;
rank_add_smaller:
    add t1, t1, t2              # p += smaller;
    addi t0, t0, 1              # ++i;
    blt t0, a3, rank_permutation # Continue while i < CUBIES

    li t0, 0                    # i = 0;
    li t2, 0                    # o = 0;
    li t6, 6                    # Encode the first six orientation digits
rank_orientation:
    add t5, a0, t0              # o = (o << 1) + o + state->o[i];
    lbu t4, 7(t5)
    slli t5, t2, 1
    add t2, t5, t2
    add t2, t2, t4
    addi t0, t0, 1              # ++i;
    blt t0, t6, rank_orientation # Continue while i < 6
    sh t1, 0(a1)                # *permutation_rank = (uint16_t) p;
    sh t2, 0(a2)                # *orientation_rank = (uint16_t) o;
    ret

# search_optimal(p, o): a0 = p, a1 = o.
# Return the shortest length in a0, or -1 on failure; fill search_path.
search_optimal:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    sw s2, 0(sp)
    # Compute the lower bound before trying each depth limit.
    li t0, 5040                 # if(p >= PERMUTATIONS || o >= ORIENTATIONS) return -1;
    bgeu a0, t0, search_optimal_valid
    li t0, 729
    bgeu a1, t0, search_optimal_valid
    la t1, permutation_distance # lower_bound = search->permutation_distance[p]
    add t0, t1, a0
    lbu t2, 0(t0)               # t2 is lower_bound
    la t1, orientation_distance # load search->orientation[o]
    add t0, t1, a1
    lbu t3, 0(t0)               # t3 is search->orientation[o]
    bge t2, t3, search_optimal_next # if(search->orientation[o] > lower_bound)
    mv t2, t3                   # lower_bound = search->orientation_distance[o]
search_optimal_next:
    mv s0, a0                   # store p and o in s register
    mv s1, a1
    mv s2, t2                   # limit = lower_bound
search_optimal_loop:
    mv a0, s0
    mv a1, s1
    mv a2, s2
    jal ra, search_limited      # search_limited(search, p, o, limited)
    bge a0, zero, search_optimal_return # return length
    addi s2, s2, 1
    li t3, 11                   # end the loop if limit > Max_Depth
    bge t3, s2, search_optimal_loop

search_optimal_valid:
    lw s2, 0(sp)
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    li a0, -1                   # return -1
    ret
search_optimal_return:
    lw s2, 0(sp)
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# search_limited(p, o, limit): a0 = p, a1 = o, a2 = limit.
# The four tables have static labels, so no search_t pointer is passed.
# Write the moves to search_path; return the length in a0, or -1 on failure.
# Restore sp and any s-registers you use before returning.
search_limited:
    li t0, 5040                 # if (p >= PERMUTATIONS) return -1;
    bgeu a0, t0, search_limited_invalid
    li t0, 729                  # if (o >= ORIENTATIONS) return -1;
    bgeu a1, t0, search_limited_invalid
    li t0, 11                   # if (limit > MAX_DEPTH) return -1;
    bltu t0, a2, search_limited_invalid

    # stack[12]: 72 bytes; saved s0-s5: 24 bytes. Total: 96 bytes.
    # Each entry: p at +0, o at +2, next_move at +4, padding at +5.
    addi sp, sp, -96            # search_frame_t stack[MAX_DEPTH + 1];
    sw s0, 72(sp)
    sw s1, 76(sp)
    sw s2, 80(sp)
    sw s3, 84(sp)
    sw s4, 88(sp)
    sw s5, 92(sp)
    la s2, permutation_distance # Keep the four table bases across iterations
    la s3, orientation_distance
    la s4, permutation_table
    la s5, orientation_table
    li s0, 0                   # depth = 0; keep depth in s0
    mv s1, a2                  # Keep limit in s1
    sh a0, 0(sp)               # stack[0] = (search_frame_t) {p, o, 0};
    sh a1, 2(sp)
    sb zero, 4(sp)
    mv t0, sp                 # frame = &stack[0]; keep its address in t0
    # SEARCH_NODE_VISITED() is a no-op outside host tests.

search_limited_loop:
    # s0 = depth, s1 = limit; t0 = frame, t1 = p, t2 = o.
    # a0 = move, a1 = face, a2 = turns; a3/a4 = transition row addresses.
    lhu t1, 0(t0)
    lhu t2, 2(t0)
    or t3, t1, t2              # if (frame->p == 0 && frame->o == 0)
    beq t3, zero, search_limited_solved

    add t4, s2, t1             # lower_bound = permutation_distance[frame->p];
    lbu t3, 0(t4)
    add t4, s3, t2             # if (orientation_distance[o] > lower_bound)
    lbu t5, 0(t4)
    bgeu t3, t5, search_limited_bound
    mv t3, t5                  # lower_bound = orientation_distance[o];
search_limited_bound:
    beq s0, s1, search_limited_backtrack # depth == limit
    lbu a0, 4(t0)              # frame->next_move == MOVES
    li t4, 9
    beq a0, t4, search_limited_backtrack
    add t3, s0, t3             # depth + lower_bound > limit
    bltu s1, t3, search_limited_backtrack

    addi t4, a0, 1             # move = frame->next_move++;
    sb t4, 4(t0)
    sltiu t4, a0, 3            # face = (move >= 3) + (move >= 6);
    xori t4, t4, 1
    sltiu a1, a0, 6
    xori a1, a1, 1
    add a1, t4, a1

    beq s0, zero, search_limited_turns # Check the previous face if depth > 0
    la t4, search_path         # previous = path[depth - 1];
    add t4, t4, s0
    lbu t5, -1(t4)
    sltiu t6, t5, 3            # previous_face: compare previous with 3 and 6
    xori t6, t6, 1
    sltiu a5, t5, 6
    xori a5, a5, 1
    add t6, t6, a5
    beq a1, t6, search_limited_loop # if (face == previous_face) continue;

search_limited_turns:
    slli a2, a1, 1             # turns = move - ((face << 1) + face) + 1;
    add a2, a2, a1
    sub a2, a0, a2
    addi a2, a2, 1

    # Select rows for face 0, 1, or 2 by adding the row size zero to two times.
    # permutation rows: 5040 * 2 bytes; orientation rows: 729 * 2 bytes.
    mv a3, s4
    mv a4, s5
    beq a1, zero, search_limited_quarter_turn
    li t4, 10080
    li t5, 1458
    add a3, a3, t4
    add a4, a4, t5
    li t6, 1
    beq a1, t6, search_limited_quarter_turn
    add a3, a3, t4
    add a4, a4, t5
search_limited_quarter_turn:
    slli t4, t1, 1             # next.p = permutation[face][next.p];
    add t4, a3, t4
    lhu t1, 0(t4)
    slli t4, t2, 1             # next.o = orientation[face][next.o];
    add t4, a4, t4
    lhu t2, 0(t4)
    addi a2, a2, -1            # Repeat until all quarter turns are applied
    bne a2, zero, search_limited_quarter_turn

    la t4, search_path         # path[depth] = move;
    add t4, t4, s0
    sb a0, 0(t4)
    addi s0, s0, 1             # stack[++depth] = next;
    addi t0, t0, 6             # frame = &stack[depth]; each entry is 6 bytes
    sh t1, 0(t0)
    sh t2, 2(t0)
    sb zero, 4(t0)
    j search_limited_loop

search_limited_backtrack:
    beq s0, zero, search_limited_failed # if (depth == 0) return -1;
    addi s0, s0, -1            # --depth; continue;
    addi t0, t0, -6            # Move frame back to the parent entry
    j search_limited_loop
search_limited_solved:
    mv a0, s0                  # return depth;
    j search_limited_return
search_limited_failed:
    li a0, -1
search_limited_return:
    lw s5, 92(sp)
    lw s4, 88(sp)
    lw s3, 84(sp)
    lw s2, 80(sp)
    lw s1, 76(sp)
    lw s0, 72(sp)
    addi sp, sp, 96
    ret
search_limited_invalid:
    li a0, -1
    ret

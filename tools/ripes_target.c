/* Built with solver_core.h extracted from solver.c by compare_gcc.py. */
#include "solver_core.h"

extern search_t target_search;
extern char input_state[];

static inline void print_string(const char *text)
{
    register const char *arg asm("a0") = text;
    register unsigned call asm("a7") = 4;
    asm volatile("ecall" : "+r"(arg), "+r"(call) : : "memory");
}

static inline void print_char(unsigned value)
{
    register unsigned arg asm("a0") = value;
    register unsigned call asm("a7") = 11;
    asm volatile("ecall" : "+r"(arg), "+r"(call) : : "memory");
}

int target_main(void)
{
    state_t state;
    uint16_t p, o;
    if (!parse_state(input_state, &state)) {
        print_string("invalid input: expected PPPPPPPOOOOOOO\n");
        return 2;
    }
    rank_components(&state, &p, &o);
    int length = search_optimal(&target_search, p, o);
    if (length < 0) {
        print_string("could not find a solution\n");
        return 1;
    }
    for (int i = 0; i < length; ++i) {
        if (i)
            print_char(' ');
        uint8_t move = target_search.path[i];
        print_string(move_names[move]);
        state = apply_move(state, move);
    }
    print_char('\n');
    if (valid(&state)) {
        rank_components(&state, &p, &o);
        if (!p && !o)
            return 0;
    }
    print_string("solution replay did not reach solved\n");
    return 3;
}

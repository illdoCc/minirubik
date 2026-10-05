#define main solver_main
#include "../solver.c"
#undef main

/* Check table completeness, solved entries, and maximum distances (H2).
 * Verify the heuristic never exceeds the exact BFS distance for any state (H1).
 */
static int check_distances(const uint8_t *table)
{
    uint16_t permutation[3][PERMUTATIONS], orientation[3][ORIENTATIONS];
    uint8_t permutation_distance[PERMUTATIONS], orientation_distance[ORIENTATIONS];
    uint16_t queue[PERMUTATIONS];
    build_transitions(permutation, orientation);
    if (!build_distances(PERMUTATIONS, permutation, permutation_distance, queue) ||
        !build_distances(ORIENTATIONS, orientation, orientation_distance, queue))
        return 0;
    if (permutation_distance[0] != 0 || orientation_distance[0] != 0)
        return 0;
    uint8_t permutation_max = 0, orientation_max = 0;
    for (uint16_t rank = 0; rank < PERMUTATIONS; ++rank)
        if (permutation_distance[rank] > permutation_max)
            permutation_max = permutation_distance[rank];
    for (uint16_t rank = 0; rank < ORIENTATIONS; ++rank)
        if (orientation_distance[rank] > orientation_max)
            orientation_max = orientation_distance[rank];
    if (permutation_max != 7 || orientation_max != 6)
        return 0;

    /* Following the original BFS table gives the exact distance. Compare
     * both projections against it for every state, hence also their maximum.
     */
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        state_t state;
        uint8_t distance = 0;
        unrank_state(rank, &state);
        for (uint32_t here = rank; here; here = rank_state(&state)) {
            if (distance >= 11 || table[here] >= MOVES)
                return 0;
            state = apply_move(state, table[here]);
            ++distance;
        }
        if (permutation_distance[rank / ORIENTATIONS] > distance ||
            orientation_distance[rank % ORIENTATIONS] > distance)
            return 0;
    }
    return 1;
}

int main(void)
{
    uint8_t diameter;
    uint8_t *table = build_table(&diameter);
    if (!table) {
        fputs("could not build complete state table\n", stderr);
        return 1;
    }
    int passed = diameter == 11 && check_distances(table);
    free(table);
    if (!passed) {
        fputs("heuristic table check failed\n", stderr);
        return 1;
    }
    puts("heuristic tables complete; maxima 7 and 6; admissible on 3674160 states");
    return output_failed();
}

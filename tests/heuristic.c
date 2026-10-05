#define main solver_main
#include "../solver.c"
#undef main

/* Replay the returned moves using the cubie model, not the transition tables. */
static int check_path(search_t *search, uint32_t rank, uint8_t limit)
{
    int length = search_limited(search, rank, limit);
    if (length < 0 || length > limit)
        return -1;
    state_t state;
    unrank_state(rank, &state);
    for (int i = 0; i < length; ++i) {
        if (search->path[i] >= MOVES)
            return -1;
        state = apply_move(state, search->path[i]);
    }
    return rank_state(&state) == 0 ? length : -1;
}

/* Check table completeness, solved entries, and maximum distances (H2).
 * Verify the heuristic never exceeds the exact BFS distance for any state (H1).
 */
static int check_distances(const uint8_t *table)
{
    search_t search;
    if (!init_search(&search))
        return 0;
    if (search_limited(&search, STATES, 0) != -1 ||
        search_limited(&search, 0, MAX_DEPTH + 1) != -1)
        return 0;
    /* An inverse B turn allows the unpruned DFS to exercise its full stack. */
    state_t solved;
    unrank_state(0, &solved);
    state_t scramble = apply_move(solved, 5);
    if (check_path(&search, rank_state(&scramble), MAX_DEPTH) < 0)
        return 0;
    if (search.permutation_distance[0] != 0 ||
        search.orientation_distance[0] != 0)
        return 0;
    uint8_t permutation_max = 0, orientation_max = 0;
    for (uint16_t rank = 0; rank < PERMUTATIONS; ++rank)
        if (search.permutation_distance[rank] > permutation_max)
            permutation_max = search.permutation_distance[rank];
    for (uint16_t rank = 0; rank < ORIENTATIONS; ++rank)
        if (search.orientation_distance[rank] > orientation_max)
            orientation_max = search.orientation_distance[rank];
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
            if (distance >= MAX_DEPTH || table[here] >= MOVES)
                return 0;
            state = apply_move(state, table[here]);
            ++distance;
        }
        if (search.permutation_distance[rank / ORIENTATIONS] > distance ||
            search.orientation_distance[rank % ORIENTATIONS] > distance)
            return 0;
        /* Check cutoff, backtracking, and paths for every shallow state. */
        if (distance <= 3) {
            if (distance > 0 &&
                search_limited(&search, rank, distance - 1U) != -1)
                return 0;
            if (check_path(&search, rank, distance) != distance)
                return 0;
        }
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
        fputs("heuristic table or bounded DFS check failed\n", stderr);
        return 1;
    }
    puts("heuristic tables complete; maxima 7 and 6; admissible on 3674160 states");
    puts("bounded DFS: cutoffs and solution paths verified through depth 3");
    return output_failed();
}

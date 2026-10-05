#define main solver_main
#include "../solver.c"
#undef main

/* Replay the returned moves using the cubie model, not the transition tables. */
static int check_solution_path(search_t *search, uint32_t rank, int length)
{
    if (length < 0 || length > MAX_DEPTH)
        return -1;
    state_t state;
    unrank_state(rank, &state);
    for (int i = 0; i < length; ++i) {
        if (search->path[i] >= MOVES)
            return -1;
        if (i > 0 && search->path[i] / 3U == search->path[i - 1] / 3U)
            return -1;
        state = apply_move(state, search->path[i]);
    }
    return rank_state(&state) == 0 ? length : -1;
}

static int check_path(search_t *search, uint32_t rank, uint8_t limit)
{
    int length = search_limited(search, rank, limit);
    if (length > limit)
        return -1;
    return check_solution_path(search, rank, length);
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
        search_limited(&search, 0, MAX_DEPTH + 1) != -1 ||
        search_optimal(&search, STATES) != -1)
        return 0;
    /* A loose limit must still produce a valid path without repeated faces. */
    state_t solved;
    unrank_state(0, &solved);
    state_t scramble = apply_move(solved, 5);
    if (check_path(&search, rank_state(&scramble), MAX_DEPTH) < 0)
        return 0;
    /* This known distance-11 state must reach the last stack/path entries. */
    if (!parse_state("21345671111111", &scramble) ||
        search_limited(&search, rank_state(&scramble), MAX_DEPTH - 1) != -1 ||
        check_path(&search, rank_state(&scramble), MAX_DEPTH) != MAX_DEPTH)
        return 0;
    uint32_t sample_rank = rank_state(&scramble);
    int sample_length = search_optimal(&search, sample_rank);
    if (check_solution_path(&search, sample_rank, sample_length) != MAX_DEPTH)
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
    uint8_t checked[MAX_DEPTH + 1] = {0};
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
        if (distance <= 4) {
            if (distance > 0 &&
                search_limited(&search, rank, distance - 1U) != -1)
                return 0;
            if (check_path(&search, rank, distance) != distance)
                return 0;
        }
        /* All shallow states, plus one state at each remaining distance. */
        if (distance <= 4 || !checked[distance]) {
            int length = search_optimal(&search, rank);
            if (length != distance ||
                check_solution_path(&search, rank, length) != distance)
                return 0;
            checked[distance] = 1;
        }
    }
    for (uint8_t distance = 0; distance <= MAX_DEPTH; ++distance)
        if (!checked[distance])
            return 0;
    return 1;
}

/* Require canonical move tokens separated by single spaces, then replay them. */
static int replay_solution(state_t state, const char *solution)
{
    int length = 0;
    while (*solution) {
        size_t token_length = strcspn(solution, " ");
        uint8_t move;
        for (move = 0; move < MOVES; ++move)
            if (strlen(move_names[move]) == token_length &&
                !strncmp(solution, move_names[move], token_length))
                break;
        if (move == MOVES || length == MAX_DEPTH)
            return -1;
        state = apply_move(state, move);
        ++length;
        solution += token_length;
        if (*solution) {
            ++solution;
            if (!*solution)
                return -1;
        }
    }
    return rank_state(&state) == 0 ? length : -1;
}

/* Accept any solving path with the fixture's optimal length, but preserve
 * the CLI format: a single line, single spaces, and one terminating newline.
 */
static int check_cli_solution(const char *input, const char *reference)
{
    state_t state;
    if (!parse_state(input, &state))
        return 0;
    char output[3 * MAX_DEPTH + 1];
    size_t size = fread(output, 1, sizeof output, stdin);
    if (size == 0 || size == sizeof output || ferror(stdin) ||
        output[size - 1] != '\n' || memchr(output, '\0', size - 1))
        return 0;
    output[size - 1] = '\0';
    int expected = replay_solution(state, reference);
    return expected >= 0 && replay_solution(state, output) == expected;
}

int main(int argc, char **argv)
{
    if (argc == 4 && !strcmp(argv[1], "--check-solution")) {
        if (check_cli_solution(argv[2], argv[3]))
            return 0;
        fputs("invalid or non-optimal CLI solution\n", stderr);
        return 1;
    }
    if (argc != 1)
        return 2;
    uint8_t diameter;
    uint8_t *table = build_table(&diameter);
    if (!table) {
        fputs("could not build complete state table\n", stderr);
        return 1;
    }
    int passed = diameter == 11 && check_distances(table);
    free(table);
    if (!passed) {
        fputs("heuristic table or search check failed\n", stderr);
        return 1;
    }
    puts("heuristic tables complete; maxima 7 and 6; admissible on 3674160 states");
    puts("bounded DFS: cutoffs and paths verified through depth 4 and at 11");
    puts("IDA*: BFS distances matched through depth 4 and samples at depths 5-11");
    return output_failed();
}

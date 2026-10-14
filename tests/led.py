"""Check LED frames against geometric rotations, using RAM as the peripheral."""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_ripes",
                                             ROOT / "tools/build_ripes.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

# Physical corners and outward normals; x=right, y=up, z=front.
POSITIONS = [(-1, 1, 1), (1, 1, 1), (1, -1, 1), (-1, -1, 1),
             (1, 1, -1), (1, -1, -1), (-1, -1, -1), (-1, 1, -1)]
NORMALS = {"U": (0, 1, 0), "L": (-1, 0, 0), "F": (0, 0, 1),
           "R": (1, 0, 0), "B": (0, 0, -1), "D": (0, -1, 0)}
SLOTS = ["UFL", "URF", "DFR", "DLF", "UBR", "DRB", "DBL", "ULB"]
COLORS = dict(zip("ULFRBD", [0xffffff, 0xff8000, 0x00c000,
                                   0xff0000, 0x0040ff, 0xffff00]))
# Face: origin, screen-right vector, screen-down vector.
VIEWS = {"U": ((9, 2), (1, 0, 0), (0, 0, 1)),
         "L": ((0, 9), (0, 0, 1), (0, -1, 0)),
         "F": ((9, 9), (1, 0, 0), (0, -1, 0)),
         "R": ((18, 9), (0, 0, -1), (0, -1, 0)),
         "B": ((27, 9), (-1, 0, 0), (0, -1, 0)),
         "D": ((9, 16), (1, 0, 0), (0, 0, -1))}
MOVES = "R R2 R' B B2 B' D D2 D'".split()
LED_BASE = 0x20000000


def stickers(value):
    cubies = [0] + [int(c) for c in value[:7]]
    twists = [0] + [int(c) - 1 for c in value[7:]]
    return {(position, NORMALS[face]): SLOTS[cubies[i]][(slot + twists[i]) % 3]
            for i, position in enumerate(POSITIONS)
            for slot, face in enumerate(SLOTS[i])}


def rotate(vector, axis):
    x, y, z = vector
    return [(x, -z, y), (z, y, -x), (-y, x, z)][axis]


def apply_geometry(state, move):
    # Clockwise from outside: -90 about +x, +90 about -z or -y.
    axis, side, quarter_turns = {"R": (0, 1, 3), "B": (2, -1, 1),
                                "D": (1, -1, 1)}[move[0]]
    turns = {"": 1, "2": 2, "'": 3}[move[1:]]
    for _ in range(turns):
        result = {}
        for (position, normal), color in state.items():
            if position[axis] == side:
                for _ in range(quarter_turns):
                    position = rotate(position, axis)
                    normal = rotate(normal, axis)
            result[position, normal] = color
        state = result
    return state


def pixels(state):
    result = [0] * (35 * 25)
    for (position, normal), color in state.items():
        face = next(f for f, n in NORMALS.items() if n == normal)
        (x, y), right, down = VIEWS[face]
        x += 4 * ((sum(a * b for a, b in zip(position, right)) + 1) // 2)
        y += 3 * ((sum(a * b for a, b in zip(position, down)) + 1) // 2)
        for dy in range(3):
            for dx in range(4):
                result[(y + dy) * 35 + x + dx] = COLORS[color]
    return result


def with_input(source, value):
    return source.replace('.asciz "21345671111111"', f'.asciz "{value}"', 1)


def checked_renderer(source, value, solution):
    state = stickers(value)
    frames = [pixels(state)]
    for move in solution.split():
        state = apply_geometry(state, move)
        frames.append(pixels(state))
    assert state == stickers("12345671111111"), "Geometric replay failed"
    expected = [pixel for frame in frames for pixel in frame]
    words = "\n".join("    .word " + ", ".join(hex(x) for x in expected[i:i+8])
                      for i in range(0, len(expected), 8))
    source = with_input(source, value)
    source = source.replace(".equ LED_DELAY, 1000000", ".equ LED_DELAY, 0")
    source = source.replace("    jal ra, render_cube",
                            "    jal ra, render_cube\n    jal ra, test_frame")
    source = source.replace("main_exit:\n", f"""main_exit:
    la t0, test_frame_count
    lw t1, 0(t0)
    li t2, {len(frames)}
    bne t1, t2, test_failure
""")
    source = source.replace("main:\n", f"""main:
    li t0, {LED_BASE - 4}
    li t1, 12345
    sw t1, 0(t0)
    li t0, {LED_BASE + 35 * 25 * 4}
    sw t1, 0(t0)
""")
    source += f"""
.data
.align 4
test_expected:
{words}
test_frame_ptr:
    .word test_expected
test_frame_count:
    .word 0
.text
test_frame:
    li t0, {LED_BASE - 4}
    lw t1, 0(t0)
    li t2, 12345
    bne t1, t2, test_failure
    li t0, {LED_BASE + 35 * 25 * 4}
    lw t1, 0(t0)
    bne t1, t2, test_failure
    la t0, test_frame_ptr
    lw t1, 0(t0)
    li t2, LED_MATRIX_0_BASE
    li t3, 875
test_pixel:
    lw t4, 0(t1)
    lw t5, 0(t2)
    bne t4, t5, test_failure
    addi t1, t1, 4
    addi t2, t2, 4
    addi t3, t3, -1
    bne t3, zero, test_pixel
    sw t1, 0(t0)
    la t0, test_frame_count
    lw t1, 0(t0)
    addi t1, t1, 1
    sw t1, 0(t0)
    ret
test_failure:
    li a0, 99
    li a7, 93
    ecall
    j test_failure
"""
    return (f".equ LED_MATRIX_0_BASE, {LED_BASE}\n"
            ".equ LED_MATRIX_0_WIDTH, 35\n.equ LED_MATRIX_0_HEIGHT, 25\n"
            + source), len(frames)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ripes", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    work = args.output or Path(tempfile.mkdtemp(prefix="minirubik-led-"))
    work.mkdir(parents=True, exist_ok=True)
    ripes = str(args.ripes.resolve())
    for source, binary in [("solver.c", "solver"),
                           ("tests/heuristic.c", "check")]:
        subprocess.run(["cc", "-O3", "-std=c99", str(ROOT / source),
                        "-o", str(work / binary)], check=True)
    helper = ('#define main solver_main\n#include '
              + json.dumps(str(ROOT / "solver.c")))
    helper += r'''
#undef main
int main(void) {
    state_t solved = {{0, 1, 2, 3, 4, 5, 6}, {0}};
    for (unsigned move = 0; move < MOVES; ++move) {
        state_t state = apply_move(solved, move);
        for (unsigned i = 0; i < 7; ++i) printf("%u", state.p[i] + 1U);
        for (unsigned i = 0; i < 7; ++i) printf("%u", state.o[i] + 1U);
        putchar('\n');
    }
}
'''
    subprocess.run(["cc", "-O3", "-x", "c", "-", "-o", str(work / "moves")],
                   input=helper, text=True, check=True)
    short = subprocess.check_output([str(work / "moves")],
                                    text=True).splitlines()
    solved = stickers("12345671111111")
    for move, value in zip(MOVES, short):
        assert apply_geometry(solved, move) == stickers(value), move
    values = [line.split("|", 1)[0] for line in
              (ROOT / "tests/solutions.txt").read_text().splitlines()
              if line and not line.startswith("#")]
    values += short + ["54721631111111"]
    cli, gui = BUILDER.build_source(False), BUILDER.build_source(True)
    assert "LED_MATRIX_0_" not in cli
    (work / "gui.s").write_text(gui)
    records = []

    def run(source, name, model="RV32_ISS", expected_status=0):
        path = work / f"{name}.s"
        path.write_text(source)
        result = subprocess.run([ripes, "--mode", "cli", "--src", str(path),
                                 "-t", "asm", "--proc", model, "--iret",
                                 "--timeout", "300000"], capture_output=True,
                                text=True, timeout=330)
        output = result.stdout.replace("\x00", "")
        (work / f"{name}.log").write_text(output + result.stderr)
        assert result.returncode == 0, output + result.stderr
        assert f"Program exited with code: {expected_status}" in output, output
        count = int(re.search(r"instructions retired\s*\n(\d+)", output)[1])
        return output.split("\nProgram exited with code:")[0], count

    for value in values:
        reference = subprocess.check_output([str(work / "solver"), value],
                                            text=True).strip()
        output, count = run(with_input(cli, value), "cli-" + value)
        checked = subprocess.run([str(work / "check"), "--check-solution",
                                  value, reference], input=output, text=True)
        assert checked.returncode == 0
        rendered, frames = checked_renderer(gui, value, reference)
        rendered_output, _ = run(rendered, "led-" + value)
        assert rendered_output == output
        records.append({"input": value, "frames": frames, "cli_iret": count})
        print(f"{value}: {frames} frames match geometry; "
              f"CLI {count} instructions", flush=True)
    for value in ["12345671111111", short[0], "21345671111111"]:
        reference = subprocess.check_output([str(work / "solver"), value],
                                            text=True).strip()
        rendered, _ = checked_renderer(gui, value, reference)
        output, _ = run(rendered, "pipeline-" + value, "RV32_5S")
        assert output.strip() == reference
        print(f"RV32_5S {value}: replay and pixel checks passed", flush=True)
    # A deliberately wrong move must be caught by the target's replay check.
    broken = with_input(cli, short[0]).replace("    mv s0, a0",
              "    la t0, search_path\n    sb zero, 0(t0)\n    mv s0, a0", 1)
    run(broken, "bad-path", expected_status=3)
    (work / "results.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Passed {len(values)} CLI/LED cases, 3 pipeline cases, "
          "and bad-path check.", flush=True)
    print(f"Artifacts: {work}", flush=True)


if __name__ == "__main__":
    main()

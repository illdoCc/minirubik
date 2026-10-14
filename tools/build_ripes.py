"""Select renderer blocks and combine the assembly for the pinned Ripes."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_source(render=False):
    # This Ripes build supports .equ, but not .if/.endif or .include.
    lines = []
    inside = False
    for line in (ROOT / "solver.s").read_text().splitlines():
        directive = line.split("#", 1)[0].strip()
        if directive == ".if RENDER":
            if inside:
                raise ValueError("Nested renderer blocks are not supported")
            inside = True
        elif directive == ".endif":
            if not inside:
                raise ValueError("Unmatched .endif")
            inside = False
        elif not inside or render:
            if directive.startswith(".equ RENDER,"):
                line = f".equ RENDER, {int(render)}"
            lines.append(line)
    if inside:
        raise ValueError("Unclosed renderer block")
    return (ROOT / "tables.s").read_text() + "\n" + "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true",
                        help="include LED code for a GUI with a 35x25 matrix")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(build_source(args.render))


if __name__ == "__main__":
    main()

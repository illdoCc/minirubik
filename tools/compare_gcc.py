"""Build RV32I ELF files and compare GCC -O2 with handwritten assembly."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from build_ripes import build_source

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ["-O2", "-march=rv32i", "-mabi=ilp32", "-ffreestanding",
         "-fno-pic", "-fno-pie", "-msmall-data-limit=0", "-mno-relax",
         "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
         "-ffunction-sections", "-fdata-sections", "-fstack-usage"]
LINKER = """OUTPUT_ARCH(riscv)
ENTRY(main)
SECTIONS {
    . = 0;
    .text : { *(.text.entry) *(.text .text.*) }
    . = 0x10000000;
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) }
    .data : { *(.data .data.* .sdata .sdata.*) }
    .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) }
    /DISCARD/ : { *(.eh_frame*) *(.comment) }
}
"""
START = """.section .text.entry
.globl main
main:
    la sp, call_stack_top
    call target_main
    li a7, 93
    ecall
.section .bss
.balign 16
call_stack:
    .zero 256
call_stack_top:
"""


def core_source():
    # Select the existing C functions without maintaining a second search.
    source = re.sub(r"/\*.*?\*/", "", (ROOT / "solver.c").read_text(),
                    flags=re.S)
    types = source[source.index("enum {"):
                   source.index("} search_frame_t;") + len("} search_frame_t;")]
    parts = ["#include <stdint.h>",
             "#define SEARCH_NODE_VISITED() ((void) 0)", types]
    for field, offset in [("permutation", 0), ("orientation", 30240),
                          ("permutation_distance", 34614),
                          ("orientation_distance", 39654), ("path", 40383)]:
        parts.append(f'_Static_assert(__builtin_offsetof(search_t, {field}) '
                     f'== {offset}, "table layout");')
    parts.append('_Static_assert(sizeof(search_t) == 40394, "table size");')
    for name in ["move_names", "source", "twist"]:
        match = re.search(r"^static const [^;]*\b" + name +
                          r"\[.*?;", source, re.M | re.S)
        assert match, name
        parts.append(match[0])
    for name in ["quarter_turn", "apply_move", "rank_components", "valid",
                 "search_limited", "search_optimal", "parse_state"]:
        match = re.search(r"^static [^;{]*\b" + name +
                          r"\([^;]*?\n\{.*?^\}", source, re.M | re.S)
        assert match, name
        body = match[0]
        if name == "quarter_turn":
            # Target replay needs modulo 3; operands are 0..2 for valid cubes.
            old = ("result.o[i] = (uint8_t) ((state.o[from] + "
                   "twist[face][i]) % 3U);")
            assert body.count(old) == 1
            body = body.replace(old,
                "uint8_t sum = state.o[from] + twist[face][i];\n"
                "        result.o[i] = sum >= 3U ? sum - 3U : sum;")
        parts.append(body)
    return "\n\n".join(parts) + "\n"


def gnu_source(source):
    # Ripes uses bytes for .align; GNU RISC-V .align uses powers of two.
    return re.sub(r"(?m)^(\s*)\.align\b", r"\1.balign", source)


def with_input(source, value):
    source, count = re.subn(r'(input_state:\s*\.asciz\s+")[^"]*(")',
                           lambda m: m[1] + value + m[2], source)
    assert count == 1
    return source


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, text=True,
                          capture_output=True, **kwargs)


def build(cc, work, value, variant, source=None):
    work.mkdir(parents=True, exist_ok=True)
    (work / "layout.ld").write_text(LINKER)
    if variant == "asm":
        text = with_input(source or build_source(False), value)
        (work / "ripes.s").write_text(text)
        (work / "program.s").write_text(gnu_source(text))
        inputs = [work / "program.s"]
    else:
        (work / "solver_core.h").write_text(core_source())
        (work / "program.c").write_text(
            (ROOT / "tools/ripes_target.c").read_text())
        tables = gnu_source((ROOT / "tables.s").read_text())
        tables = tables.replace("permutation_table:",
                                ".globl target_search\ntarget_search:\n"
                                "permutation_table:", 1)
        # The four tables followed by path[11] match search_t's C layout.
        tables += ("\n.zero 11\n.globl input_state\ninput_state:\n"
                   f'    .asciz "{value}"\n')
        (work / "data.s").write_text(tables)
        (work / "start.s").write_text(START)
        inputs = [work / "start.s", work / "program.c", work / "data.s"]
    elf = work / "solver.elf"
    command = [cc, *FLAGS, "-nostdlib", "-I", work,
               "-Wl,--no-relax,--gc-sections,-T," + str(work / "layout.ld"),
               "-Wl,-Map," + str(work / "solver.map"), *inputs, "-o", elf]
    (work / "build-command.json").write_text(json.dumps(
        [str(x) for x in command], indent=2) + "\n")
    result = run(command)
    (work / "build.log").write_text(result.stdout + result.stderr)
    prefix = str(cc).removesuffix("gcc")
    sections = run([prefix + "size", "-A", elf]).stdout
    (work / "size.txt").write_text(sections)
    sizes = {name: int(size) for name, size in
             re.findall(r"^(\.\S+)\s+(\d+)\s+\d+", sections, re.M)}
    disassembly = run([prefix + "objdump", "-d", "-M", "no-aliases",
                       elf]).stdout
    (work / "disassembly.txt").write_text(disassembly)
    symbols = run([prefix + "nm", elf]).stdout
    assert not re.search(r"__(?:mul|div|mod|udiv|umod)\w*", symbols)
    allowed = set("lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw "
                  "lbu lhu sb sh sw addi slti sltiu xori ori andi slli srli "
                  "srai add sub sll slt sltu xor srl sra or and fence "
                  "ecall ebreak".split())
    instructions = re.findall(r"^\s*[0-9a-f]+:\s+([0-9a-f]+)\s+(\S+)",
                              disassembly, re.M)
    assert instructions and all(len(bits) == 8 and op in allowed
                                for bits, op in instructions), instructions
    assert not run([prefix + "nm", "-u", elf]).stdout.strip()
    return elf, sizes


def simulate(ripes, source, kind, work):
    result = run([ripes, "--mode", "cli", "--src", source, "-t", kind,
                  "--proc", "RV32_ISS", "--iret", "--timeout", "300000"],
                 timeout=330)
    output = result.stdout.replace("\x00", "")
    (work / (kind + ".log")).write_text(output + result.stderr)
    assert "Program exited with code: 0" in output, output + result.stderr
    count = int(re.search(r"instructions retired\s*\n(\d+)", output)[1])
    return output.split("\nProgram exited with code:")[0].strip(), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ripes", type=Path)
    parser.add_argument("--cc", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cc = Path(shutil.which(args.cc) or args.cc).resolve()
    # Needed when using an unpacked toolchain instead of a system install.
    os.environ["PATH"] = str(cc.parent) + os.pathsep + os.environ["PATH"]
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    run(["cc", "-O3", ROOT / "tests/heuristic.c", "-o", work / "check"])
    run(["cc", "-O3", ROOT / "solver.c", "-o", work / "reference"])
    values = ["12345671111111", "25314672313211", "21345671111111",
              "54721631111111"]
    records = []
    for value in values:
        reference = run([work / "reference", value]).stdout.strip()
        for variant in ["asm", "gcc"]:
            case = work / value / variant
            elf, sizes = build(cc, case, value, variant)
            solution, count = simulate(args.ripes.resolve(), elf, "elf", case)
            run([work / "check", "--check-solution", value, reference],
                input=solution + "\n")
            record = {"input": value, "variant": variant,
                      "instructions": count, "text_bytes": sizes[".text"],
                      "static_bytes": sum(sizes.get(s, 0) for s in
                                          [".data", ".bss", ".rodata"]),
                      "solution": solution, "valid": True}
            assert record["static_bytes"] <= 128 * 1024
            if variant == "asm":
                text_solution, text_count = simulate(
                    args.ripes.resolve(), case / "ripes.s", "asm", case)
                assert text_solution == solution and text_count == count
                record["ripes_assembler_instructions"] = text_count
            records.append(record)
            print(record, flush=True)
    summary = {"compiler": run([cc, "--version"]).stdout.splitlines()[0],
               "ripes": str(args.ripes.resolve()),
               "ripes_sha256": hashlib.sha256(
                   args.ripes.read_bytes()).hexdigest(),
               "flags": FLAGS, "link_relaxation": False,
               "renderer": False, "records": records,
               "wall_seconds": time.monotonic() - started,
               "source_hashes": {name: hashlib.sha256(
                   (ROOT / name).read_bytes()).hexdigest() for name in
                   ["solver.c", "solver.s", "tables.s", "tools/ripes_target.c",
                    "tools/compare_gcc.py", "tools/build_ripes.py"]}}
    (work / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (work / "results.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print("Results:", work, flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BC5 experiment 0401 (exp 0381's build0381.py without its private include directory: no header changes): the shared
normal build's compile command for the private src/libs/bc5LleAgc.cpp into a private object, then the shared link command
with that object swapped in. The shared objects and the shared archive are only read. Warnings are counted by the caller.
Series d (2026-11-03) gives a private include directory too (exp 0379's zero_skip.hpp), put first on the path as exp 0388's
build0389z.py does. Series e also gives more private units (src/<rel>=<file>, each compiled with its own shared command
and swapped into the link) and a gate program (--gate <source> <out>): compiled with libNpCppWebApi.cpp's command and
linked with the emulator's link line, the private objects in, main.cpp.o out (exp 0328's pattern). Series e4 adds more
include directories (--inc <dir>, after the first, in order) and more gate programs, each compiled with the command of the
unit --like names (default libNpCppWebApi.cpp's).
usage (in the container): build0401.py <compdb.json> <private unit> <obj dir> <shared build dir> <out binary> [include dir]
                          [--inc <dir> ...] [src/<rel>=<file> ...] [--gate <source> <out> [--like src/<rel>] ...]"""
import json
import os
import shlex
import subprocess
import sys

UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
MAIN = "src/CMakeFiles/kyty_emulator.dir/main.cpp.o"
GATE_LIKE = "src/CMakeFiles/kyty_emulator.dir/libs/libNpCppWebApi.cpp.o"


def unit_obj(rel):
    """src/libs/x.cpp -> the emulator's object for it in the compdb."""
    assert rel.startswith("src/") and rel.endswith(".cpp"), rel
    return "src/CMakeFiles/kyty_emulator.dir/" + rel[len("src/"):] + ".o"


def clean_compile(cmd):
    argv, clean, skip = shlex.split(cmd), [], 0
    for a in argv:
        if skip:
            skip -= 1
            continue
        if a in ("-MT", "-MF"):
            skip = 1
            continue
        if a == "-MD":
            continue
        clean.append(a)
    return clean


def run(argv, build):
    print("+", " ".join(argv)[:240], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode


def compile_argv(db, unit_src, obj, inc=None, unit=UNIT):
    """inc: one include directory or a list of them, put first on the path in that order."""
    comp = next((clean_compile(e["command"]) for e in db if e.get("output") == unit), None)
    assert comp is not None, f"{unit} is not in the compdb"
    comp[comp.index("-o") + 1] = obj
    comp[comp.index("-c") + 1] = unit_src
    for k, d in enumerate([inc] if isinstance(inc, str) else list(inc or [])):
        comp.insert(1 + k, "-I" + d)
    return comp


def link_argv(db, obj, out, more=None):
    """obj replaces bc5LleAgc.cpp's object; more maps further emulator objects to their private ones."""
    swap = dict(more or {})
    swap[UNIT] = obj
    link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
    argv = [a for a in shlex.split(link) if a not in (":", "&&")]
    seen = {u: 0 for u in swap}
    for k, a in enumerate(argv):
        if a in swap:
            argv[k] = swap[a]
            seen[a] += 1
        elif a.startswith("-Wl,-Map="):
            argv[k] = "-Wl,-Map=" + out + ".map"
        elif a.startswith("--dependency-file="):
            argv[k] = "--dependency-file=" + out + ".d"
    for u, n in seen.items():
        assert n == 1, f"{u} appears {n} times in the link command"
    argv[argv.index("-o") + 1] = out
    return argv


def gate_argv(link, gate_obj, out):
    """The emulator's link line (private objects already in) with main.cpp.o out and the gate's object in."""
    assert link.count(MAIN) == 1, "main.cpp.o is not in the link line once"
    argv = [gate_obj if a == MAIN else a for a in link]
    for k, a in enumerate(argv):
        if a.startswith("-Wl,-Map="):
            argv[k] = "-Wl,-Map=" + out + ".map"
        elif a.startswith("--dependency-file="):
            argv[k] = "--dependency-file=" + out + ".d"
    argv[argv.index("-o") + 1] = out
    return argv


def parse_rest(rest):
    """[include dir] [--inc <dir> ...] [src/<rel>=<file> ...] [--gate <source> <out> [--like src/<rel>] ...]
    -> ([include dirs], {rel: file}, [(source, out, like unit object)])"""
    incs, units, gates = [], {}, []
    k = 0
    while k < len(rest):
        a = rest[k]
        if a == "--gate":
            like = GATE_LIKE
            if k + 3 < len(rest) and rest[k + 3] == "--like":
                like = unit_obj(rest[k + 4])
                gates.append((rest[k + 1], rest[k + 2], like))
                k += 5
                continue
            gates.append((rest[k + 1], rest[k + 2], like))
            k += 3
            continue
        if a == "--inc":
            assert incs, "--inc comes after the first include directory"
            incs.append(rest[k + 1])
            k += 2
            continue
        if a.startswith("src/") and "=" in a:
            rel, path = a.split("=", 1)
            assert rel not in units, rel
            units[rel] = path
        else:
            assert not incs and k == 0, ("the include directory comes first, once", a)
            incs.append(a)
        k += 1
    return incs, units, gates


def main():
    db_path, unit_src, obj_dir, build, out = sys.argv[1:6]
    inc, units, gates = parse_rest(sys.argv[6:])
    with open(db_path, encoding="utf-8") as f:
        db = json.load(f)
    os.makedirs(obj_dir, exist_ok=True)
    obj = os.path.join(obj_dir, "bc5LleAgc.cpp.o")
    if run(compile_argv(db, unit_src, obj, inc), build) != 0:
        print("== COMPILE FAILED", flush=True)
        return 2
    more = {}
    for rel, path in units.items():
        o = os.path.join(obj_dir, os.path.basename(rel) + ".o")
        if run(compile_argv(db, path, o, inc, unit_obj(rel)), build) != 0:
            print("== COMPILE FAILED", rel, flush=True)
            return 2
        more[unit_obj(rel)] = o
    link = link_argv(db, obj, out, more)
    rc = run(link, build)
    for k, (gate_src, gate_out, like) in enumerate(gates):
        if rc != 0:
            break
        gate_obj = os.path.join(obj_dir, "gate.o" if k == 0 else f"gate{k}.o")
        if run(compile_argv(db, gate_src, gate_obj, inc, like), build) != 0:
            print("== COMPILE FAILED gate", gate_src, flush=True)
            return 2
        rc = run(gate_argv(link, gate_obj, gate_out), build)
    return rc


if __name__ == "__main__":
    sys.exit(main())

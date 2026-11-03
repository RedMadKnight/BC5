#!/usr/bin/env python3
"""BC5 experiment 0401 (exp 0381's build0381.py without its private include directory: no header changes): the shared
normal build's compile command for the private src/libs/bc5LleAgc.cpp into a private object, then the shared link command
with that object swapped in. The shared objects and the shared archive are only read. Warnings are counted by the caller.
Series d (2026-11-03) gives a private include directory too (exp 0379's zero_skip.hpp), put first on the path as exp 0388's
build0389z.py does.
usage (in the container): build0401.py <compdb.json> <private unit> <obj dir> <shared build dir> <out binary> [include dir]"""
import json
import os
import shlex
import subprocess
import sys

UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"


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


def compile_argv(db, unit_src, obj, inc=None):
    comp = next((clean_compile(e["command"]) for e in db if e.get("output") == UNIT), None)
    assert comp is not None, f"{UNIT} is not in the compdb"
    comp[comp.index("-o") + 1] = obj
    comp[comp.index("-c") + 1] = unit_src
    if inc:
        comp.insert(1, "-I" + inc)
    return comp


def link_argv(db, obj, out):
    link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
    argv = [a for a in shlex.split(link) if a not in (":", "&&")]
    seen = 0
    for k, a in enumerate(argv):
        if a == UNIT:
            argv[k] = obj
            seen += 1
        elif a.startswith("-Wl,-Map="):
            argv[k] = "-Wl,-Map=" + out + ".map"
        elif a.startswith("--dependency-file="):
            argv[k] = "--dependency-file=" + out + ".d"
    assert seen == 1, f"{UNIT} appears {seen} times in the link command"
    argv[argv.index("-o") + 1] = out
    return argv


def main():
    db_path, unit_src, obj_dir, build, out = sys.argv[1:6]
    inc = sys.argv[6] if len(sys.argv) > 6 else None
    with open(db_path, encoding="utf-8") as f:
        db = json.load(f)
    os.makedirs(obj_dir, exist_ok=True)
    obj = os.path.join(obj_dir, "bc5LleAgc.cpp.o")
    if run(compile_argv(db, unit_src, obj, inc), build) != 0:
        print("== COMPILE FAILED", flush=True)
        return 2
    return run(link_argv(db, obj, out), build)


if __name__ == "__main__":
    sys.exit(main())

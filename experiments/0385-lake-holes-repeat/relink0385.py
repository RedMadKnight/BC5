#!/usr/bin/env python3
"""BC5 experiment 0385: the shared normal build's own link command with the private backend archive in place of the shared
one (exp 0381's build0381.py without its compile step: no host unit changes, and the backend's public headers keep their
ABI). The shared objects and the shared archive are only read.
usage: relink0385.py <compdb.json> <shared build dir> <shared archive> <private archive> <out binary>   (in the container)"""
import json, os, shlex, subprocess, sys

db_path, build, shared, private, out = sys.argv[1:6]
link = next(e["command"] for e in json.load(open(db_path)) if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
hits = 0
for k, a in enumerate(argv):
    if a == shared or os.path.basename(a) == os.path.basename(shared):
        argv[k] = private
        hits += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out + ".d"
assert hits == 1, f"the archive appears {hits} times in the link command"
argv[argv.index("-o") + 1] = out
sys.exit(subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode)

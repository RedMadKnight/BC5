#!/usr/bin/env bash
# BC5 experiment 0298: one private emulator, two units compiled from private copies, relinked against the shared
# normal build's objects (exp 0294's build0294.sh pattern):
#   - src/loader/systemContent.cpp (tree a3a786ff): PlayGo::Open also reads a PS5 "plgx" chunk table;
#   - src/libs/libPlayGo.cpp (tree 193cc47a): the title's PlayGo calls on stderr.
# The edits are edit0298.py's. Nothing shared is written; the result is ~/bc5-work/exp0298/kyty_emulator.
# usage: build0298.sh   (on the box; CPU only, nice 19, under the supervisor's BOX-LOCK)
set -u
E=$HOME/bc5-work/exp0298; R=$E/raw; S=$E/src; O=$E/obj
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus
mkdir -p "$R" "$S" "$O"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q "^supervisor | PlayGo" "$HOME/bc5-work/BOX-LOCK" || { echo "not under the supervisor's PlayGo lock: stop"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$K/src/loader/systemContent.cpp")" = a3a786ff ] || { echo "the tree's systemContent.cpp is not a3a786ff: stop"; exit 1; }
[ "$(m "$K/src/libs/libPlayGo.cpp")" = 193cc47a ] || { echo "the tree's libPlayGo.cpp is not 193cc47a: stop"; exit 1; }
[ "$(m "$B/src/kyty_emulator")" = 893f8ab4 ] || { echo "the shared normal binary is not 893f8ab4: stop"; exit 1; }
cp "$K/src/loader/systemContent.cpp" "$S/systemContent.cpp"; cp "$K/src/libs/libPlayGo.cpp" "$S/libPlayGo.cpp"
python3 -I "$E/edit0298.py" "$S/systemContent.cpp" "$S/libPlayGo.cpp" || { echo "edit failed"; exit 1; }
diff -u "$K/src/loader/systemContent.cpp" "$S/systemContent.cpp" > "$R/systemContent.diff"
diff -u "$K/src/libs/libPlayGo.cpp" "$S/libPlayGo.cpp" > "$R/libPlayGo.diff"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
cat > "$E/build0298.py" <<'PY'
import json, os, shlex, subprocess, sys
db, src, obj, out_dir, build, tree = sys.argv[1:7]
units = {"src/CMakeFiles/kyty_emulator.dir/loader/systemContent.cpp.o": ("loader", "systemContent.cpp"),
         "src/CMakeFiles/kyty_emulator.dir/libs/libPlayGo.cpp.o": ("libs", "libPlayGo.cpp")}
entries = json.load(open(db))
for out, (sub, name) in units.items():
    e = next(e for e in entries if e.get("output") == out)
    argv = shlex.split(e["command"])
    orig = os.path.join(tree, "src", sub, name)
    k = argv.index(orig) if orig in argv else argv.index(e["file"])
    argv[k] = os.path.join(src, name)
    argv[argv.index("-o") + 1] = os.path.join(obj, name + ".o")
    if "-MF" in argv:
        i = argv.index("-MF"); argv[i + 1] = os.path.join(obj, name + ".d")
    argv.insert(1, "-iquote" + os.path.join(tree, "src", sub))
    print("+ compile", name, flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=e.get("directory", build), check=True)
link = next(e["command"] for e in entries if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
n = 0
for k, a in enumerate(argv):
    if a in units:
        argv[k] = os.path.join(obj, units[a][1] + ".o"); n += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert n == 2, f"units replaced {n}"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
print("+ link", flush=True)
subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=True)
PY
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$E/build0298.py" "$E/compdb.json" "$S" "$O" "$E" "$B" "$K" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc"; [ $rc = 0 ] || { tail -30 "$R/build.out"; exit $rc; }
BIN=$E/kyty_emulator
ls -la "$BIN"; echo "md5 $(m "$BIN")"
echo "trace strings: $(strings "$BIN" | grep -c 'bc5 playgo: ')"
echo "shared binary after: $(m "$B/src/kyty_emulator"); tree after: $(m "$K/src/loader/systemContent.cpp") $(m "$K/src/libs/libPlayGo.cpp")"

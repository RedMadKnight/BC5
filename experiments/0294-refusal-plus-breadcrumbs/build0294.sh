#!/usr/bin/env bash
# BC5 experiment 0294: one private emulator from three verified parts, by a relink only (no compile):
#   - the shared normal build's objects as they are (binary 893f8ab4; ninja -t compdb -x gives the link command);
#   - exp 0281's breadcrumb unit ~/bc5-work/exp0281/obj/bc5LleAgc.cpp.o (built 2026-10-24 22:34 from
#     ~/bc5-work/exp0281/src/bc5LleAgc.bc.cpp, md5 55fa73a4 = the tree's bc5LleAgc.cpp 5bccbb80 + exp 0277's breadcrumbs);
#   - exp 0290's private backend archive ~/bc5-work/exp0290/build/libbc5_backend.a (md5 825ae1d1, the compute-ring refusal).
# Nothing shared is written. usage: build0294.sh   (on the box; CPU only, nice 19, under the BOX-LOCK)
set -u
E=$HOME/bc5-work/exp0294; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus
OBJ=$HOME/bc5-work/exp0281/obj/bc5LleAgc.cpp.o; SRC=$HOME/bc5-work/exp0281/src/bc5LleAgc.bc.cpp
A=$HOME/bc5-work/exp0290/build/libbc5_backend.a; SHARED_A=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
mkdir -p "$R"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 5bccbb80 ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80: stop"; exit 1; }
[ "$(m "$SRC")" = 55fa73a4 ] || { echo "exp 0281's source is not 55fa73a4: stop"; exit 1; }
[ "$(m "$A")" = 825ae1d1 ] || { echo "exp 0290's archive is not 825ae1d1: stop"; exit 1; }
[ "$(m "$B/src/kyty_emulator")" = 893f8ab4 ] || { echo "the shared normal binary is not 893f8ab4: stop"; exit 1; }
[ -s "$OBJ" ] || { echo "no $OBJ"; exit 1; }
echo "bvh exp 0294 | relink of ~/bc5-work/exp0294/kyty_emulator (shared objects + exp 0281 breadcrumb unit + exp 0290 archive; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0294 | relink" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
{ echo "tree bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp") $(stat -c %y "$K/src/libs/bc5LleAgc.cpp" | cut -c1-16)"
  echo "exp0281 unit $OBJ $(stat -c '%y %s' "$OBJ" | cut -c1-30) from $SRC md5 $(m "$SRC")"
  echo "exp0290 archive $A md5 $(m "$A") (shared $(m "$SHARED_A"))"
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator")"
  echo "shared bc5LleAgc object $(stat -c %y "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o" | cut -c1-16) md5 $(m "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
echo "== $(date +%T) compdb + relink"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/relink0294.py" <<'PY'
import json, os, shlex, subprocess, sys
db, obj, a_priv, out_dir, build = sys.argv[1:6]
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
link = next(e["command"] for e in json.load(open(db)) if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = na = 0
for k, a in enumerate(argv):
    if a == UNIT: argv[k] = obj; nu += 1
    elif a.endswith("/libbc5_backend.a"): argv[k] = a_priv; na += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert nu == 1 and na == 1, f"unit replaced {nu}, archive replaced {na}"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
print("+", " ".join(argv)[:200], "...", flush=True)
subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=True)
PY
distrobox enter ubuntu -- python3 -I "$E/relink0294.py" "$E/compdb.json" "$OBJ" "$A" "$E" "$B" > "$R/relink.out" 2>&1
rc=$?; echo "== $(date +%T) relink rc $rc"; [ $rc = 0 ] || { tail -20 "$R/relink.out"; exit $rc; }
BIN=$E/kyty_emulator
ls -la "$BIN"; m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "refusal string: $(strings "$BIN" | grep -c 'MEC check unverified'); breadcrumb strings: $(strings "$BIN" | grep -c 'breadcrumbs (exp 0277)')"
echo "shared binary after: $(m "$B/src/kyty_emulator"); shared archive after: $(m "$SHARED_A")"

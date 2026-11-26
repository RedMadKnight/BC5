#!/usr/bin/env bash
# BC5 experiment 0322: one private emulator, ~/bc5-work/exp0322/kyty_emulator, from the shared normal build's objects
# (ninja -t compdb -x gives the compile and link commands) with one unit replaced: bc5LleAgc.cpp as patch0322.py makes it
# from the tree's (md5 5bccbb80) - exp 0322's dcb-aware cross-ring dependency (refused compute buffers and dcbs with a dispatch) (no
# packet added). The backend archive: the shared one by default (549892e8, 2026-10-19 - it does NOT carry exp 0290's
# compute-ring refusal: F356 'not integrated'), or with an argument exp 0290's private archive (825ae1d1, the refusal, which
# this experiment needs), md5-checked as build0294.sh does; a previous kyty_emulator is kept beside the new one under its
# md5. Nothing shared is written; ~/src/KytyPlus is read.
# usage: build0322.sh [<backend archive>]   (on the box; CPU only, nice 19, under the BOX-LOCK; no emulator runs)
#   e.g. build0322.sh ~/bc5-work/exp0290/build/libbc5_backend.a   (the refusal in, as exp 0300 ran)
set -u
E=$HOME/bc5-work/exp0322; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
ARCH=${1:-}
ARCH_NOTE=""; ARCH_MD5=""
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$R" "$E/src" "$E/obj"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 5bccbb80 ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80: stop"; exit 1; }
case "$(m "$B/src/kyty_emulator")" in e62a97c6 | 226bcb82 | d02f4696) ;; *) echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not e62a97c6 (0298), 226bcb82 (the MangoHud integration, F367) or d02f4696 (the crash log, F383): stop"; exit 1 ;; esac
[ -s "$HERE/patch0322.py" ] || { echo "no patch0322.py beside this script"; exit 1; }
if [ -n "$ARCH" ]; then
  [ -s "$ARCH" ] || { echo "no archive $ARCH"; exit 1; }
  case "$ARCH" in */exp0290/build/libbc5_backend.a) [ "$(m "$ARCH")" = 825ae1d1 ] || { echo "exp 0290 archive is not 825ae1d1: stop"; exit 1; } ;;
    *) echo "unknown archive $ARCH (md5 $(m "$ARCH")): only exp 0290 is known here, stop"; exit 1 ;; esac
  ARCH_NOTE=" and exp 0290 archive"; ARCH_MD5=$(m "$ARCH")
fi
echo "bvh exp 0322 | build of ~/bc5-work/exp0322/kyty_emulator (one unit compiled + relink against the shared objects$ARCH_NOTE; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0322 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
{ echo "tree bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp") $(stat -c %y "$K/src/libs/bc5LleAgc.cpp" | cut -c1-16)"
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator")"
  echo "shared archive md5 $(m "$HOME/bc5-work/backend-ubuntu/libbc5_backend.a"); linked archive ${ARCH:-shared} md5 ${ARCH_MD5:-same}"
  echo "shared bc5LleAgc object $(stat -c %y "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o" | cut -c1-16) md5 $(m "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
echo "== $(date +%T) patch"
[ "$HERE/patch0322.py" -ef "$E/patch0322.py" ] || cp "$HERE/patch0322.py" "$E/patch0322.py"
distrobox enter ubuntu -- python3 -I "$E/patch0322.py" "$K" "$E/src" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "patch0322.py failed"; exit 1; }
cat "$R/patch.out"
cp "$E/src/patch_0322.diff" "$R/patch_0322.diff"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/build0322.py" <<'PY'
# exp 0272's build0272.py cut to one unit: compile the patched bc5LleAgc.cpp with the shared build's flags, link with the
# shared objects (the unit's object swapped), the map and the dependency file into the private directory.
import json, os, shlex, subprocess, sys
db_path, src, out_dir, build = sys.argv[1:5]
a_priv = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None  # a backend archive in place of the shared one
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
obj = os.path.join(out_dir, "obj", "bc5LleAgc.cpp.o")
db = json.load(open(db_path))
def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=True)
compiled = 0
link = None
for e in db:
    out = e.get("output", "")
    if out == UNIT:
        argv = shlex.split(e["command"])
        clean, skip = [], 0
        for a in argv:
            if skip: skip -= 1; continue
            if a in ("-MT", "-MF"): skip = 1; continue
            if a == "-MD": continue
            clean.append(a)
        clean[clean.index("-o") + 1] = obj
        clean[clean.index("-c") + 1] = src
        run(clean)
        compiled += 1
    elif out == "src/kyty_emulator":
        link = e["command"]
assert compiled == 1, f"compiled {compiled} units"
assert link is not None, "no link command"
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = na = 0
for k, a in enumerate(argv):
    if a == UNIT: argv[k] = obj; nu += 1
    elif a_priv and a.endswith("/libbc5_backend.a"): argv[k] = a_priv; na += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert nu == 1, f"unit replaced {nu} times"
assert not a_priv or na == 1, f"archive replaced {na} times"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
run(argv)
PY
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then  # the previous binary stays, under its md5, not run
  OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"
fi
echo "== $(date +%T) compile + link"
distrobox enter ubuntu -- python3 -I "$E/build0322.py" "$E/compdb.json" "$E/src/bc5LleAgc.cpp" "$E" "$B" "$ARCH" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) build rc $rc"; [ $rc = 0 ] || { grep -n "error\|Error" "$R/build.out" | head -20; tail -5 "$R/build.out"; exit $rc; }
grep -c "warning:" "$R/build.out" | sed 's/^/warnings: /'
ls -la "$BIN"; m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: unit 23bccaa3 + shared objects + archive ${ARCH:-shared} ${ARCH_MD5:-$(m "$HOME/bc5-work/backend-ubuntu/libbc5_backend.a")}" >> "$R/binaries.txt"
echo "patched source md5 $(m "$E/src/bc5LleAgc.cpp"); strings: ring deps $(strings "$BIN" | grep -c 'ring deps (exp 0322)'), refusal $(strings "$BIN" | grep -c 'MEC check unverified')"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want e62a97c6); shared object after: $(m "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"

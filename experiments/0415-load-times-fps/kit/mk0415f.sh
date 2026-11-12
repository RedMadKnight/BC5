#!/usr/bin/env bash
# BC5 exp 0415, build L3 = L2 + 0415-l3.diff (tag ls415d): three fast forms of the mapping maintenance under the device
# mutex, each default off with a "verify" mode (KYTY_BC5_WINDOW_FAST, a stopgap for the learned windows; KYTY_BC5_VMA_FAST;
# KYTY_BC5_NAMES_FAST), their CPU test test0415sync.cpp, and three counters (fast_diff, learned_apply, learned_changed).
# Incremental on the private tree. The L2 binaries are kept as bin-l2/ and bin-lean-l2/. Only ~/bc5-work/exp0415 is
# written. No emulator is started.
# usage (on the box): P_L2="<md5 of bin/kyty_emulator> <md5 of bin-lean/kyty_emulator>" P_DIFF=<sha256, 16 hex> bash mk0415f.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; HERE=$(cd "$(dirname "$0")" && pwd); LOCK=$W/BOX-LOCK
: "${P_L2:?the two L2 md5s}"
m() { md5sum < "$1" | cut -d' ' -f1; }
stop() { echo "mk0415f STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$E/bin/kyty_emulator") $(m "$E/bin-lean/kyty_emulator")" = "$P_L2" ] || stop "the binaries in place are not L2's"
[ ! -e "$E/bin-l2" ] && [ ! -e "$E/bin-lean-l2" ] || stop "bin-l2 exists: L3 was built already"
[ "$(sha256sum < "$HERE/0415-l3.diff" | cut -c1-16)" = "${P_DIFF:?the diff sha256, 16 hex}" ] || stop "the diff is not the one sent"
for f in tree-l3.md5 test0415.cpp test0415apr.cpp test0415sync.cpp; do [ -s "$HERE/$f" ] || stop "no $f in the kit"; done
LINE="exp 0415 | token $(date +%s)$$ | exp 0415: incremental build L3 under exp0415, CPU only, no emulator | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || stop "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0415f-$$.new; al=$LOCK.0415f-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; stop "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; stop "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || stop "the lock does not read back as ours"
release() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0415f-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; echo "lock released"; fi; }
trap release EXIT
die() { echo "mk0415f STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
(cd "$E/tree" && if git -c core.autocrlf=false apply --check "$HERE/0415-l3.diff" 2> /dev/null; then git -c core.autocrlf=false apply --whitespace=nowarn "$HERE/0415-l3.diff"; fi)
bad=0
while read -r sum f; do [ "$(md5sum < "$E/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree-l3.md5"
[ "$bad" = 0 ] || die "$bad edited files differ from the laptop's tree"
echo "tree: $(wc -l < "$HERE/tree-l3.md5") edited files match the laptop's"
T=$E/raw/test-l3; mkdir -p "$T" "$E/new" || die mkdir
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$E/tree/src" "$HERE/test0415.cpp" -o "$T/test0415" < /dev/null > "$T/test0415-build.out" 2>&1 ||
    die "test0415 does not build: $(grep -m2 'error' "$T/test0415-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree/src" "$HERE/test0415apr.cpp" -o "$T/test0415apr" < /dev/null > "$T/test0415apr-build.out" 2>&1 ||
    die "test0415apr does not build: $(grep -m2 'error' "$T/test0415apr-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$E/tree/src" "$HERE/test0415sync.cpp" -o "$T/test0415sync" < /dev/null > "$T/test0415sync-build.out" 2>&1 ||
    die "test0415sync does not build: $(grep -m2 'error' "$T/test0415sync-build.out" | cut -c1-200 | tr '\n' ' ')"
distrobox enter ubuntu -- "$T/test0415sync" < /dev/null > "$T/sync.out" 2>&1 || die "test0415sync failed: $(grep -m3 FAIL "$T/sync.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$T/test0415" off < /dev/null > "$T/off.out" 2>&1 || die "test0415 off failed: $(grep -m2 FAIL "$T/off.out" | cut -c1-160 | tr '\n' ' ')"
rm -f "$T/stat.txt"
distrobox enter ubuntu -- "$T/test0415" on "$T/stat.txt" < /dev/null > "$T/on.out" 2>&1 || die "test0415 on failed: $(grep -m2 FAIL "$T/on.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$T/test0415apr" "$T" < /dev/null > "$T/apr.out" 2>&1 || die "test0415apr failed: $(grep -m3 -A1 FAIL "$T/apr.out" | cut -c1-160 | tr '\n' ' ')"
for o in off on apr sync; do grep -q '^test0415\(apr\|sync\)\?: \([0-9]*\) of \2; end$' "$T/$o.out" || die "no end marker in $o.out"; done
echo "cpu tests: $(tail -1 "$T/off.out") | $(tail -1 "$T/on.out") | $(tail -1 "$T/apr.out") | $(tail -1 "$T/sync.out")"
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$E/build-$v
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build-l3.log" 2>&1 || { grep -m5 -E "error:" "$d.build-l3.log" | cut -c1-300; die "the build ($v)"; }
    for s in KYTY_BC5_APR_POSIX "tag ls415b" KYTY_BC5_LOAD_STAT KYTY_BC5_SEMA_TARGETED_WAKE apr_fallback ds_views hold_probe KYTY_BC5_WINDOW_FAST KYTY_BC5_VMA_FAST KYTY_BC5_NAMES_FAST learned_changed; do grep -aqF -- "$s" "$d/src/kyty_emulator" || die "the $v binary lacks [$s]"; done
    cp -p "$d/src/kyty_emulator" "$E/new/kyty_emulator.$v" || die "copy"
done
mv -T "$E/bin" "$E/bin-l2" && mv -T "$E/bin-lean" "$E/bin-lean-l2" && mkdir "$E/bin" "$E/bin-lean" &&
    mv -T "$E/new/kyty_emulator.normal" "$E/bin/kyty_emulator" && mv -T "$E/new/kyty_emulator.lean" "$E/bin-lean/kyty_emulator" || die "placing the binaries"
{ printf '%s  bin/kyty_emulator\n' "$(m "$E/bin/kyty_emulator")"; printf '%s  bin-lean/kyty_emulator\n' "$(m "$E/bin-lean/kyty_emulator")"; } > "$E/built.md5"
echo "$(date '+%F %T') done; L3 normal $(m "$E/bin/kyty_emulator" | cut -c1-8), lean $(m "$E/bin-lean/kyty_emulator" | cut -c1-8); L2 kept in bin-l2, bin-lean-l2"

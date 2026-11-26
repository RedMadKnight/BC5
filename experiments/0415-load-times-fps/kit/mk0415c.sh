#!/usr/bin/env bash
# BC5 exp 0415, build L1b = L1 + 0415-l1b-apr.diff (tag ls415b): KYTY_BC5_APR_POSIX=random|direct, default off: APR reads
# by open + posix_fadvise(POSIX_FADV_RANDOM) + pread, and with "direct" straight into the guest's pages. Incremental:
# the private tree of mk0415b.sh keeps its build directories, so ninja rebuilds libAmpr.cpp and links. The L1 binaries
# are kept as bin-l1/ and bin-lean-l1/. Only ~/bc5-work/exp0415 is written. No emulator is started.
# usage (on the box): P_L1="<md5 of bin/kyty_emulator> <md5 of bin-lean/kyty_emulator>" bash mk0415c.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; HERE=$(cd "$(dirname "$0")" && pwd); LOCK=$W/BOX-LOCK
: "${P_L1:?the two L1 md5s}"
m() { md5sum < "$1" | cut -d' ' -f1; }
stop() { echo "mk0415c STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$E/bin/kyty_emulator") $(m "$E/bin-lean/kyty_emulator")" = "$P_L1" ] || stop "the binaries in place are not L1's"
[ ! -e "$E/bin-l1" ] && [ ! -e "$E/bin-lean-l1" ] || stop "bin-l1 exists: L1b was built already"
[ "$(sha256sum < "$HERE/0415-l1b-apr.diff" | cut -c1-16)" = "${P_DIFF:?the diff sha256, 16 hex}" ] || stop "the diff is not the one sent"
LINE="exp 0415 | token $(date +%s)$$ | exp 0415: incremental build L1b under exp0415, CPU only, no emulator | $(date '+%F %T')"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || stop "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0415c-$$.new; al=$LOCK.0415c-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; stop "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; stop "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || stop "the lock does not read back as ours"
release() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0415c-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; echo "lock released"; fi; }
trap release EXIT
die() { echo "mk0415c STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
(cd "$E/tree" && git -c core.autocrlf=false apply -p2 --whitespace=nowarn "$HERE/0415-l1b-apr.diff") || die "the diff does not apply"
[ "$(m "$E/tree/src/libs/libAmpr.cpp" | cut -c1-8)" = "${P_UNIT:?the edited unit md5, 8 hex}" ] || die "the edited unit is not the laptop's"
mkdir -p "$E/new" || die mkdir
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$E/build-$v
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build-l1b.log" 2>&1 || { grep -m5 -E "error:" "$d.build-l1b.log" | cut -c1-300; die "the build ($v)"; }
    for s in KYTY_BC5_APR_POSIX "tag ls415b" KYTY_BC5_LOAD_STAT KYTY_BC5_SEMA_TARGETED_WAKE; do grep -aqF -- "$s" "$d/src/kyty_emulator" || die "the $v binary lacks [$s]"; done
    cp -p "$d/src/kyty_emulator" "$E/new/kyty_emulator.$v" || die "copy"
done
mv -T "$E/bin" "$E/bin-l1" && mv -T "$E/bin-lean" "$E/bin-lean-l1" && mkdir "$E/bin" "$E/bin-lean" &&
    mv -T "$E/new/kyty_emulator.normal" "$E/bin/kyty_emulator" && mv -T "$E/new/kyty_emulator.lean" "$E/bin-lean/kyty_emulator" || die "placing the binaries"
{ printf '%s  bin/kyty_emulator\n' "$(m "$E/bin/kyty_emulator")"; printf '%s  bin-lean/kyty_emulator\n' "$(m "$E/bin-lean/kyty_emulator")"; } > "$E/built.md5"
echo "$(date '+%F %T') done; L1b normal $(m "$E/bin/kyty_emulator" | cut -c1-8), lean $(m "$E/bin-lean/kyty_emulator" | cut -c1-8); L1 kept in bin-l1, bin-lean-l1"

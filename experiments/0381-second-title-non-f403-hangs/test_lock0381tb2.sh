#!/usr/bin/env bash
# BC5 exp 0381: test build 2's lock (REVIEW-PORTS-28), laptop only. The real scripts on a tree under a tb2-test- path, reached through TB2_ROOT: HOME and PATH are not changed.
# Stand-ins (pgrep, setsid, distrobox) load only through TB2_FAKE, and a hook at a named point plays the competitor. tb2run0381.sh's own step runs through PC_REMOTE, a local shell.
# What it does not show: Linux's ln, mv -T and find on the box, ssh, or a real process lifecycle. usage (in a git checkout, clean): bash test_lock0381tb2.sh
HERE=$(cd "$(dirname "$0")" && pwd)
[ -z "$(git -C "$HERE" status --short -- .)" ] || { echo "NOT RUN: uncommitted changes here, and the tests take HEAD"; exit 3; }
echo "testing $(git -C "$HERE" rev-parse HEAD)"
T=$(mktemp -d "${TMPDIR:-/tmp}/tb2-test-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
export T TB2_ROOT=$T/home TB2_FAKE=$T/fake.sh
W=$TB2_ROOT/bc5-work; E=$W/exp0381; ED=experiments/0381-second-title-non-f403-hangs; IN=$E/in-tb2/$ED
FOREIGN='other session | its run'; TOK=abc; LINE="top exp 0381 | test build 2 | token $TOK"
PLUS=$'\n'"$FOREIGN"
printf '#!/usr/bin/env bash\nexec bash -c "$1"\n' > "$T/remote"; chmod +x "$T/remote"
fail=0; pass=0
ok() { pass=$((pass + 1)); echo "ok: $1"; }
bad() { fail=1; echo "FAIL: $1"; [ -z "${2:-}" ] || echo "$2" | tail -3; }
hk() { H="$1"; C="$2"; }
base() {
    rm -rf "$TB2_ROOT"; H=none; C=:
    mkdir -p "$W/_SaveData/PPSA03671" "$W/exp0379" "$E/tb2/bin" "$E/tb2/raw" "$E/tb2/play" "$E/wd/_SaveData/PPSA03671" "$E/saves-sample/PPSA03671" "$IN"
    echo a > "$W/_SaveData/PPSA03671/a.dat"; cp "$W/_SaveData/PPSA03671/a.dat" "$E/saves-sample/PPSA03671/"; : > "$W/exp0379/in-D2.cmd"; echo old > "$E/wd/_SaveData/PPSA03671/old.dat"
    echo 'RayTracing.PPSA03671=on' > "$E/input-rton.cfg"; printf '#!/bin/sh\n' > "$E/tb2/bin/kyty_emulator"; cp "$E/tb2/bin/kyty_emulator" "$E/tb2/play-pkg-0381tb2s.sh"; chmod +x "$E/tb2/bin/kyty_emulator" "$E/tb2/play-pkg-0381tb2s.sh"
    for f in lock0381tb2.inc pathcheck0381tb2.inc boxcap0381.sh; do git -C "$HERE" show "HEAD:./$f" > "$IN/$f"; done
    echo sentinel > "$E/in-tb2/old-file"
    echo q > "$W/BOX-QUEUE"; echo "$LINE" > "$W/BOX-LOCK"; : > "$T/calls"; rm -f "$T/emu"
    git -C "$HERE" show HEAD:./start0381tb2.sh > "$T/start.sh"
    git -C "$HERE" show HEAD:./snapshot0381tb2.sh > "$T/snap.sh"
    git -C "$HERE" show HEAD:./build0381tb2.sh > "$IN/build0381tb2.sh"; git -C "$HERE" show HEAD:./pins0381tb2.env > "$IN/pins0381tb2.env"
}
fake() {
    cat > "$TB2_FAKE" <<EOF
pgrep() { [ -e "\$T/emu" ]; }
setsid() { :; }
distrobox() { echo distrobox >> "\$T/calls"; }
case "\$1" in $H) $C ;; esac
EOF
}
lock() { cat "$W/BOX-LOCK" 2> /dev/null; }
out() { fake; o=$("$@" 2>&1); rc=$?; }
tstart() { out bash "$T/start.sh" TS "${1:-$TOK}"; }
tsnap() { out bash "$T/snap.sh" "${1:-$TOK}"; }
tbuild() { out env TB2_TOKEN="${1:-$TOK}" TB2_PINS="$IN/pins0381tb2.env" bash "$IN/build0381tb2.sh"; }
tclaim() { out env PC_REMOTE="$T/remote" TB2_MAIN=HEAD TB2_NP=HEAD bash "$HERE/tb2run0381.sh" build "$T/o"; }
tpins() { rm -rf "$T/o"; mkdir -p "$T/o"; out env PC_REMOTE="$T/remote" bash "$HERE/tb2run0381.sh" pins "$T/o" pins0381tb2r.env; }
trec() { rm -rf "$T/o"; mkdir -p "$T/o"; echo "$TOK" > "$T/o/token"; out env PC_REMOTE="$T/remote" bash "$HERE/tb2run0381.sh" recover "$T/o"; }
trel() { rm -rf "$T/o"; mkdir -p "$T/o"; echo "$TOK" > "$T/o/token"; out env PC_REMOTE="$T/remote" bash "$HERE/tb2run0381.sh" release "$T/o"; }
says() { case "$o" in *"$1"*) return 0 ;; esac; return 1; }
extracted() { [ -e "$E/in-tb2/$ED/lock0381tb2.inc" ] && [ ! -e "$E/in-tb2/old-file" ]; }
aside() { ls -d "$E"/in-tb2-before-* > /dev/null 2>&1; }
nothing() { [ -e "$E/in-tb2/old-file" ] && ! aside; }

# Claim before the transfer.
base; : > "$W/BOX-LOCK"; hk after-claim 'cp "$TB2_LOCK" "$T/at-claim"; [ -e "$W/exp0381/in-tb2/old-file" ] && echo before > "$T/seen"'; tclaim
[ -e "$T/seen" ] && [ "$(sed -n 1p "$T/at-claim" | cut -d' ' -f1-9)" = 'top exp 0381 | test build 2 | token' ] && aside && [ -e "$E/in-tb2/$ED/build0381tb2.sh" ] && ok "claim: the line is ours while the tree has not moved, and the tree crosses after it" || bad "claim order" "$o"
grep -qF ': private build, CPU only' "$W/BOX-QUEUE" && [ "$(wc -l < "$T/at-claim")" = 1 ] && says 'a shared pin differs' && [ -z "$(lock)" ] && ok "claim: one exact line and its record; the build that follows fails on its pins and gives the line back" || bad "claim line" "$o"
base; : > "$W/BOX-LOCK"; hk before-claim 'echo "$FOREIGN" > "$TB2_LOCK"'; export FOREIGN; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && nothing && says 'foreign lock' && ok "competing claim after a free look: stopped, its line kept, nothing moved" || bad "competing claim" "$o"
base; : > "$W/BOX-LOCK"; hk after-aside 'echo "$FOREIGN" > "$a"'; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && nothing && says 'arrived during the claim' && ok "a writer into the old lock during the claim: its line goes back" || bad "aside writer" "$o"
base; : > "$W/BOX-LOCK"; hk after-aside 'echo "$FOREIGN" > "$TB2_LOCK"'; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && nothing && says 'lost the claim' && ok "a new lock file during the claim: the hard link fails, it stays" || bad "new lock" "$o"
base; echo "$FOREIGN" > "$W/BOX-LOCK"; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && nothing && [ "$(cat "$W/BOX-QUEUE")" = q ] && ok "a held lock: stopped, nothing recorded" || bad "held lock" "$o"
base; : > "$W/BOX-LOCK"; hk after-claim 'echo "$FOREIGN" > "$TB2_LOCK"'; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && nothing && [ "$(cat "$W/BOX-QUEUE")" = q ] && ok "ownership lost before the rename: nothing moved, the foreign line stays" || bad "loss before rename" "$o"
base; : > "$W/BOX-LOCK"; hk before-extract 'echo "$FOREIGN" > "$TB2_LOCK"'; tclaim
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && [ ! -e "$E/in-tb2" ] && [ "$(cat "$W/BOX-QUEUE")" = q ] && ok "ownership lost before the extraction: nothing extracted, the foreign line stays" || bad "loss before extract" "$o"
base; : > "$W/BOX-LOCK"; hk before-extract 'printf "%s\n%s\n" "$TB2_LINE" "$FOREIGN" > "$TB2_LOCK"'; tclaim
[ "$rc" != 0 ] && [ ! -e "$E/in-tb2" ] && lock | grep -qxF "$FOREIGN" && ok "a foreign line next to ours before the extraction: stopped, both kept" || bad "mixed before extract" "$o"

# The pin read fills the two FILL pins without a commit.
base; : > "$W/BOX-LOCK"; mkdir -p "$TB2_ROOT/src/KytyPlus/src/libs"; echo p > "$W/play-pkg.sh"; echo l > "$TB2_ROOT/src/KytyPlus/src/libs/libC.cpp"; tpins
PP=$(md5sum < "$W/play-pkg.sh" | cut -c1-8); LB=$(md5sum < "$TB2_ROOT/src/KytyPlus/src/libs/libC.cpp" | cut -c1-8)
[ "$rc" = 0 ] && grep -qx "PIN_PLAY_PKG=$PP" "$T/o/pins-read.env" && grep -qx "PIN_LIBC=$LB" "$T/o/pins-read.env" && ! grep -q '=FILL$' "$T/o/pins-read.env" && [ -z "$(lock)" ] && ok "pins: the two filled from the box, the lock given back" || bad "pins fill" "$o"
base; : > "$W/BOX-LOCK"; tpins
[ "$rc" = 3 ] && [ ! -e "$T/o/pins-read.env" ] && [ -z "$(lock)" ] && ok "pins: a file missing on the box: stopped, no pins, the lock given back" || bad "pins missing" "$o"
base; echo "$FOREIGN" > "$W/BOX-LOCK"; tpins
[ "$rc" = 3 ] && [ ! -e "$T/o/pins-read.env" ] && [ "$(lock)" = "$FOREIGN" ] && ok "pins: a foreign line: stopped, it stays" || bad "pins foreign" "$o"
# The snapshot.
base; rm -rf "$E/saves-sample"; tsnap
[ "$rc" = 0 ] && [ -f "$E/saves-sample/PPSA03671/a.dat" ] && [ "$(lock)" = "$LINE" ] && ok "snapshot: made under the exact line, which stays" || bad "snapshot" "$o"
base; rm -rf "$E/saves-sample"; echo "$LINE$PLUS" > "$W/BOX-LOCK"; tsnap
[ "$rc" = 4 ] && [ ! -e "$E/saves-sample" ] && [ "$(lock)" = "$LINE$PLUS" ] && ok "snapshot: a foreign line next to ours: nothing made, both kept" || bad "snapshot mixed" "$o"
base; rm -rf "$E/saves-sample"; tsnap other
[ "$rc" = 4 ] && [ ! -e "$E/saves-sample" ] && [ "$(lock)" = "$LINE" ] && ok "snapshot: another token: nothing made" || bad "snapshot token" "$o"
base; rm -rf "$E/saves-sample"; : > "$W/BOX-LOCK"; tsnap
[ "$rc" = 4 ] && [ ! -e "$E/saves-sample" ] && [ -z "$(lock)" ] && ok "snapshot: an empty lock is not ownership" || bad "snapshot empty" "$o"
base; rm -rf "$E/saves-sample"; hk before-snapshot 'echo "$FOREIGN" > "$TB2_LOCK"'; tsnap
[ "$rc" = 4 ] && [ ! -e "$E/saves-sample.tmp" ] && [ ! -e "$E/saves-sample" ] && [ "$(lock)" = "$FOREIGN" ] && ok "snapshot: ownership lost before the copy: nothing written" || bad "snapshot loss" "$o"

# The smoke's starter.
base; tstart
[ "$rc" = 0 ] && grep -q distrobox "$T/calls" && [ -z "$(lock)" ] && [ -e "$E/wd/_SaveData/PPSA03671/a.dat" ] && [ ! -e "$E/wd/_SaveData/PPSA03671/old.dat" ] && grep -q 'smoke ended' "$W/BOX-QUEUE" && ok "starter: launched under the line, then only that line cleared" || bad "starter" "$o"
base; echo "$LINE$PLUS" > "$W/BOX-LOCK"; tstart
[ "$rc" = 4 ] && [ ! -s "$T/calls" ] && [ -e "$E/wd/_SaveData/PPSA03671/old.dat" ] && [ "$(lock)" = "$LINE$PLUS" ] && ok "starter: a foreign line next to ours: no delete, no launch, both kept" || bad "starter mixed" "$o"
base; : > "$W/BOX-LOCK"; tstart
[ "$rc" = 4 ] && [ ! -s "$T/calls" ] && [ -e "$E/wd/_SaveData/PPSA03671/old.dat" ] && [ -z "$(lock)" ] && ok "starter: an empty lock is not ownership" || bad "starter empty" "$o"
base; hk before-launch 'echo "$FOREIGN" > "$TB2_LOCK"'; tstart
[ "$rc" = 4 ] && [ ! -s "$T/calls" ] && [ "$(lock)" = "$FOREIGN" ] && ok "starter: ownership lost before the launch: no launch, the foreign line stays" || bad "starter loss" "$o"
base; hk at-launch 'echo "$FOREIGN" > "$TB2_LOCK"'; tstart
[ "$rc" = 4 ] && [ ! -s "$T/calls" ] && [ "$(lock)" = "$FOREIGN" ] && ! grep -q 'smoke ended' "$W/BOX-QUEUE" && ok "starter: ownership lost after its queue line: no launch, the foreign line stays, no outcome recorded" || bad "starter loss at launch" "$o"
base; hk before-release 'echo "$FOREIGN" > "$TB2_LOCK"'; tstart
grep -q distrobox "$T/calls" && [ "$(lock)" = "$FOREIGN" ] && says 'left as it is' && ok "starter: ownership lost before the release: the foreign line stays" || bad "release loss" "$o"
base; hk before-launch 'printf "%s\n%s\n" "$TB2_LINE" "$FOREIGN" > "$TB2_LOCK"'; tstart
[ "$rc" = 4 ] && [ ! -s "$T/calls" ] && [ "$(lock)" = "$LINE$PLUS" ] && ok "starter: a line added before the launch: stopped, both kept" || bad "starter added" "$o"

# The build's failure path: its pins do not match this tree, so it fails for real.
base; tbuild
[ "$rc" != 0 ] && says 'a shared pin differs' && [ -z "$(lock)" ] && grep -q 'build FAILED' "$W/BOX-QUEUE" && ok "build: a failure gives back its own line and records it" || bad "build failure" "$o"
base; echo "$LINE$PLUS" > "$W/BOX-LOCK"; tbuild
[ "$rc" = 4 ] && [ "$(lock)" = "$LINE$PLUS" ] && ! grep -q 'build FAILED' "$W/BOX-QUEUE" && ok "build: a foreign line next to ours: stopped, both kept, no record" || bad "build mixed" "$o"
base; echo sentinel > "$W/BOX-LOCK"; tbuild
[ "$rc" = 4 ] && [ "$(lock)" = sentinel ] && [ "$(cat "$W/BOX-QUEUE")" = q ] && ok "build: another owner's lock: sentinel kept, queue untouched" || bad "build foreign" "$o"
base; hk before-release 'echo "$FOREIGN" > "$TB2_LOCK"'; tbuild
[ "$rc" != 0 ] && [ "$(lock)" = "$FOREIGN" ] && ok "build: failure cleanup after a loss: the foreign line stays" || bad "cleanup loss" "$o"

# The release.
base; trel
[ "$rc" = 0 ] && [ -z "$(lock)" ] && grep -q ': released' "$W/BOX-QUEUE" && ok "release: the exact line goes" || bad "release" "$o"
base; echo "$LINE$PLUS" > "$W/BOX-LOCK"; trel
[ "$(lock)" = "$LINE$PLUS" ] && ! grep -q ': released' "$W/BOX-QUEUE" && ok "release: a foreign line next to ours: nothing cleared" || bad "release mixed" "$o"
base; echo "$FOREIGN" > "$W/BOX-LOCK"; trel
[ "$(lock)" = "$FOREIGN" ] && ok "release: another owner: nothing cleared" || bad "release foreign" "$o"

# The rollback.
rolled() { ls -d "$E"/tb2.rolledback-* > /dev/null 2>&1; }
base; echo marker > "$W/live"; trec
[ "$rc" = 0 ] && rolled && [ ! -e "$E/tb2" ] && [ -z "$(lock)" ] && [ -f "$W/_SaveData/PPSA03671/a.dat" ] && [ -d "$E/wd" ] && grep -q 'rollback done' "$W/BOX-QUEUE" && [ -f "$(ls -d "$E"/tb2.rolledback-*)/bin/kyty_emulator" ] && ok "rollback: renames only, the saves and wd as they were, our line cleared" || bad "rollback" "$o"
base; : > "$W/BOX-LOCK"; trec
[ "$rc" = 0 ] && rolled && [ -z "$(lock)" ] && grep -q "token $TOK-recovery-" "$W/BOX-QUEUE" && ok "rollback: an empty lock is claimed first, under a new token" || bad "rollback claim" "$o"
base; echo "$FOREIGN" > "$W/BOX-LOCK"; trec
[ "$rc" != 0 ] && ! rolled && [ "$(lock)" = "$FOREIGN" ] && ok "rollback: another owner: nothing renamed" || bad "rollback foreign" "$o"
base; echo "$LINE$PLUS" > "$W/BOX-LOCK"; trec
[ "$rc" != 0 ] && ! rolled && [ "$(lock)" = "$LINE$PLUS" ] && ok "rollback: a foreign line next to ours: nothing renamed" || bad "rollback mixed" "$o"
base; touch "$T/emu"; trec
[ "$rc" != 0 ] && ! rolled && [ "$(lock)" = "$LINE" ] && says 'an emulator runs' && ok "rollback: an emulator runs: nothing renamed, nothing signalled" || bad "rollback emulator" "$o"
base; mkdir -p "$T/target"; echo keep > "$T/target/m"; cmd //c mklink //J "$(cygpath -w "$E/tb2/lnk")" "$(cygpath -w "$T/target")" > /dev/null; trec
[ "$rc" != 0 ] && ! rolled && [ "$(cat "$T/target/m")" = keep ] && says 'holds a link' && [ -z "$(lock)" ] && ok "rollback: a link inside a target: nothing renamed" || bad "rollback link" "$o"
base; hk before-rename 'echo "$FOREIGN" > "$TB2_LOCK"'; trec
[ "$rc" != 0 ] && ! rolled && [ "$(lock)" = "$FOREIGN" ] && ok "rollback: ownership lost before the rename: nothing renamed" || bad "rollback loss" "$o"
echo "passed $pass, failed $fail"
exit $fail

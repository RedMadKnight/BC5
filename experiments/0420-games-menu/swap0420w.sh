#!/usr/bin/env bash
# BC5 exp 0420: the shared swap to build W with the games menu (the maintainer, 2026-11-15, relayed by the top session:
# his one yes, asked for and given; after the night series, on the top's GO, after the race fix and the replug).
# What it changes, each kept first as *.before-W under ~/bc5-work/exp0420/before-W and read back:
#   - the shared host tree ~/src/KytyPlus: patch 0001 27b6416f (B) reversed, 0001-W-menu.patch (S_NEW) applied; every
#     patched file checked against tree-W-menu.md5 (the laptop's replay: B + exp 0419's W + exp 0420's menu)
#   - the shared backend source (~/bc5-work/d19/export/backend): the files the private W source differs in, from
#     ~/bc5-work/exp0413/p/backend-src; the shared archive rebuilt and required to equal the private one
#   - both shared emulators rebuilt in place (ninja kyty_emulator, nice 19); compared with the private W+menu builds
#   - the launchers: play-any.sh (exp 0420: one launcher, the lean stop after its refusing checks), lean-session.sh
#     (one owner), play-t1.sh (BC5_GAME_DIR); the shared bc5-mount (uninstall, the install fixes)
# Not touched: play-pkg.sh, bc5-run.env, the desktop shortcuts, the saves, ~/bc5-data. No launch, no GPU.
#   swap0420w.sh dry      the checks and every diff; changes nothing, takes no lock
#   swap0420w.sh apply    the swap (one lock line); a failure restores what was changed and checks the restore
#   swap0420w.sh undo     everything back from the .before-W copies (no rebuild needed: the binaries are copied back)
# Run on the box from the kit directory (~/bc5-work/exp0420/swapW): this script, 0001-B.patch, 0001-W-menu.patch,
# tree-W-menu.md5, play-any.sh, play-t1.sh, lean-session.sh.
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
BK=$W/exp0420/before-W
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
PB=$P/backend-src; PARCH=$P/backend-build/libbc5_backend.a
PIN_NORMAL=51af1ed78e84291caf5ee042ea82c46d; PIN_LEAN=59894428d98ed94918d09a31002c1e3b
PIN_ARCH=75e303357610fee8d1d205bdc88c031c; PIN_OLD=27b6416f; S_NEW=101555c7; TREE_LIST=e7f6224a
PRIV_N=10e3ef15; PRIV_L=98ba9468   # the private W+menu builds (exp 0420's round, after the name fix)
L_ANY=$W/play-any.sh; L_T1=$W/play-t1.sh; L_LS=$W/lean-session.sh; BM=$W/bc5-tools-ubuntu/release/bc5-mount
PBM=$W/exp0420/bc5-tools/release/bc5-mount
ANY_OLD="92c090c5 1cd59817"; ANY_NEW=fc7a1395; T1_OLD=48238ccd; T1_NEW=e943bd8f; LS_NEW=189885ea; BM_NEW=be372d39
ST=$W/lean-session.state; BASE_REV=f266548
# tests only (test-swap0420w.sh): a file that sets the pins above for stand-ins
[ -n "${SWAP_PINS:-}" ] && . "$SWAP_PINS"
m() { md5sum < "$1" | cut -d' ' -f1; }
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color "$BASE_REV" | md5sum | cut -c1-8; }
say() { echo "swap0420w: $*"; }
stop() { say "STOP: $*"; exit 1; }
lean_active() { # a lean session: a state not restored yet, or a live owner
  local o pid st s
  [ -s "$ST" ] && { echo "the state $ST names: $(tr '\n' ' ' < "$ST")"; return 0; }
  o=$(cat "$ST.owner/pid" 2> /dev/null) || return 1
  pid=${o%% *}; st=${o#* }
  s=$(cat "/proc/$pid/stat" 2> /dev/null) || return 1
  s=${s##*) }
  # shellcheck disable=SC2086
  set -- $s
  [ "${20:-}" = "$st" ] && { echo "the lean session of $pid runs"; return 0; }
  return 1
}
quiet_box() { # no emulator, no launcher, no lean session
  local why
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; return 1; }
  pgrep -f 'play-any.sh|play-pkg.sh|play-t1.sh' > /dev/null && { echo "a launcher runs: $(pgrep -af 'play-any.sh|play-pkg.sh|play-t1.sh' | head -2 | cut -c1-120)"; return 1; }
  why=$(lean_active) && { echo "a lean session is active: $why"; return 1; }
  return 0
}
in_list() { local x=$1; shift; for y in "$@"; do [ "$x" = "$y" ] && return 0; done; return 1; }
# the backend files the private W source differs in (relative paths); a file only on one side stops the swap
backend_files() {
  local out
  out=$(diff -rq -x build -x '*.o' "$BSRC" "$PB" 2> /dev/null)
  printf '%s\n' "$out" | grep -q '^Only in' && { printf '%s\n' "$out" | grep '^Only in' >&2; return 1; }
  printf '%s\n' "$out" | sed -n "s|^Files $BSRC/\(.*\) and $PB/.* differ\$|\1|p"
}
checks() { # every check that needs no lock; prints the findings, returns 1 at the first that fails
  local f n bad
  for f in 0001-B.patch 0001-W-menu.patch tree-W-menu.md5 play-any.sh play-t1.sh lean-session.sh; do [ -f "$HERE/$f" ] || { echo "the kit lacks $f"; return 1; }; done
  [ "$(m8 "$HERE/0001-B.patch")" = "$PIN_OLD" ] && [ "$(m8 "$HERE/0001-W-menu.patch")" = "$S_NEW" ] && [ "$(m8 "$HERE/tree-W-menu.md5")" = "$TREE_LIST" ] || { echo "the kit's patches or list are not the pins"; return 1; }
  [ "$(grep -c 'exp 0372' "$HERE/0001-W-menu.patch")" = 5 ] && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-W-menu.patch" || { echo "the new patch lacks exp 0372's pad audio route"; return 1; }
  [ "$(m8 "$HERE/play-any.sh")" = "$ANY_NEW" ] && [ "$(m8 "$HERE/play-t1.sh")" = "$T1_NEW" ] && [ "$(m8 "$HERE/lean-session.sh")" = "$LS_NEW" ] && [ "$(m8 "$PBM")" = "$BM_NEW" ] || { echo "the kit's launchers or the private bc5-mount are not the pins"; return 1; }
  for f in play-any.sh play-t1.sh lean-session.sh; do bash -n "$HERE/$f" || { echo "$f does not parse"; return 1; }; done
  grep -l 'BC5_GUARD_MAP_RULE\|BC5_GUARD_PRT_BG\|LEARNED\|learned-windows' "$HERE/play-any.sh" "$HERE/play-t1.sh" && { echo "a new launcher names MAP_RULE, PRT_BG or the learned windows"; return 1; }
  "$PBM" uninstall --help > /dev/null 2>&1 || { echo "the private bc5-mount has no uninstall"; return 1; }
  [ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m "$ARCH")" = "$PIN_ARCH" ] || { echo "the shared binaries or archive are not B's: $(m8 "$NB") $(m8 "$LB") $(m8 "$ARCH")"; return 1; }
  [ "$(tdiff)" = "$PIN_OLD" ] || { echo "the shared tree's diff is $(tdiff), not $PIN_OLD"; return 1; }
  (cd "$K" && git apply -R --check --whitespace=nowarn "$HERE/0001-B.patch") || { echo "0001-B does not reverse on the shared tree"; return 1; }
  bad=0; n=0
  while read -r s f; do n=$((n + 1)); [ "$(m "$P/tree/$f" 2> /dev/null)" = "$s" ] || { echo "  the private tree differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree-W-menu.md5"
  [ "$bad" = 0 ] || { echo "$bad of $n files of the private tree are not the laptop's W+menu"; return 1; }
  echo "the private tree: $n of $n patched files are the laptop's W+menu"
  [ "$(m8 "$P/build-normal/src/kyty_emulator")" = "$PRIV_N" ] && [ "$(m8 "$P/build-lean/src/kyty_emulator")" = "$PRIV_L" ] || { echo "the private builds are not $PRIV_N / $PRIV_L: $(m8 "$P/build-normal/src/kyty_emulator") $(m8 "$P/build-lean/src/kyty_emulator")"; return 1; }
  [ -f "$PARCH" ] && [ -f "$BBLD/build.ninja" ] || { echo "no private archive at $PARCH or no $BBLD/build.ninja"; return 1; }
  BFILES=$(backend_files) || { echo "the private backend source has files the shared one has not (or the reverse)"; return 1; }
  in_list "$(m8 "$L_ANY")" $ANY_OLD || { echo "the shared play-any.sh is $(m8 "$L_ANY"), not one of $ANY_OLD"; return 1; }
  [ "$(m8 "$L_T1")" = "$T1_OLD" ] || { echo "the shared play-t1.sh is $(m8 "$L_T1"), not $T1_OLD"; return 1; }
  [ -x "$BM" ] || { echo "no shared bc5-mount at $BM"; return 1; }
  return 0
}
show() {
  echo "shared now: normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$ARCH"), tree diff $(tdiff); play-any $(m8 "$L_ANY"), play-t1 $(m8 "$L_T1"), lean-session $(m8 "$L_LS"), bc5-mount $(m8 "$BM")"
  echo "after the swap: normal = private $PRIV_N expected, lean = private $PRIV_L expected, archive = private $(m8 "$PARCH"), tree diff $S_NEW; play-any $ANY_NEW, play-t1 $T1_NEW, lean-session $LS_NEW, bc5-mount $BM_NEW"
  echo "backend source files from the private W source: ${BFILES:-none}"
  for f in $BFILES; do echo "  $f: $(m8 "$BSRC/$f") -> $(m8 "$PB/$f")"; done
  echo "== play-any.sh"; diff -u "$L_ANY" "$HERE/play-any.sh" | sed -n '1,400p'
  echo "== play-t1.sh"; diff -u "$L_T1" "$HERE/play-t1.sh"
  echo "== lean-session.sh"; if [ -f "$L_LS" ]; then diff -u "$L_LS" "$HERE/lean-session.sh" | sed -n '1,60p'; [ "$(m8 "$L_LS")" = "$LS_NEW" ] && echo "(the same)"; else echo "(none now)"; fi
}
RESTORE_FROM=""
restore() {
  say "restoring from $BK ($*)"
  local ok=1 f
  cp -p "$BK/kyty_emulator.normal" "$NB" && cp -p "$BK/kyty_emulator.lean" "$LB" || ok=0
  [ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] || { echo "restore: binaries read $(m8 "$NB") $(m8 "$LB")"; ok=0; }
  cp -p "$BK/libbc5_backend.a" "$ARCH" || ok=0
  [ "$(m "$ARCH")" = "$PIN_ARCH" ] || { echo "restore: the archive reads $(m8 "$ARCH")"; ok=0; }
  for f in $(cat "$BK/backend-files.txt" 2> /dev/null); do cp -p "$BK/backend/$f" "$BSRC/$f" || ok=0; done
  [ -z "$(cat "$BK/backend-files.txt" 2> /dev/null)" ] || [ "$(cd "$BSRC" && md5sum $(cat "$BK/backend-files.txt") | md5sum | cut -c1-8)" = "$(cat "$BK/backend-files.md5")" ] || { echo "restore: the backend source does not read back"; ok=0; }
  if [ "$(tdiff)" != "$PIN_OLD" ]; then
    (cd "$K" && git reset -q && git apply -R --whitespace=nowarn "$HERE/0001-W-menu.patch" && git apply --whitespace=nowarn "$HERE/0001-B.patch" && git add -N .) || echo "restore: the patches could not put the tree back"
  fi
  [ "$(tdiff)" = "$PIN_OLD" ] || { echo "restore: the tree's diff reads $(tdiff)"; ok=0; }
  for f in play-any.sh play-t1.sh lean-session.sh; do [ -f "$BK/$f" ] && { cp -p "$BK/$f" "$W/$f" || ok=0; }; done
  [ -f "$BK/bc5-mount" ] && { cp -p "$BK/bc5-mount" "$BM" || ok=0; }
  if [ "$ok" = 1 ]; then say "restored and read back (B's binaries, archive and tree; the launchers); the build directories' objects are newer than the tree: rebuild before the next change"; return 0; fi
  say "THE RESTORE IS INCOMPLETE; the lock is KEPT. State: normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$ARCH"), tree $(tdiff); copies in $BK"
  trap - EXIT; exit 2
}
fail() { restore "FAILED: $*"; exit 1; }
case "${1:-dry}" in
  dry)
    why=$(quiet_box) || say "note: $why (apply would refuse now)"
    checks || stop "a check failed: nothing done"
    show
    say "dry: every check passed; nothing changed" ;;
  apply)
    why=$(quiet_box) || stop "$why: nothing done"
    checks > "$HERE/checks-apply.out" 2>&1 || { cat "$HERE/checks-apply.out"; stop "a check failed: nothing done"; }
    . "$N/chainlock0417.inc"
    chain_claim "exp 0420: the shared swap to W with the games menu (patch $S_NEW, the backend archive, both emulators, the launchers, bc5-mount; CPU only, no emulator)" 45 || stop "the lock: nothing done"
    trap chain_release EXIT
    [ -e "$BK" ] && stop "$BK exists already (an earlier swap?): nothing done"
    mkdir -p "$BK/backend" || stop "cannot make $BK"
    echo "$(date '+%F %T') before: $(show | head -1)" | tee "$BK/before.txt"
    cp -p "$NB" "$BK/kyty_emulator.normal" && cp -p "$LB" "$BK/kyty_emulator.lean" && cp -p "$ARCH" "$BK/libbc5_backend.a" || stop "copies failed"
    for f in play-any.sh play-t1.sh lean-session.sh; do [ -f "$W/$f" ] && { cp -p "$W/$f" "$BK/$f" || stop "copy of $f failed"; }; done
    cp -p "$BM" "$BK/bc5-mount" || stop "copy of bc5-mount failed"
    printf '%s\n' $BFILES > "$BK/backend-files.txt"
    for f in $BFILES; do mkdir -p "$BK/backend/$(dirname "$f")" && cp -p "$BSRC/$f" "$BK/backend/$f" || stop "copy of $f failed"; done
    [ -z "$BFILES" ] || (cd "$BSRC" && md5sum $BFILES | md5sum | cut -c1-8) > "$BK/backend-files.md5"
    [ "$(m "$BK/kyty_emulator.normal")" = "$PIN_NORMAL" ] && [ "$(m "$BK/kyty_emulator.lean")" = "$PIN_LEAN" ] && [ "$(m "$BK/libbc5_backend.a")" = "$PIN_ARCH" ] || stop "the copies do not read back"
    for f in play-any.sh play-t1.sh lean-session.sh; do [ ! -f "$W/$f" ] || cmp -s "$W/$f" "$BK/$f" || stop "the copy of $f does not read back"; done
    cmp -s "$BM" "$BK/bc5-mount" || stop "the copy of bc5-mount does not read back"
    echo "copies in $BK, read back"
    # the tree
    (cd "$K" && git apply -R --whitespace=nowarn "$HERE/0001-B.patch" && git apply --whitespace=nowarn "$HERE/0001-W-menu.patch" && git add -N .) || fail "applying the patch"
    bad=0
    while read -r s f; do [ "$(m "$K/$f")" = "$s" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree-W-menu.md5"
    [ "$bad" = 0 ] || fail "$bad patched files differ from the laptop's tree"
    [ "$(tdiff)" = "$S_NEW" ] || fail "the tree's diff is $(tdiff), not $S_NEW"
    echo "tree: $(wc -l < "$HERE/tree-W-menu.md5") patched files match; diff $S_NEW"
    # the backend
    for f in $BFILES; do cp "$PB/$f" "$BSRC/$f" && cmp -s "$PB/$f" "$BSRC/$f" || fail "putting $f in"; done
    pgrep '^kyty_emulator' > /dev/null && fail "an emulator started before the backend build"
    echo "== $(date +%T) backend"
    distrobox enter ubuntu -- sh -c "cd '$BBLD' && nice -n 19 ninja" < /dev/null > "$BK/build-backend.out" 2>&1 || { grep -m5 "error:" "$BK/build-backend.out"; fail "the backend build"; }
    [ "$(m "$ARCH")" = "$(m "$PARCH")" ] || fail "the rebuilt archive is $(m8 "$ARCH"), not the private $(m8 "$PARCH")"
    echo "backend archive: $(m8 "$ARCH") (the private one; was $(m8 "$BK/libbc5_backend.a"))"
    for v in normal lean; do
      d=$W/kytyplus-build; [ "$v" = lean ] && d=$W/kytyplus-build-lean
      pgrep '^kyty_emulator' > /dev/null && fail "an emulator started before the $v build"
      echo "== $(date +%T) $v"
      distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$BK/build-$v.out" 2>&1 || { grep -m5 "error:" "$BK/build-$v.out"; fail "build $v"; }
    done
    [ "$(m "$NB")" != "$PIN_NORMAL" ] && [ "$(m "$LB")" != "$PIN_LEAN" ] || fail "a binary did not change"
    for b in "$NB" "$LB"; do for s in "Uninstall game" "Installed games" KYTY_BC5_MENU_DIR; do grep -aqF -- "$s" "$b" || fail "$b lacks [$s]"; done; done
    grep -aqF KYTY_BC5_SWITCH_DEFAULTS "$NB" || fail "the normal binary lacks KYTY_BC5_SWITCH_DEFAULTS"
    [ "$(m "$ARCH")" = "$(m "$PARCH")" ] && [ "$(tdiff)" = "$S_NEW" ] || fail "the archive or the tree changed during the builds"
    same="DIFFERENT from the private builds ($PRIV_N / $PRIV_L)"
    [ "$(m8 "$NB")" = "$PRIV_N" ] && [ "$(m8 "$LB")" = "$PRIV_L" ] && same="byte-identical to the private builds"
    # the launchers and bc5-mount, last
    quiet=$(quiet_box) || fail "$quiet before the launchers"
    for f in play-any.sh play-t1.sh lean-session.sh; do
      cp "$HERE/$f" "$W/$f.W-new" && chmod 755 "$W/$f.W-new" && mv -fT "$W/$f.W-new" "$W/$f" || fail "putting $f in"
    done
    cp "$PBM" "$BM.W-new" && chmod 755 "$BM.W-new" && mv -fT "$BM.W-new" "$BM" || fail "putting bc5-mount in"
    [ "$(m8 "$L_ANY")" = "$ANY_NEW" ] && [ "$(m8 "$L_T1")" = "$T1_NEW" ] && [ "$(m8 "$L_LS")" = "$LS_NEW" ] && [ "$(m8 "$BM")" = "$BM_NEW" ] || fail "the launchers or bc5-mount do not read back"
    bash -n "$L_ANY" && bash -n "$L_T1" && bash -n "$L_LS" || fail "a launcher does not parse"
    "$BM" uninstall --help > /dev/null 2>&1 || fail "the shared bc5-mount has no uninstall"
    echo "$(date '+%F %T') after: normal $(m8 "$NB"), lean $(m8 "$LB") ($same), archive $(m8 "$ARCH"), tree $S_NEW; play-any $ANY_NEW, play-t1 $T1_NEW, lean-session $LS_NEW, bc5-mount $BM_NEW" | tee "$BK/after.txt"
    echo "undo: bash $HERE/swap0420w.sh undo (puts back every file from $BK; then rebuild before the next change)" ;;
  undo)
    [ -d "$BK" ] && [ -f "$BK/kyty_emulator.normal" ] || stop "no $BK: nothing to undo"
    why=$(quiet_box) || stop "$why: nothing done"
    . "$N/chainlock0417.inc"
    chain_claim "exp 0420: undo of the shared swap to W (copies back from $BK; CPU only, no emulator)" 15 || stop "the lock: nothing done"
    trap chain_release EXIT
    restore "the undo"
    echo "$(date '+%F %T') undone: normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$ARCH"), tree $(tdiff); play-any $(m8 "$L_ANY"), play-t1 $(m8 "$L_T1"), lean-session $(m8 "$L_LS"), bc5-mount $(m8 "$BM")" | tee "$BK/undone.txt"
    mv -T "$BK" "$BK.undone-$(date +%Y%m%d-%H%M)" ;;
  *) echo "usage: swap0420w.sh [dry | apply | undo]"; exit 1 ;;
esac

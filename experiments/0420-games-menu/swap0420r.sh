#!/usr/bin/env bash
# BC5 exp 0420: Recent lists only paths that exist (the maintainer, 2026-11-15 13:05: "recent nie może być elementów,
# które nie istnieją"). One file changes against the shared W with the games menu: hostMenu.cpp 0f324fa4 -> a6314317
# (mkmenu0420.py's 26th edit: LoadRecent drops a path that does not exist and writes recent.txt without it); patch
# 0001 101555c7 -> ba617454. No launcher, no backend change.
#   swap0420r.sh dry      the checks; changes nothing, no lock
#   swap0420r.sh private  the private tree (exp0413/p) gets the file, normal and lean rebuilt: the compile check
#   swap0420r.sh apply    the shared tree gets the file, both shared emulators rebuilt; copies *.before-R first
#   swap0420r.sh undo     the shared file and both shared binaries back from the copies
# Kit (~/bc5-work/exp0420/swapR): this script, hostMenu.cpp (a6314317). CPU only, no emulator, one lock line a stage.
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
F=src/graphics/presentation/hostMenu.cpp; OLD=0f324fa4; NEW=a6314317; P_OLD=101555c7; P_NEW=ba617454
BK=$W/exp0420/before-R
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
SN_OLD=bab1ce79; SL_OLD=c4aca9af
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
say() { echo "swap0420r: $*"; }
stop() { say "STOP: $*"; exit 1; }
quiet() {
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; return 1; }
  pgrep -f 'play-any.sh|play-pkg.sh|play-astro.sh' > /dev/null && { echo "a launcher runs"; return 1; }
  [ -s "$W/lean-session.state" ] && { echo "a lean session is active"; return 1; }
  return 0
}
build() { # directory, name, log
  distrobox enter ubuntu -- sh -c "cd '$1' && nice -n 19 ninja kyty_emulator" < /dev/null > "$3" 2>&1 || { grep -m8 "error:" "$3" | cut -c1-240; return 1; }
  echo "$2: $(m8 "$1/src/kyty_emulator"), warnings in hostMenu.cpp: $(grep -c 'hostMenu.cpp.*warning:' "$3")"
}
[ "$(m8 "$HERE/hostMenu.cpp")" = "$NEW" ] || stop "the kit's hostMenu.cpp is $(m8 "$HERE/hostMenu.cpp"), not $NEW"
case "${1:-dry}" in
  dry)
    echo "shared: $F $(m8 "$K/$F"), tree $(tdiff), normal $(m8 "$NB"), lean $(m8 "$LB"); private: $F $(m8 "$P/tree/$F")"
    why=$(quiet) || say "note: $why"
    diff -u "$K/$F" "$HERE/hostMenu.cpp"
    say "dry: nothing changed" ;;
  private)
    why=$(quiet) || stop "$why"
    s=$(m8 "$P/tree/$F"); [ "$s" = "$OLD" ] || [ "$s" = "$NEW" ] || stop "the private $F is $s, not $OLD"
    . "$N/chainlock0417.inc"
    chain_claim "exp 0420: Recent without missing paths, the private build (hostMenu.cpp, normal and lean; CPU only)" 15 || stop "the lock"
    trap chain_release EXIT
    mkdir -p "$P/before-R" && { [ -e "$P/before-R/hostMenu.cpp" ] || cp -p "$P/tree/$F" "$P/before-R/hostMenu.cpp"; } || stop "copy"
    cp "$HERE/hostMenu.cpp" "$P/tree/$F" || stop "put"
    for v in normal lean; do build "$P/build-$v" "private $v" "$P/build-$v.R.log" || { cp -p "$P/before-R/hostMenu.cpp" "$P/tree/$F"; stop "the private $v build failed; the private file is put back"; }; done ;;
  apply)
    why=$(quiet) || stop "$why"
    [ "$(m8 "$K/$F")" = "$OLD" ] && [ "$(tdiff)" = "$P_OLD" ] && [ "$(m8 "$NB")" = "$SN_OLD" ] && [ "$(m8 "$LB")" = "$SL_OLD" ] || stop "the shared state is not W with the menu: $(m8 "$K/$F") $(tdiff) $(m8 "$NB") $(m8 "$LB")"
    [ -e "$BK" ] && stop "$BK exists already"
    . "$N/chainlock0417.inc"
    chain_claim "exp 0420: Recent without missing paths into the shared builds (hostMenu.cpp, both emulators rebuilt; CPU only)" 20 || stop "the lock"
    trap chain_release EXIT
    mkdir -p "$BK" && cp -p "$K/$F" "$BK/hostMenu.cpp" && cp -p "$NB" "$BK/kyty_emulator.normal" && cp -p "$LB" "$BK/kyty_emulator.lean" || stop "copies"
    [ "$(m8 "$BK/hostMenu.cpp")" = "$OLD" ] && [ "$(m8 "$BK/kyty_emulator.normal")" = "$SN_OLD" ] && [ "$(m8 "$BK/kyty_emulator.lean")" = "$SL_OLD" ] || stop "the copies do not read back"
    back() {
      cp -p "$BK/hostMenu.cpp" "$K/$F"; cp -p "$BK/kyty_emulator.normal" "$NB"; cp -p "$BK/kyty_emulator.lean" "$LB"
      [ "$(m8 "$K/$F")" = "$OLD" ] && [ "$(m8 "$NB")" = "$SN_OLD" ] && [ "$(m8 "$LB")" = "$SL_OLD" ] && [ "$(tdiff)" = "$P_OLD" ] && say "restored and read back" || { say "THE RESTORE IS INCOMPLETE; the lock is KEPT"; trap - EXIT; exit 2; }
    }
    cp "$HERE/hostMenu.cpp" "$K/$F" && [ "$(tdiff)" = "$P_NEW" ] || { back; stop "the tree's diff is $(tdiff), not $P_NEW"; }
    for v in normal lean; do
      d=$W/kytyplus-build; [ "$v" = lean ] && d=$W/kytyplus-build-lean
      build "$d" "shared $v" "$BK/build-$v.out" || { back; stop "the shared $v build failed"; }
    done
    for b in "$NB" "$LB"; do grep -aqF "Uninstall game" "$b" || { back; stop "$b lacks the menu"; }; done
    echo "$(date '+%F %T') after: tree $P_NEW, normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/swap0420r.sh undo" | tee "$BK/after.txt" ;;
  undo)
    [ -f "$BK/kyty_emulator.normal" ] || stop "no $BK"
    why=$(quiet) || stop "$why"
    . "$N/chainlock0417.inc"
    chain_claim "exp 0420: undo of Recent without missing paths (copies back; CPU only)" 5 || stop "the lock"
    trap chain_release EXIT
    cp -p "$BK/hostMenu.cpp" "$K/$F" && cp -p "$BK/kyty_emulator.normal" "$NB" && cp -p "$BK/kyty_emulator.lean" "$LB" || stop "copy back failed"
    echo "undone: tree $(tdiff), normal $(m8 "$NB"), lean $(m8 "$LB")"
    mv -T "$BK" "$BK.undone-$(date +%Y%m%d-%H%M)" ;;
  *) echo "usage: swap0420r.sh [dry | private | apply | undo]"; exit 1 ;;
esac

#!/usr/bin/env bash
# BC5 exp 0415: private copies of the two SHARED binaries (candidate B), for a control run on exactly what the
# maintainer plays without starting anything from the shared build directories (lesson R51: a difference between
# builds is reported only after a control on the shared build in the same window).
# The shared files are only read. Written: ~/bc5-work/exp0415/bin-b/, bin-lean-b/, built-b.md5.
# usage (on the box): P_B="<md5 prefix of the shared normal> <md5 prefix of the shared lean>" bash getb0415.sh
#   (2026-11-14, from the top session: normal 51af1ed7, lean 59894428)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415
: "${P_B:?the two md5 prefixes}"
m() { md5sum < "$1" | cut -d' ' -f1; }
stop() { echo "getb0415 STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
SN=$W/kytyplus-build/src/kyty_emulator; SL=$W/kytyplus-build-lean/src/kyty_emulator
[ -f "$SN" ] && [ -f "$SL" ] || stop "no shared binaries"
set -- $P_B
[ $# = 2 ] && [ ${#1} -ge 8 ] && [ ${#2} -ge 8 ] || stop "P_B is two md5 prefixes of at least 8 hex"
MN=$(m "$SN"); ML=$(m "$SL")
case "$MN" in "$1"*) ;; *) stop "the shared normal is $MN, not $1" ;; esac
case "$ML" in "$2"*) ;; *) stop "the shared lean is $ML, not $2" ;; esac
[ ! -e "$E/bin-b" ] && [ ! -e "$E/bin-lean-b" ] || stop "bin-b exists already"
mkdir "$E/bin-b" "$E/bin-lean-b" && cp -p "$SN" "$E/bin-b/kyty_emulator" && cp -p "$SL" "$E/bin-lean-b/kyty_emulator" || stop "copy"
[ "$(m "$E/bin-b/kyty_emulator")" = "$MN" ] && [ "$(m "$E/bin-lean-b/kyty_emulator")" = "$ML" ] || stop "the copies do not read back"
{ printf '%s  bin-b/kyty_emulator\n' "$MN"; printf '%s  bin-lean-b/kyty_emulator\n' "$ML"; } > "$E/built-b.md5"
for s in KYTY_BC5_LOAD_STAT KYTY_BC5_FRAME_STAT BC5_DIRECT_DCB_WAIT_MS BC5_DIRECT_CHAIN_HOLD_US KYTY_BC5_SEMA_TARGETED_WAKE; do
  for b in "$E/bin-b/kyty_emulator" "$E/bin-lean-b/kyty_emulator"; do grep -aqF -- "$s" "$b" || echo "note: $b has no text [$s]"; done
done
echo "getb0415 done: bin-b $MN, bin-lean-b $ML"

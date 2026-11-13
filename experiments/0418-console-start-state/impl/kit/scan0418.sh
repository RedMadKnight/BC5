#!/usr/bin/env bash
# BC5 exp 0418: the trap scan (impl/README.md result 4). Read-only on the captures, CPU only, no emulator, about two
# minutes. One lock line, claimed atomically as mk0418.sh claims it (a hard link; R35), released on every exit.
# It runs trap0418.py over ~/bc5-data/captures (exp 0401's audit set) and lists where shader dumps lie (for a later
# s_trap check). Writes only ~/bc5-work/exp0418/raw/trap-scan.txt and the lock line.
# usage (on the box): bash ~/bc5-work/exp0418/kit/scan0418.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0418; HERE=$(cd "$(dirname "$0")" && pwd); LOCK=$W/BOX-LOCK; ID=$E/scan.lock.line; C=$HOME/bc5-data/captures
OUT=$E/raw/trap-scan.txt
stop() { echo "scan0418 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0418s-$$.new a=$LOCK.0418s-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    line="exp 0418 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
    mkdir "$c" 2> /dev/null || stop "another claim runs, or $c was left behind"
    fail() { rm -f "$t"; rmdir "$c"; stop "$1"; }
    printf '%s\n' "$line" > "$t" || fail "cannot write $t"
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        { [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; } && fail "$LOCK is not a plain file"
        [ -s "$LOCK" ] && fail "foreign lock: $(cat "$LOCK")"
        mv -T "$LOCK" "$a" || fail "the lock moved under us"
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        [ -s "$a" ] || rm -f "$a"
        fail "lost the claim to: $(cat "$LOCK" 2> /dev/null)"
    fi
    if [ -s "$a" ]; then
        local w; w=$(cat "$a"); mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim: $w"
    fi
    rm -f "$a" "$t"; rmdir "$c" || stop "cannot remove $c"
    printf '%s\n' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"
    own || stop "the lock does not read back as ours"
    echo "claimed: $line"
}
release() {
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "scan0418: the lock could not be released"; return 1; fi
    echo "scan0418: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
[ -s "$HERE/trap0418.py" ] || stop "no trap0418.py in the kit"
[ -d "$C" ] || stop "no $C"
mkdir -p "$E/raw" || stop "mkdir"
claim "exp 0418: trap scan of the captures (read-only), CPU only" 10
trap release EXIT
{
    echo "== $(date '+%F %T') trap0418.py (md5 $(md5sum < "$HERE/trap0418.py" | cut -c1-8)) in $C"
    (cd "$C" && nice -n 19 python3 -I "$HERE/trap0418.py")
    echo "== shader dumps: files and directories named like shaders, depth 4"
    find "$C" "$W" -maxdepth 4 \( -iname '*shader*' -o -iname '*.sb' -o -iname '*pgm*' \) 2> /dev/null | grep -v '/kytyplus\|/tree/\|/build' | sed 's#/[^/]*$##' | sort | uniq -c | sort -rn | head -20
    echo "== the capture directories, newest first"
    ls -t "$C" | head -30
    echo "== $(date '+%F %T') end"
} > "$OUT" 2>&1
cat "$OUT"

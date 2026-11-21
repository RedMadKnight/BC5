#!/usr/bin/env bash
# BC5 exp 0438 (tag bake438b): the (KYTY_)BC5_ switch words of two emulator binaries, before and after the bake: the
# count of each, the words gained and lost, and the bake's normal-only diagnostics that must not be in a lean build.
# Read only (strings, nice 19); no lock line, no emulator.
#   bash leanwords438b.sh [BEFORE] [AFTER]
#     BEFORE: default the shared lean ~/bc5-work/kytyplus-build-lean/src/kyty_emulator (3a20b974 before the swap; after
#             the swap the copy ~/bc5-work/exp0438/swapb/kyty_emulator.lean.before-0438b)
#     AFTER:  default the private lean of boxbake438b.sh, ~/bc5-work/exp0438/bake438b-priv/lean/kyty_emulator
set -u
export LC_ALL=C
W=$HOME/bc5-work
A=${1:-$W/kytyplus-build-lean/src/kyty_emulator}; B=${2:-$W/exp0438/bake438b-priv/lean/kyty_emulator}
WANT="BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1P"
[ -s "$A" ] && [ -s "$B" ] || { echo "leanwords438b: missing $A or $B"; exit 1; }
T=$(mktemp -d) || exit 1
nice -n 19 strings "$A" > "$T/a.txt"; nice -n 19 strings "$B" > "$T/b.txt"
grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$T/a.txt" | sort -u > "$T/wa"; grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$T/b.txt" | sort -u > "$T/wb"
gained=$(comm -13 "$T/wa" "$T/wb" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$T/wa" "$T/wb" | tr '\n' ' ' | sed 's/ $//')
echo "before $(md5sum < "$A" | cut -c1-8) $A: $(wc -l < "$T/wa") (KYTY_)BC5_ words"
echo "after  $(md5sum < "$B" | cut -c1-8) $B: $(wc -l < "$T/wb") (KYTY_)BC5_ words"
echo "gained: [$gained]"; echo "lost:   [$lost]"
ok=1
[ "$gained" = "$WANT" ] || { echo "NOT the bake's lean words: want [$WANT]"; ok=0; }
[ -z "$lost" ] || { echo "words lost"; ok=0; }
for t in KYTY_BC5_0438_A1J BC5_DIRECT_0438_A2_CHECK "tag a1c438" "tag a2c438" "tag a2): MISMATCH" "ng438 (exp 0438)" "wd438" BC5_0438_SUBMITQ BC5_0438_R438_LWM; do
    n=$(grep -cF "$t" "$T/b.txt"); echo "after: '$t' $n"; [ "$n" = 0 ] || ok=0
done
rm -rf "$T"
[ $ok = 1 ] && echo "leanwords438b: PASS" || echo "leanwords438b: FAIL"
[ $ok = 1 ]

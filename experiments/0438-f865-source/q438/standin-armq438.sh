#!/usr/bin/env bash
# BC5 exp 0438: a laptop stand-in run of armq438.sh (fake box tree, stub start0413g.sh writing a play log and a capture
# journal with one q438 BUG line, stub pgrep / sudo / distrobox). Checks that the switch words reach the runner as given
# (no stray word), that the run's own capture journal is read, that BUG lines keep the result from "CLEAN", and that
# the lock is released. No box, no GPU.   bash standin-armq438.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd); D=$(mktemp -d)
mkdir -p "$D/home/bc5-work/exp0413/n/raw" "$D/home/bc5-work/exp0438/stack/normal" "$D/home/bc5-data/captures/faults/x" "$D/bin"
echo fake > "$D/home/bc5-work/exp0438/stack/normal/kyty_emulator"
md5sum < "$D/home/bc5-work/exp0438/stack/normal/kyty_emulator" | cut -d' ' -f1 > "$D/home/bc5-work/exp0438/stack/normal/binary.md5"
printf '#!/bin/sh\nexit 1\n' > "$D/bin/pgrep"; printf '#!/bin/sh\nexit 0\n' > "$D/bin/sudo"; printf '#!/bin/sh\nexit 0\n' > "$D/bin/distrobox"; chmod +x "$D/bin/"*
cat > "$D/home/bc5-work/exp0413/n/start0413g.sh" << 'STUB'
echo "args: $*" >> "$(dirname "$0")/raw/calls.txt"
mkdir -p "$HOME/bc5-data/captures/play-x/gc"; echo "q438 (exp 0438): BUG: y" > "$HOME/bc5-data/captures/play-x/gc/direct.log"
echo x > "$(dirname "$0")/raw/$1-play.log"; echo "$1 (astro) PASS: ran 60 s; RssAnon 1 kB; kernel lines 0, crash lines 0"
STUB
sed 's/\[ "\${WANT:0:8}" = 853e16e9 \] \&\& //' "$HERE/armq438.sh" > "$D/arm.sh"
HOME="$D/home" PATH="$D/bin:$PATH" bash "$D/arm.sh" sa KYTY_BC5_0438_A1=1 BC5_DIRECT_0438_A2=1 2>&1 | grep -v boot_id | grep "journal\|RESULT\|lock"
echo "the runner got: $(cat "$D/home/bc5-work/exp0413/n/raw/calls.txt")"

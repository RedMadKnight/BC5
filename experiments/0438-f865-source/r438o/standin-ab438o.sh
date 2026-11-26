#!/usr/bin/env bash
# BC5 exp 0438: a laptop stand-in run of ab438o.sh (fake box tree, stub start0413g.sh writing a fake MangoHud log, stub
# pgrep / sudo / distrobox / kscreen-doctor). Checks the arm order, the binaries and switch words each arm passes, the
# lock line's hand-over and its release, and the display check of LESSONS R72 (display438.inc): a good 1920x1080@60
# display with an EDID passes; an empty EDID at 640x480 stops the chain before the lock. No box, no GPU.
#   bash standin-ab438o.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd); D=$(mktemp -d)
mkdir -p "$D/w/exp0413/n/raw" "$D/w/bin" "$D/bin" "$D/drm/card1-DP-1" "$D/m"; echo connected > "$D/drm/card1-DP-1/status"
head -c 256 /dev/urandom > "$D/drm/card1-DP-1/edid"; printf '1920x1080\n1280x720\n' > "$D/drm/card1-DP-1/modes"
for b in c o n; do echo "$b" > "$D/w/bin/$b"; done
printf '#!/bin/sh\nexit 1\n' > "$D/bin/pgrep"; printf '#!/bin/sh\nexit 0\n' > "$D/bin/sudo"; printf '#!/bin/sh\nexit 0\n' > "$D/bin/distrobox"
printf '#!/bin/sh\necho "Output: 1 DP-1 enabled connected priority 1 DisplayPort Modes: 0:1920x1080@60*! 1:1280x720@60"\necho "	Scale: 1"\n' > "$D/bin/kscreen-doctor"
chmod +x "$D/bin/"*
printf 'exit 0\n' > "$D/w/lean-session.sh"
cat > "$D/w/exp0413/n/start0413g.sh" << 'STUB'
TAG=$1; shift 3; R=$(dirname "$0")/raw; echo "start $TAG lock=[$(cat "$(dirname "$0")/../../BOX-LOCK")] bin=$P_BIN words=$*" >> "$R/stub-calls.txt"
for a in "$@"; do case "$a" in MANGOHUD_CONFIG=*) of=${a#*output_folder=}; of=${of%%,*}; mkdir -p "$of"; { echo os; echo x; echo "fps,frametime,elapsed"; i=0; while [ $i -lt 3000 ]; do echo "60,16.6,$((i * 16600000))"; i=$((i + 1)); done; } > "$of/k.csv" ;; esac; done
echo x > "$R/$TAG-play.log"; echo "$TAG (t1) PASS: ran 180 s; RssAnon at the end 1 kB; kernel lines 0, crash lines 0"
STUB
COMMON=(DISP_DRM="$D/drm" AB_DISP_INC="$HERE/display438.inc" AB_STANDIN=1 AB_W="$D/w" AB_M="$D/m" AB_DRM="$D/drm" AB_CB="$D/w/bin/c" AB_OB="$D/w/bin/o" AB_NB="$D/w/bin/n" PATH="$D/bin:$PATH")
echo "== a good display (1920x1080@60, EDID 256 bytes)"
env "${COMMON[@]}" AB_WARMUP=1 AB_PAIR4=auto AB_O_WORDS="O1=1" AB_N_WORDS="N1=1" bash "$HERE/ab438o.sh" sa 2>&1 | grep -v boot_id | grep "display:\|STOP\|lock released"
sed 's/MANGOHUD_CONFIG=[^ ]*/MH/; s/lock=\[[^]]*\]/lock=held/' "$D/w/exp0413/n/raw/stub-calls.txt"
echo "lock after: [$(cat "$D/w/BOX-LOCK")]"
echo "== R72 negative: an empty EDID at 640x480 must stop before the lock"
: > "$D/drm/card1-DP-1/edid"; printf '640x480\n' > "$D/drm/card1-DP-1/modes"
printf '#!/bin/sh\necho "Output: 1 DP-1 enabled connected Modes: 0:640x480@59.94*!"\necho "	Scale: 0.5"\n' > "$D/bin/kscreen-doctor"
env "${COMMON[@]}" bash "$HERE/ab438o.sh" sb 2>&1 | grep -v boot_id | grep "display:\|STOP\|lock claimed"
echo "lock after: [$(cat "$D/w/BOX-LOCK")]"

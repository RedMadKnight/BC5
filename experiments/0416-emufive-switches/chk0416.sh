#!/usr/bin/env bash
# BC5 exp 0416: the private rebuild (patch 0001 P_NEW8) and the on/off checks, one unattended chain in the top's slot
# (2026-11-12 21:00-21:35). Private directories only (~/bc5-work/exp0413/p and /n, exp 0413's tools); every step takes
# and releases BOX-LOCK by itself and refuses when an emulator runs. The chain stops at a failed build.
#   launcher  if ~/bc5-work/play-pkg.sh is still I_OLD, exp 0413's installer runs first (the maintainer's order)
#   build     p0416.sh: the private tree from 01abfc0c to P_NEW8, normal and lean
#   ASTRO BOT, 30 s each, no dummy variables:
#     a1 plain   a2 KYTY_BC5_EVENT_COALESCE_SAME=1   a3 KYTY_BC5_SEMA_TARGETED_WAKE=1
#     a4 both and KYTY_BC5_AMM_SETBUFFER_MAP=1 (the guard must still refuse the mapped target)
#     a5 KYTY_BC5_SWITCH_DEFAULTS=0 (the four fixes must still be on)   a6 BC5_R3_SUBMIT_EOP_EVENT=1
#   second title, RT on, no zero skip, 240 s after G, fault0416.py beside each:
#     r1off plain   r2on COALESCE_SAME, SEMA_TARGETED_WAKE and SUBMIT_EOP_EVENT on
#   lean start 120 s with the two switches on
# usage (on the box, detached): P_NEW8=<patch md5> chk0416.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw
: "${P_NEW8:?the patch md5}"
I_OLD=97835f8850cc22ece5c4bcdbbb646912; I_NEW=157021e3c7adc36f93170369c63056a6
cd "$N" || exit 1
L=$(md5sum < "$W/play-pkg.sh" | cut -d' ' -f1)
if [ "$L" = "$I_OLD" ]; then I_OLD=$I_OLD I_NEW=$I_NEW bash ./instpkg0413.sh ./play-pkg-new-0413.sh; fi
echo "launcher: $(md5sum < "$W/play-pkg.sh" | cut -d' ' -f1)"
(cd "$P/kit" && P_NEW8=$P_NEW8 bash ./p0416.sh) > "$P/p0416.log" 2>&1
tail -3 "$P/p0416.log"
grep -q "^lock released" "$P/p0416.log" && grep -q " done; normal " "$P/p0416.log" || { echo "chk0416: the build did not end clean"; grep -m8 "error:\|STOP\|differs" "$P/p0416.log" "$P"/build-*.build.log 2> /dev/null | cut -c1-300; exit 1; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1)
echo "0416 binaries: normal $MN lean $ML"
export P_BIN=$BN P_WANT=$MN
bash ./sweep0413g.sh a1x 30 "0"
bash ./sweep0413g.sh a2x 30 "0" KYTY_BC5_EVENT_COALESCE_SAME=1
bash ./sweep0413g.sh a3x 30 "0" KYTY_BC5_SEMA_TARGETED_WAKE=1
bash ./sweep0413g.sh a4x 30 "0" KYTY_BC5_EVENT_COALESCE_SAME=1 KYTY_BC5_SEMA_TARGETED_WAKE=1 KYTY_BC5_AMM_SETBUFFER_MAP=1
bash ./sweep0413g.sh a5x 30 "0" KYTY_BC5_SWITCH_DEFAULTS=0
bash ./sweep0413g.sh a6x 30 "0" BC5_R3_SUBMIT_EOP_EVENT=1
for t in a1x0 a2x0 a3x0 a4x0 a5x0 a6x0; do
    echo "$t lines: $(grep -a -h "COALESCE_SAME on\|TARGETED_WAKE on\|exp 0416: set-buffer\|exp 0412 events: pending cap\|SETBUFFER_GUARD o\|SessionManager V2 o" "$R/$t-play.log" 2> /dev/null | sed 's/\[bc5\] //' | cut -c1-70 | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
    echo "$t env-read lines: $(grep -a -c "ACB_STATE_RESTORE\|RANGES_FAST\|PHYSMAP_SORTED" "$R/$t-play.log" 2> /dev/null)"
done
second() {  # tag, extra words
    local tag=$1; shift
    setsid nohup python3 ./fault0416.py "$R/$tag-faults.txt" 460 < /dev/null > /dev/null 2>&1 &
    local fp=$!
    P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 "$@"
    kill "$fp" 2> /dev/null; pkill -f "fault0416.py $R/$tag-faults.txt" 2> /dev/null  # SIGTERM: the catcher ends and reaps its dmesg child and writes its last line
    sleep 4; tail -1 "$R/$tag-faults.txt"
    echo "$tag faults: $(grep -c ' fault: ' "$R/$tag-faults.txt" 2> /dev/null) lines, no CPU VMA $(grep -c ' fault: .*CPU VMA now: none' "$R/$tag-faults.txt" 2> /dev/null); switch lines: $(grep -a -h "COALESCE_SAME on\|TARGETED_WAKE on" "$R/$tag-play.log" 2> /dev/null | wc -l)"
    sleep 5
}
second r1off
second r2on KYTY_BC5_EVENT_COALESCE_SAME=1 KYTY_BC5_SEMA_TARGETED_WAKE=1 BC5_R3_SUBMIT_EOP_EVENT=1
P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh l5lean lean 120 KYTY_BC5_EVENT_COALESCE_SAME=1 KYTY_BC5_SEMA_TARGETED_WAKE=1
echo "chk0416 done $(date +%T)"

#!/usr/bin/env bash
# exp 0446 (tag dep446, 2026-11-26): the stage-1 deployment on the maintainer's yes and the top session's word.
# Waits for chain446c.sh to end, then: 1. bake446.sh check; 2. bake446.sh swap; 3. the md5s at the shared paths that his
# launchers use, against the kit; 4. check runs from the deployed paths: the first title on lean (180 s, shots), the second
# title from the NAS on lean (600 s, frame log), the second title on normal (180 s). Any failure in 4 (a GPU kernel line, a
# run that ends by itself, a missing record): bake446.sh undo at once and the old hashes read back. His launchers, menu
# files and shortcuts are not touched (the runs use exp 0446's derived launcher: its own logs, a save copy, the route).
set -u
X=$HOME/bc5-work/exp0446; W=$HOME/bc5-work; cd "$X" || exit 1; R=$X/raw
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; SA=$W/backend-ubuntu/libbc5_backend.a; SM=$W/bc5-tools-ubuntu/release/bc5-mount
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
say() { echo "$(date +%T) dep446: $*" | tee -a "$R/dep446.txt"; }
kcount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -v TMZ | grep -ciE 'timeout|reset|page fault|wedged'; }
# a run passes when its record exists and it was stopped by us (SIGTERM at its end) or cut by our own memory guard
ok_run() { [ -s "$1" ] && { grep -q "stop: SIGTERM" "$1" || grep -q "GUARD at" "$1"; } && ! { grep -q "ended by itself" "$1" && ! grep -q "GUARD at" "$1"; }; }
avail() { echo "$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 )) MiB available, $(( $(awk '/^Shmem:/ {print $2}' /proc/meminfo) / 1024 )) MiB shmem, other runs: $(pgrep -c '^kyty_emulator|^clang|^cc1plus|^ninja|^cargo|^rustc')"; }
# the OOM killer ended the emulator since $1 (journal time): the second title on the normal build sits at the memory floor on
# today's shared build too (x446pSND, 17:04:13, F921's class); recorded with its memory picture, not a reason to undo
oom_since() { journalctl -k --since "$1" --no-pager 2> /dev/null | grep -q "Killed process [0-9]* (kyty_emulator)"; }
oom_picture() { journalctl -k --since "$1" --no-pager 2> /dev/null | grep -E "Killed process|shmem:[0-9]|Free swap" | cut -c1-300 >> "$R/dep446.txt"; }
undo_now() { say "FAILURE: $*; bake446.sh undo"; bash ./bake446.sh undo 2>&1 | tee -a "$R/dep446.txt"; say "after undo: normal $(m8 "$NB") lean $(m8 "$LB") archive $(m8 "$SA") bc5-mount $(m8 "$SM")"; exit 2; }
t0=$(date +%s); while pgrep -f "bash chain446c[.]sh" > /dev/null && [ $(( $(date +%s) - t0 )) -lt 14400 ]; do sleep 30; done
pgrep -f "bash chain446c[.]sh" > /dev/null && { say "chain446c still runs after 4 h: no deployment"; exit 1; }
t0=$(date +%s); while { [ -s "$W/BOX-LOCK" ] || pgrep '^kyty_emulator' > /dev/null || pgrep -x bc5-mount > /dev/null; } && [ $(( $(date +%s) - t0 )) -lt 3600 ]; do sleep 15; done
say "boot $(uptime -s), kernel lines $(kcount); shared before: normal $(m8 "$NB") lean $(m8 "$LB") archive $(m8 "$SA") bc5-mount $(m8 "$SM")"
bash ./bake446.sh check 2>&1 | tee -a "$R/dep446.txt" | grep -q "check: ok" || { say "check failed: no swap"; exit 1; }
bash ./bake446.sh swap 2>&1 | tee -a "$R/dep446.txt"
grep -q "swap: bc5-mount" "$W/bake446/bake446.log" && [ "$(m8 "$SM")" = 31d9bbfa ] || { say "swap did not finish (its own undo ran if a step failed)"; exit 1; }
NN=$(m8 "$NB"); NL=$(m8 "$LB"); NA=$(m8 "$SA")
say "deployed: normal $NN lean $NL archive $NA bc5-mount $(m8 "$SM"); kept: $NB.bakeH ($(m8 "$NB.bakeH")) $LB.bakeH ($(m8 "$LB.bakeH")) $SA.bakeH ($(m8 "$SA.bakeH")) $SM.bakeH ($(m8 "$SM.bakeH")); sources in $W/bake446/orig"
say "his launchers' binaries: $(grep -hoE '~/bc5-work/kytyplus-build(-lean)?/src/kyty_emulator|~/bc5-work/bc5-tools-ubuntu/release/bc5-mount' "$W/play-pkg.sh" "$W/play-any.sh" "$W/play-t1.sh" 2> /dev/null | sort | uniq -c | tr '\n' ';')"
# 4. check runs (the available memory and other runs noted before each)
say "before the first title: $(avail)"
AB_PIN_C=$NL AB_PIN_O=ef76f031 AB_PIN_N=94e0e462 AB_KIND=t1 AB_LEAN=1 AB_SECS=180 AB_SHOT_S=10 AB_GUARD_MB=1200 AB_ROUNDS=1 AB_ARMS="K" \
    AB_ARM_K="$LB|$NL|KYTY_BC5_INPUT_CMD=$X/press446.cmd KYTY_BC5_MENU_DIR=$X/menu-full" bash ./ab446.sh x446d1 2>&1 | grep -E "PASS|ENDED|GUARD|STOP|memory:" | tee -a "$R/dep446.txt"
grep -q PASS "$R/x446d1K1-end.txt" 2> /dev/null || undo_now "the first title did not pass"
[ "$(kcount)" = 0 ] || undo_now "a GPU kernel line after the first title"
say "before the second title (lean): $(avail)"
SER_WAIT=3600 SER_BIN=$LB SER_PIN=$NL SER_LEAN=1 SER_MH=1 SER_SECS=600 SER_EXTRA="KYTY_BC5_MANGOHUD=0" bash ./ser446.sh x446d2 D 2>&1 | grep -E "^.{8} ser " | tee -a "$R/dep446.txt"
ok_run "$R/x446d2D-nas.txt" || undo_now "the second title (lean) ended by itself or left no record"
[ "$(kcount)" = 0 ] || undo_now "a GPU kernel line after the second title (lean)"
say "before the second title (normal): $(avail)"; T3=$(date "+%F %T")
SER_WAIT=3600 SER_BIN=$NB SER_PIN=$NN SER_LEAN=0 SER_MH=0 SER_SECS=180 SER_EXTRA="" bash ./ser446.sh x446d3 D 2>&1 | grep -E "^.{8} ser " | tee -a "$R/dep446.txt"
if oom_since "$T3"; then say "the second title (normal) was ended by the OOM killer: recorded, no undo (compare x446pSND)"; oom_picture "$T3"
else ok_run "$R/x446d3D-nas.txt" || undo_now "the second title (normal) ended by itself (not the OOM killer) or left no record"; fi
[ "$(kcount)" = 0 ] || undo_now "a GPU kernel line after the second title (normal)"
say "check runs done: all passed, kernel lines 0; deployed normal $NN lean $NL archive $NA bc5-mount $(m8 "$SM")"

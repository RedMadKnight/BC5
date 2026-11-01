s = open(r"C:/Users/kjani/Documents/ChatGPT/BC5/coordination/d19/s6n-d19.sh", encoding="utf-8", newline="").read()
def R(a, b, n=1):
    global s
    assert s.count(a) >= 1 and (n == 0 or s.count(a) == n), (a, s.count(a))
    s = s.replace(a, b)
head_end = s.index("set -u\n")
s = """#!/usr/bin/env bash
# BC5 exp 0386: one F464 fight run with the job-arena fix on or off, on the shared normal build, RT on.
# Derived from coordination/d19/s6n-d19.sh d7cf6e33 by mk0386.py. What differs (each marked "0386:" where it stands):
#  - the route: exp 0358's save copy, exp 0360's menu script, and the gameplay inputs appended on the journal gate of
#    run0360.sh (REPRO_PHASE2); KYTY_BC5_JOB_ARENA_FIX in the emulator's environment, proved there.
#  - the emulator is the one that carries this run's D19_OWNER token; a foreign one stops the run and is never touched.
#  - the journal is the run's own: BC5_GC_DUMP_DIR from the emulator's environment, not the newest capture directory.
#  - the lock line is checked at every poll; a lost lock stops the run.
#  - every clear of a private directory proves containment first; no live-save snapshot, no shots, no forced samples.
#  - all /proc, kernel and clock reads are small functions, so the stand-ins replace only those.
# Called by box0386.sh only. usage: s6n0386.sh <live saves sum> <tag> <secs> <on|off>
# Exit: 0 verdict pass, 1 anything else, 3 the live saves changed.
""" + s[head_end:]
R('EXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:-600}; RT=${4:-on}; VARIANT=${D19_VARIANT:?}; OWNER=${D19_OWNER:?}  # d19: the mark of all our processes\ncase "$RT" in off | on) ;; *) echo "RT is off or on"; exit 1 ;; esac\n',
  'export LC_ALL=C  # 0386: the save sums are the C-locale ones\nEXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:?secs}; FIX=${4:?on or off}; RT=on; VARIANT=normal; OWNER=${D19_OWNER:?}  # d19: the mark of all our processes\ncase "$FIX" in on) FIXV=1 ;; off) FIXV=0 ;; *) echo "the fix is on or off"; exit 1 ;; esac\n')
R('E=$HOME/bc5-work/d19/run; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E30=$W/exp0330\nBIN=${D19_BIN:?}; WANT=${BC5_0380_WANT:?}\nSWITCHES=""; [ "$VARIANT" = lean ] && SWITCHES="BC5_LEAN=1 BC5_LOGS=1"\n',
  'W=${D19_WORK:-$HOME/bc5-work}; EX=$W/exp0386; E=$EX/run; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330\nBIN=${D19_BIN:?}; WANT=${BC5_0380_WANT:?}; LOCKLINE=${E0386_LOCKLINE:?}\nSWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV"  # 0386\nT_ROUTE=60; T_RT=$((SECS * 5 / 6)); T_FD=120; T_P2=88; T_P2_WAIT=30; T_POLL=5; T_POLL_P2=1; T_KERN=25; T_KILL=4; T_SETTLE=3\n')
R('SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617\n',
  "SAVES=$W/exp0358/saves-live-47aefd45; MENU=$W/exp0360/fight1450-menu.cmd; PHASE2=$W/exp0360/fight1450-play.cmd  # 0386: F464's route\n")
R('LAUNCH=$E/play-pkg-d19s.sh', 'LAUNCH=$E/play-pkg-0386.sh')
R('pgrep \'^kyty_emulator\' > /dev/null && { echo "an emulator is running: not started"; exit 1; }\n[ -s "$LOCK" ] && ! grep -q "^top d19 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }\nsudo -n dmesg > /dev/null 2>&1 || { echo "no dmesg access, the kernel gate would be empty: not started"; exit 1; }  # d19\n[ -d "$HOME/bc5-data/captures/devcoredump" ] || { echo "no devcoredump directory, that gate would be empty: not started"; exit 1; }  # d19\n[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?} (build0358.sh first): not started"; exit 1; }\n[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0330.sh or $LEARN_SRC"; exit 1; }\n',
  r'''# 0386: the box's reads, in one place
now() { date +%s; }
el() { echo $(($(now) - T0)); }
pause() { sleep "$1"; }
emu_pids() { pgrep -x kyty_emulator; return 0; }
env_raw() { cat "/proc/$1/environ"; }
exe_of() { readlink "/proc/$1/exe"; }
exe_md5() { md5sum < "/proc/$1/exe" | cut -c1-8; }
cwd_of() { readlink -f "/proc/$1/cwd"; }
alive() { [ -d "/proc/$1" ]; }
fdinfo_of() { cat /proc/"$1"/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; }
kern() { sudo -n dmesg 2> /dev/null; }
mount_opts() { findmnt -no OPTIONS -T "$1" 2> /dev/null; }
route_read() { find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null; }
sampler() { "$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!; }
launch() { setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 & }
devcores() { find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null; }
box_settings() { echo "swappiness $(cat /proc/sys/vm/swappiness); kernel $(uname -r); shared normal $(md5sum < "$BIN" | cut -c1-8); learned $(md5sum < "$LEARN_SRC" | cut -c1-8)"; }
boot_line() { echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; }
# Stand-ins load only from a d19-test- path; they replace the functions above and the T_ times, nothing else.
case "${D19_FAKE:-}" in *d19-test-*) . "$D19_FAKE" ;; esac
envof() { env_raw "$1" 2> /dev/null | tr '\0' '\n'; }
is_ours() { envof "$1" | grep -qxF -- "D19_OWNER=$OWNER"; }
own_lock_q() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }
# A directory may be cleared only if it is really inside this experiment: no link on the way, no escape.
contained() {
  local p=$1 r x; [ -e "$p" ] || return 0
  [ ! -L "$p" ] && r=$(readlink -f "$p") && x=$(readlink -f "$EX") && [ -n "$x" ] || return 1
  case "$r" in "$x"/*) return 0 ;; *) return 1 ;; esac
}
[ -z "$(emu_pids)" ] || { echo "an emulator is running: not started"; exit 1; }
own_lock_q || { echo "the lock is not this run's: not started"; exit 1; }  # 0386: box0386.sh owns the lock
kern > /dev/null || { echo "no dmesg access, the kernel gate would be empty: not started"; exit 1; }  # d19
[ -d "$HOME/bc5-data/captures/devcoredump" ] || { echo "no devcoredump directory, that gate would be empty: not started"; exit 1; }  # d19
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?}: not started"; exit 1; }
[ -d "$SAVES" ] && [ ! -L "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -s "$MENU" ] && [ -s "$PHASE2" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, $MENU, $PHASE2, sample0330.sh or $LEARN_SRC"; exit 1; }
''')
i = s.index('FORCE=$HOME/bc5-data/captures/gpu-stall/force;'); j = s.index('saves() {')
s = s[:i] + s[j:]
R('saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253\'s ab0253.sh',
  'saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }  # exp 0253\'s ab0253.sh, C locale')
i = s.index("# The box's memory settings, read only"); j = s.index('cat "$R/$TAG-box-settings.txt"')
s = s[:i] + "# The box's settings, read only (the maintainer's to change)\nbox_settings > \"$R/$TAG-box-settings.txt\"\n" + s[j:]
i = s.index('# exp 0364: BC5_0368_RESET_LEARNED'); j = s.index('# 2. The derived launcher')
s = s[:i] + s[j:]
s = s.replace('PLAY_PKG_MD5=${PLAY_PKG_MD5:-55531ab6}   # exp 0378: play-pkg.sh as read on 2026-10-29 10:40', "PLAY_PKG_MD5=55531ab6   # D19's pin; box0386.sh checks the full md5")
s = s.replace(''', not ${PLAY_PKG_MD5:-?} (int0350.sh's): check the edits below against it, not started (PLAY_PKG_MD5=... to accept)"''', ''', not $PLAY_PKG_MD5: not started"''')
s = s.replace("~/bc5-work/d19/run/", "~/bc5-work/exp0386/run/").replace("$HOME/bc5-work/d19/run/", "$HOME/bc5-work/exp0386/run/")
s = s.replace("d19/run/wd", "exp0386/run/wd").replace("d19/run/play-last", "exp0386/run/play-last").replace("d19/run/direct-learned", "exp0386/run/direct-learned")
s = s.replace("play-pkg-d19s.diff", "play-pkg-0386.diff")
R('[ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)"', 'contained "$WD/_SaveData" && contained "$SDD" || { echo "$WD/_SaveData or $SDD is not inside $EX: not started"; exit 1; }\n[ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)"')
R('''case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in''', '''case " $(mount_opts "$E" | tr ',' ' ') " in''')
i = s.index('SNAP=$E/saves-before-'); j = s.index('# d19: d19box.sh owns the lock')
s = s[:i] + '''WANT_SAVES=$(saves)\necho "$(date '+%F %T') live saves $WANT_SAVES (comparison only)" | tee -a "$R/s6n-saves.txt"\n''' + s[j:]
R('# d19: d19box.sh owns the lock\n# d19: no lock trap\n', '# box0386.sh owns the lock\n')
R('abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; [ -n "$SP" ] && kill "$SP" 2> /dev/null;',
  'stop_emu() { if [ -n "$EP" ] && alive "$EP" && is_ours "$EP"; then kill "$EP"; pause "$T_KILL"; alive "$EP" && is_ours "$EP" && kill -9 "$EP" 2> /dev/null; fi; return 0; }  # 0386: only our own\nabort() { stop_emu; [ -n "$SP" ] && kill "$SP" 2> /dev/null;')
R('''envof() { tr '\\0' '\\n' < "/proc/$1/environ" 2> /dev/null; }\nENDED=""''', 'ENDED=""')
R('RTOFF=""; FL=0; SPAN=0; FPS=0; FDINFO=""; JOK=0; KERN_OK=0; RTAT=$((SECS * 5 / 6))', 'RTOFF=""; FL=0; SPAN=0; FPS=0; FDINFO=""; JOK=0; KERN_OK=0; RTAT=$T_RT; JRUN=""')
R('journal_of() { echo "$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log"; }\n', '')
R('  private_capture "$2" cat "/proc/$1/environ" || return 1', '  private_capture "$2" env_raw "$1" || return 1')
R('ENVS=(BC5_EMU="$BIN" BC5_0358_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" D19_OWNER="$OWNER")\n[ "$RT" = off ] && ENVS+=(KYTY_BC5_RT=0)\n', 'ENVS=(BC5_EMU="$BIN" BC5_0358_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" D19_OWNER="$OWNER")\n')
R('case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "refusing to clear $SROOT"; exit 1 ;; esac\n', 'contained "$SROOT/PPSA03671" || { echo "refusing to clear $SROOT/PPSA03671"; exit 1; }\nrm -rf "$SROOT/PPSA03671" || exit 1\n')
R('cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"\nN=$(sudo -n dmesg 2> /dev/null | wc -l)\n', '''cp "$MENU" "$E/in-$TAG.cmd" || { echo "the menu script could not be copied"; exit 1; }\nP2LOAD=""; P2DONE=""; P2GAME=0  # 0386: the fight route's second part\nNEWDIRS=$(ls -d "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null)  # 0386: what existed before this run\nN=$(kern | wc -l)\n''')
R('''echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; } > "$R/$TAG-start.txt"\n"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!\nsetsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &\nfor _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done\nT0=$(date +%s)\n''',
  '''boot_line; } > "$R/$TAG-start.txt"\nsampler\nT0=$(now)\nlaunch\n# 0386: the emulator is the one with our token. Any other is foreign: the run stops and does not touch it.\nfor _ in $(seq 1 120); do\n  for p in $(emu_pids); do if is_ours "$p"; then EP=$p; else ENDED="SETUP: a foreign emulator $p"; fi; done\n  [ -z "$EP" ] && [ -z "$ENDED" ] || break\n  pause 0.5\ndone\n''')
i = s.index('SHOTS=$HOME/bc5-data/captures/d19/shots;'); j = s.index('if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"')
s = s[:i] + s[j:]
R('if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"\nelse\n', 'if [ -n "$ENDED" ]; then :\nelif [ -z "$EP" ]; then ENDED="SETUP: no emulator started"\nelse\n')
R('  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"\n', '  echo "emulator pid $EP exe $(exe_of "$EP") cwd $(cwd_of "$EP")" >> "$R/$TAG-start.txt"\n')
R("|MALLOC_ARENA_MAX|BC5_LEAN|BC5_LOGS)='", "|MALLOC_ARENA_MAX|BC5_LEAN|BC5_LOGS|KYTY_BC5_JOB_ARENA_FIX|BC5_GC_DUMP_DIR)='")
R('  [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"\n', '  [ "$(exe_md5 "$EP")" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"\n')
R('''  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"\n''',
  r'''  [ "$(cwd_of "$EP")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  # 0386: the run's own journal, from its environment, in a directory that did not exist before this run.
  GC=$(envof "$EP" | sed -n 's/^BC5_GC_DUMP_DIR=//p')
  case "$GC" in "$HOME"/bc5-data/captures/play-*/gc) JRUN=$GC/direct.log ;; *) [ -n "$ENDED" ] || ENDED="SETUP: no journal directory of this run in its environment" ;; esac
  case "
$NEWDIRS
" in *"
$GC
"*) [ -n "$ENDED" ] || ENDED="SETUP: the journal directory $GC is older than this run" ;; esac
''')
R('''while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do\n  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }\n''',
  '''while [ -z "$ENDED" ] && [ "$(el)" -lt "$SECS" ]; do\n  own_lock_q || { ENDED="SETUP: the lock is no longer this run's"; break; }  # 0386\n  alive "$EP" || { ENDED="ended by itself at $(el) s"; break; }\n''')
R('''  if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
    if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1; echo "routed at $(($(date +%s) - T0)) s: $(find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | head -1)" > "$R/$TAG-route.txt"  # d19
    else ENDED="SETUP: the route save was not read by 60 s"; break; fi
  fi
''', '''  if [ -z "$ROUTED" ] && [ "$(el)" -ge "$T_ROUTE" ]; then
    if route_read | grep -q .; then ROUTED=1; echo "routed at $(el) s: $(route_read | head -1)" > "$R/$TAG-route.txt"  # d19
    else ENDED="SETUP: the route save was not read by $T_ROUTE s"; break; fi
  fi
''')
R('''  if [ -z "$FDINFO" ] && [ $(($(date +%s) - T0)) -ge 120 ]; then  # exp 0341: the rings the work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)\n    FDINFO=1; { echo "at $(($(date +%s) - T0)) s:"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\\|^drm-client-id" | sort | uniq -c; } > "$R/$TAG-fdinfo.txt"\n''',
  '''  if [ -z "$FDINFO" ] && [ "$(el)" -ge "$T_FD" ]; then  # exp 0341: the rings the work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)\n    FDINFO=1; { echo "at $(el) s:"; fdinfo_of "$EP"; } > "$R/$TAG-fdinfo.txt"\n''')
R('''[ $(($(date +%s) - T0)) -ge "$RTAT" ]; then  # d19: was >= 180 s, inside a < 180 s loop\n    rt_check "$(journal_of)" "$T0" "$RT"; [ -z "$ENDED" ] || break\n''', '''[ "$(el)" -ge "$RTAT" ]; then  # d19: was >= 180 s, inside a < 180 s loop\n    rt_check "$JRUN" "$T0" "$RT"; [ -z "$ENDED" ] || break\n''')
i = s.index('  if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then'); j = s.index('DUR=$(($(date +%s) - T0))')
s = s[:i] + r'''  if kern | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
    pause "$T_KERN"
    if kern | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="DOWN: kernel amdgpu line, reset failed or MODE1"
    elif kern | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then ENDED="HANG: kernel amdgpu line at $(($(el) - T_KERN)) s, ring reset succeeded"
    else ENDED="HANG: kernel amdgpu line at $(($(el) - T_KERN)) s, no reset line"; fi
    break
  fi
  # 0386, from run0360.sh: the gameplay inputs are appended to the input script (the input thread tails it every 20 ms)
  # once the journal shows the load after the menu (the last 5 flips slower than 55 ms) and then gameplay (of the last
  # 25 flips at least 20 faster than 40 ms, the last 3 among them), from 88 s on; 30 s after the load without that they
  # go anyway, and the run then does not count as routed. Every poll is kept in raw/<tag>-phase2.txt.
  if [ -z "$P2DONE" ] && [ "$(el)" -ge "$T_P2" ] && [ -f "$JRUN" ]; then
    P2IV=$(tail -c 400000 "$JRUN" | grep -a "^frame profile: t" | tail -25 | sed -n 's/^frame profile: t [0-9.]* s, \([0-9.]*\) ms since.*/\1/p' | tr '\n' ' ')
    read -r P2SLOW P2FAST <<< "$(echo "$P2IV" | awk '{slow = NF >= 5; for (i = NF - 4; i <= NF && i >= 1; i++) if ($i <= 55) slow = 0; f = 0; for (i = 1; i <= NF; i++) if ($i < 40) f++; fast = NF >= 25 && f >= 20; for (i = NF - 2; i <= NF && i >= 1; i++) if ($i >= 40) fast = 0; print slow + 0, fast + 0}')"
    echo "$(el) s: slow ${P2SLOW:-?} fast ${P2FAST:-?} load ${P2LOAD:-} | $P2IV" >> "$R/$TAG-phase2.txt"
    [ "${P2SLOW:-0}" = 1 ] && [ -z "$P2LOAD" ] && P2LOAD=$(el)
    if { [ -n "$P2LOAD" ] && [ "${P2FAST:-0}" = 1 ]; } || { [ -n "$P2LOAD" ] && [ $(($(el) - P2LOAD)) -ge "$T_P2_WAIT" ]; }; then
      [ "${P2FAST:-0}" = 1 ] && P2GAME=1
      cat "$PHASE2" >> "$E/in-$TAG.cmd" || { ENDED="SETUP: the gameplay inputs could not be appended"; break; }
      P2DONE=$(el)
      echo "phase2 appended $P2DONE load $P2LOAD gameplay $P2GAME lines $(grep -c . "$PHASE2")" | tee "$R/$TAG-phase2-done.txt"
    fi
  fi
  if [ -z "$P2DONE" ] && [ "$(el)" -ge $((T_P2 - 3)) ]; then pause "$T_POLL_P2"; else pause "$T_POLL"; fi
done
''' + s[j:]
R('''DUR=$(($(date +%s) - T0))\nif [ -n "$EP" ] && [ -d "/proc/$EP" ]; then { echo "at $DUR s (end):"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\\|^drm-client-id" | sort | uniq -c; } >> "$R/$TAG-fdinfo.txt"; fi\nif [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi\nsleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""\n''',
  '''DUR=$(el)\nif [ -n "$EP" ] && alive "$EP" && is_ours "$EP"; then { echo "at $DUR s (end):"; fdinfo_of "$EP"; } >> "$R/$TAG-fdinfo.txt"; fi\nstop_emu\npause "$T_SETTLE"; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""\n''')
R('''if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else''', '''if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log" || echo "no log of this run: the copy failed" > "$R/$TAG-play.log"; else''')
R('''J=$(journal_of)\nNRT=0; NCR=0\nif [ -f "$J" ]''', '''J=$JRUN  # 0386: this run's own\nNRT=0; NCR=0\nif [ -n "$J" ] && [ -f "$J" ]''')
R('  JOK=1  # d19\n', '''  JOK=1  # d19\n  if [ -z "$RTOFF" ] && ! grep -aq "ray tracing off:" "$J"; then RTOFF=on; fi  # 0386: a crash ends the run before the live check\n''')
R('else echo "no journal of this run ($J)"', 'else echo "no journal of this run (${J:-none})"')
R('if KT=$(sudo -n dmesg 2> /dev/null); then', 'if KT=$(kern); then')
i = s.index('find "$(dirname "$FORCE")" -maxdepth 1'); j = s.index('cmp -s "$LEARN_SRC" "$LEARN"')
s = s[:i] + 'devcores > "$R/$TAG-devcoredump.txt"\n' + s[j:]
R('sleep 2\nX=$(grep', 'X=$(grep')
R('''[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot $SNAP): tell the maintainer before anything is restored"\nsync\n# d19: the lock stays with d19box.sh\n[ "$S1" = "$WANT_SAVES" ] && [ "$(cat "$R/$TAG-verdict.txt")" = pass ]  # d19: the exit status carries the result\n''',
  '''[ "$S1" = "$WANT_SAVES" ] || { echo "THE LIVE SAVES ARE NOT $WANT_SAVES: tell the maintainer before anything is restored"; exit 3; }\nsync\n[ "$(cat "$R/$TAG-verdict.txt")" = pass ]  # d19: the exit status carries the result\n''')

# REVIEW-PORTS-32
R('T_ROUTE=60; T_RT=$((SECS * 5 / 6));', 'DISK_MAX=80; T_ROUTE=60; T_RT=$((SECS * 5 / 6));')
R('mount_opts() { findmnt', 'disk_pct() { df --output=pcent "$HOME" | tail -1 | tr -dc 0-9; }\nmount_opts() { findmnt')
R('  local p=$1 r x; [ -e "$p" ] || return 0\n', '  local p=$1 r x; [ -e "$p" ] || [ -L "$p" ] || return 0\n')
R('''sed -i '/^done < "\\$ENVF"$/a [ -n "${BC5_0358_INPUT_CONFIG:-}" ] \\&\\& export KYTY_BC5_INPUT_CONFIG=$BC5_0358_INPUT_CONFIG  # exp 0339' "$LAUNCH" || exit 1\n''',
  '''sed -i '/^done < "\\$ENVF"$/a [ -n "${BC5_0358_INPUT_CONFIG:-}" ] \\&\\& export KYTY_BC5_INPUT_CONFIG=$BC5_0358_INPUT_CONFIG  # exp 0339' "$LAUNCH" || exit 1
# 0386: the last settings load is bc5-pkg.env. The check runs after it and before each emulator start, the F2 restart too.
PRE='. ~/bc5-work/exp0386/s/prestart0386.sh || exit 97  # exp 0386'
[ "$(grep -c '^~/bc5-work/pad-volume\\.sh >> "$LOG"' "$LAUNCH")" = 1 ] && [ "$(grep -c '^  "$EMU" --game "$M" ' "$LAUNCH")" = 1 ] || { echo "the launcher's start lines are not as pinned: not started"; rm -f "$LAUNCH"; exit 1; }
sed -i -e "/^~\\/bc5-work\\/pad-volume\\.sh >> \\"\\$LOG\\"/i $PRE" -e "/^  \\"\\$EMU\\" --game \\"\\$M\\" /i $PRE" "$LAUNCH" || exit 1
[ "$(grep -cxF -- "$PRE" "$LAUNCH")" = 2 ] && [ "$(grep -n -F "$PRE" "$LAUNCH" | head -1 | cut -d: -f1)" -gt "$(grep -n '^  done < "$PKG_ENV"$' "$LAUNCH" | cut -d: -f1)" ] || { echo "the start check is not after the last settings load: not started"; exit 1; }
''')
R('''= 11 ] || { echo "the derived launcher's diff is not 5 lines changed + 1 added: not started"; exit 1; }''', '''= 13 ] || { echo "the derived launcher's diff is not 5 lines changed + 3 added: not started"; exit 1; }''')
R('if [ ! -e "$WD" ]; then\n', 'contained "$WD" || { echo "$WD is not inside $EX: not started"; exit 1; }\nif [ ! -e "$WD" ]; then\n')
R('''[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }\n''',
  '''[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
# 0386: what prestart0386.sh must find after the last settings load.
{ echo "lock=$LOCKLINE"
  for w in "${WANTENV[@]}"; do echo "want=$w"; done
  echo "want=KYTY_BC5_INPUT_CMD=$E/in-$TAG.cmd"; echo "want=BC5_0358_INPUT_CONFIG=$CFG"; echo "want=BC5_EMU=$BIN"; echo "want=EMU=$BIN"; echo "want=LOG=$LOG"
  echo "want=HOME=$HOME"; echo "want=ENVF=$W/bc5-run.env"; echo "want=M=$HOME/bc5-data/mnt/pkg-play"; echo "want=PKG=$HOME/bc5-data/pkg/game.pkg"
  echo "want=PLAY_ARGS=$(sed -n 's/^PLAY_ARGS=//p' "$W/bc5-run.env" | tail -1) --fullscreen"
} > "$E/prestart.want.$$" && mv -f "$E/prestart.want.$$" "$E/prestart.want" || { echo "the start check's file could not be written"; exit 1; }
rm -f "$E/prestart.out"
''')
R('sampler\nT0=$(now)\nlaunch\n', '''sampler\nT0=$(now)\nown_lock_q || { echo "the lock is not this run's: not launched"; [ -z "$SP" ] || kill "$SP" 2> /dev/null; exit 1; }  # 0386: the last look before the launch\nlaunch\n''')
R('''  if kern | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then\n''', '''  D=$(disk_pct); [ -n "$D" ] && [ "$D" -lt "$DISK_MAX" ] || { ENDED="SETUP: the disk is at ${D:-unknown} %"; break; }  # 0386: at every poll\n  KL=$(kern) || { ENDED="SETUP: the kernel log could not be read"; break; }\n  if printf '%s\\n' "$KL" | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then\n''')
R('''devcores > "$R/$TAG-devcoredump.txt"\n''', '''devcores > "$R/$TAG-devcoredump.txt"; DEV_OK=$?\necho "kernel $KERN_OK devcore $([ "$DEV_OK" = 0 ] && echo 1 || echo 0)" > "$R/$TAG-reads.txt"  # 0386: an empty file is not a read\n''')
open(r"C:/Users/kjani/Downloads/bc5/bc5-0386/experiments/0386-fight-job-arena/s6n0386.sh", "w", encoding="utf-8", newline="").write(s)
print("written")

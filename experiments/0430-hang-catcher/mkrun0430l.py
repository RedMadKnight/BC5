#!/usr/bin/env python3
"""BC5 experiment 0430 (2026-11-18 evening, the bake's tests): derive run0430l.sh from run0430f.sh (md5 pinned below), for
the lean builds, which write no journal and print no fps line. Every replacement must match exactly once.
    mkrun0430l.py <run0430f.sh> <run0430l.sh>
Changes:
  - N_TIMED=1: the route by time (exp 0432's mkrun0432.py hunk, unchanged): cross at N_T0 s, the slot keys N_T1 s later,
    Continue N_T2 s later, G taken N_T3 s after that. No journal is required.
  - N_MH=1: MangoHud's own frame log as the frame counter, the same for every binary: MANGOHUD=1 and a MANGOHUD_CONFIG of
    no_display, autostart_log, every frame (log_interval=0), into $R/$TAG-mh/ (the emulator leaves a caller's config as
    it is). After the run the frames from G on are turned into $TAG-fps.txt's per-second lines (t, frames, 1, longest
    frame in ms), which the summary already reads.
  - P_HOST=1: the launcher runs on the Bazzite host, not in the ubuntu distrobox (exp 0423's P_HOST); the start file says
    where, and at 30 s the emulator's maps are read for the Vulkan driver and MangoHud.
"""
import hashlib
import sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "9d53dccc", "run0430f.sh is not 9d53dccc"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


# the route by time (exp 0432)
sub('  if [ -z "$J" ] && [ "$NOW" -ge 60 ]; then\n', '  if [ "${N_TIMED:-0}" != 1 ] && [ -z "$J" ] && [ "$NOW" -ge 60 ]; then\n')
sub('  if [ -n "$J" ] && [ "$RS" -lt 4 ] && [ "$NOW" -ge 85 ]; then\n',
    '  if [ "${N_TIMED:-0}" = 1 ] && [ "$RS" -lt 4 ]; then  # exp 0432: the route by time (lean: no journal)\n'
    '    case "$RS" in\n'
    '      0) if [ "$NOW" -ge "${N_T0:?N_T0}" ]; then printf \'press cross\\n\' >> "$CMD"; RS=1; K=$NOW; echo "route (timed): cross (start screen) at $NOW s" >> "$R/$TAG-start.txt"; fi ;;\n'
    '      1) if [ "$NOW" -ge $((K + ${N_T1:?N_T1})) ]; then LISTED=$NOW; for _ in $(seq 2 "${N_SLOT:-1}"); do printf \'press down\\nwait 500\\n\' >> "$CMD"; done\n'
    '           printf \'press cross\\n\' >> "$CMD"; RS=2; K=$NOW; echo "route (timed): down x $((${N_SLOT:-1} - 1)), cross (slot ${N_SLOT:-1}) at $NOW s" >> "$R/$TAG-start.txt"; fi ;;\n'
    '      2) if [ "$NOW" -ge $((K + ${N_T2:?N_T2})) ]; then printf \'press cross\\n\' >> "$CMD"; RS=3; K=$NOW; LOADT=$NOW; echo "route (timed): cross (Continue) at $NOW s" >> "$R/$TAG-start.txt"; fi ;;\n'
    '      3) if [ "$NOW" -ge $((K + ${N_T3:?N_T3})) ]; then G=$NOW; RS=4; echo "route (timed): G = $G s BY TIME" >> "$R/$TAG-start.txt"; fi ;;\n'
    '    esac\n'
    '  fi\n'
    '  if [ "${N_TIMED:-0}" != 1 ] && [ -n "$J" ] && [ "$RS" -lt 4 ] && [ "$NOW" -ge 85 ]; then\n')
# MangoHud's frame log
sub('ENVS=("${WORDS[@]}" "${EXTRA[@]}" BC5_0412N_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$CMD" WAYLAND_DISPLAY="$WL")\n',
    'ENVS=("${WORDS[@]}" "${EXTRA[@]}" BC5_0412N_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$CMD" WAYLAND_DISPLAY="$WL")\n'
    'if [ "${N_MH:-0}" = 1 ]; then  # exp 0430: MangoHud\'s frame log, the counter for a lean build\n'
    '  mkdir -p "$R/$TAG-mh" || exit 1\n'
    '  ENVS+=(MANGOHUD=1 MANGOHUD_CONFIG="no_display,autostart_log=1,log_interval=0,output_folder=$R/$TAG-mh${N_MHD:+,log_duration=$N_MHD}")  # N_MHD: seconds; MangoHud writes its log when it ends\n'
    'fi\n')
# the host
sub("setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env \"$@\"'\\'' guard0412n \"$@\"; echo \"launcher exit $?\"' _ \"${ENVS[@]}\" \"$LAUNCH\" < /dev/null > \"$R/$TAG-launch.out\" 2>&1 &\n",
    "if [ \"${P_HOST:-0}\" = 1 ]; then  # exp 0430: on the Bazzite host (exp 0423)\n"
    "  echo \"place: the Bazzite host (P_HOST=1), no distrobox\" >> \"$R/$TAG-start.txt\"\n"
    "  setsid nohup bash -c '/usr/bin/bash -c '\\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env \"$@\"'\\'' guard0412n \"$@\"; echo \"launcher exit $?\"' _ \"${ENVS[@]}\" \"$LAUNCH\" < /dev/null > \"$R/$TAG-launch.out\" 2>&1 &\n"
    "else\n"
    "  echo \"place: the ubuntu distrobox\" >> \"$R/$TAG-start.txt\"\n"
    "  setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env \"$@\"'\\'' guard0412n \"$@\"; echo \"launcher exit $?\"' _ \"${ENVS[@]}\" \"$LAUNCH\" < /dev/null > \"$R/$TAG-launch.out\" 2>&1 &\n"
    "fi\n")
sub('  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n',
    '  if [ "$NOW" -ge 30 ] && [ -z "${MAPS_DONE:-}" ]; then MAPS_DONE=1; grep -o \'/[^ ]*\\(libvulkan_radeon\\|MangoHud\\|libpipewire\\|libpulse\\|libSDL\\)[^ ]*\\.so[^ ]*\' "/proc/$EP/maps" 2> /dev/null | sort -u | sed "s/^/maps at 30 s: /" >> "$R/$TAG-start.txt"; fi  # exp 0430\n'
    '  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n')
# the per-second lines from MangoHud's log (columns found by name; frametime in ms; elapsed in ns since the log began)
sub('grep -a "fps counter" "$R/$TAG-play.log" | sed -E \'s/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\\1 \\2 \\3 \\4/\' > "$R/$TAG-fps.txt"\n',
    'grep -a "fps counter" "$R/$TAG-play.log" | sed -E \'s/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\\1 \\2 \\3 \\4/\' > "$R/$TAG-fps.txt"\n'
    'if [ "${N_MH:-0}" = 1 ]; then  # exp 0430: lean: the frames of MangoHud\'s log from G on, per second\n'
    '  MHF=$(ls -t "$R/$TAG-mh"/*.csv 2> /dev/null | grep -v summary | head -1)\n'
    '  if [ -n "$MHF" ]; then\n'
    '    awk -F, -v g="${G:-0}" \'f == 0 && /^fps,/ {for (i = 1; i <= NF; i++) {if ($i == "frametime") ft = i; if ($i == "elapsed") el = i}; f = 1; next}\n'
    '      f == 1 && ft > 0 && el > 0 {t = $el / 1e9; if (t < g) next; s = int(t); n[s]++; if ($ft > m[s]) m[s] = $ft; if (s > hi) hi = s; if (lo == "" || s < lo) lo = s}\n'
    '      END {for (s = lo + 1; s < hi; s++) printf "%d %d 1 %.1f\\n", s, n[s], m[s]}\' "$MHF" > "$R/$TAG-fps.txt"\n'
    '    echo "MangoHud log $MHF: $(wc -l < "$R/$TAG-fps.txt") seconds from G" >> "$R/$TAG-start.txt"\n'
    '  else echo "N_MH=1: no MangoHud log in $R/$TAG-mh" >> "$R/$TAG-start.txt"; fi\n'
    'fi\n')
# N_LEANSESS=1: the Plasma shell is stopped for the run through the shared lean-session.sh, as the lean shortcuts do
# (play-any.sh with BC5_LEAN=1), owned by this script's pid, and started again at the end (restore; its watcher too)
sub('ND=$(sudo -n dmesg 2> /dev/null | wc -l)\n',
    'ND=$(sudo -n dmesg 2> /dev/null | wc -l)\n'
    'LSS=""\n'
    'if [ "${N_LEANSESS:-0}" = 1 ]; then  # exp 0430: the lean session, as his lean shortcuts have it\n'
    '  /usr/bin/bash "$W/lean-session.sh" stop $$ > /dev/null 2>&1; LSS=$?\n'
    '  [ "$LSS" = 0 ] || { echo "lean-session.sh stop: exit $LSS: not started"; exit 1; }\n'
    'fi\n')
sub('LGONE=no; for _ in $(seq 1 60); do pgrep -f "exp0430/n/play-pkg-0425f.sh" > /dev/null || { LGONE=yes; break; }; sleep 1; done\n',
    'LGONE=no; for _ in $(seq 1 60); do pgrep -f "exp0430/n/play-pkg-0425f.sh" > /dev/null || { LGONE=yes; break; }; sleep 1; done\n'
    'if [ "${N_LEANSESS:-0}" = 1 ]; then  # exp 0430: the shell back before the next run\n'
    '  /usr/bin/bash "$W/lean-session.sh" restore $$ > /dev/null 2>&1; LSR=$?\n'
    '  echo "lean session: stop exit $LSS; shell during the run: ${SHELL_RUN:-not read}; restore exit $LSR; shell after: $(systemctl --user is-active plasma-plasmashell.service 2> /dev/null)" >> "$R/$TAG-start.txt"\n'
    'fi\n')
# at G+60: the shell's state, R's promotion (the scheduling of the title's Job workers), the pad's device files, the sound
# streams and the Vulkan driver mapped
sub('  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n',
    '  if [ -n "$G" ] && [ "$NOW" -ge $((G + 60)) ] && [ -z "${HOSTCHK:-}" ]; then HOSTCHK=1  # exp 0430\n'
    '    SHELL_RUN=$(systemctl --user is-active plasma-plasmashell.service 2> /dev/null)\n'
    '    { echo "at G+60 ($NOW s): plasmashell $SHELL_RUN"\n'
    '      for t in /proc/$EP/task/*; do n=$(cat "$t/comm" 2> /dev/null); case "$n" in *Job*|*job*) echo "[$n] $(chrt -p "${t##*/}" 2> /dev/null | sed \'s/.*: //\' | tr \'\\n\' \' \')";; esac; done | sort | uniq -c | head -40\n'
    '      echo "pad files: $(ls -l /proc/$EP/fd 2> /dev/null | grep -o \'/dev/\\(hidraw\\|input/event\\|input/js\\)[0-9]*\' | sort -u | tr \'\\n\' \' \')"\n'
    '      echo "sound streams of the emulator: $(pactl list sink-inputs 2> /dev/null | grep -c "application.process.id = \\"$EP\\"")"\n'
    '      echo "gpu driver: $(grep -o \'/[^ ]*libvulkan_[a-z]*\\.so[^ ]*\' /proc/$EP/maps 2> /dev/null | sort -u | tr \'\\n\' \' \')"; } >> "$R/$TAG-start.txt"\n'
    '  fi\n'
    '  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n')
s = ("#!/usr/bin/env bash\n# BC5 exp 0430: derived by mkrun0430l.py from run0430f.sh (N_TIMED, N_MH, P_HOST; see mkrun0430l.py).\n"
     + s.split("\n", 1)[1])
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", dst, hashlib.md5(s.encode()).hexdigest()[:8])

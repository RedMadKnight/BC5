#!/usr/bin/env python3
"""BC5 experiment 0432: derive run0432f.sh from exp 0430's run0430f.sh (md5 pinned below). Every replacement must match
exactly the stated number of times.
    mkrun0432.py <run0430f.sh> <run0432f.sh>
Changes:
  - everything written lands in ~/bc5-work/exp0432/n; exp 0425's named snapshot, the 14:50 record's gameplay and exp 0412's
    tools and launcher are only read; lock and queue lines say exp 0432;
  - N_SIDE=<script>: started once, at G, as `bash <script> <emulator pid> <out prefix> <play s>` (the profiler,
    prof0432.sh); only that process (its own pid, recorded by us) is signalled at the end (LESSONS R38);
  - N_TIMED=1: the route by time, for the lean build (it writes no journal, so the frame gate has nothing to read):
    cross at N_T0 s, the slot keys N_T1 s later, Continue N_T2 s later, G taken N_T3 s after that. No journal is required.
"""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "a02c3b95", "run0430f.sh is not a02c3b95"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


sub("N=$W/exp0430/n; R=$N/raw;", "N=$W/exp0432/n; R=$N/raw;")
sub("exp 0430 | private run $TAG ($ARM, cap $SECS s), the second title on exp0430/${WANT:0:8}, token $T",
    "exp 0432 | private run $TAG ($ARM, cap $SECS s), the second title on ${WANT:0:8}, token $T")
sub("exp 0430 | claimed: private run $TAG", "exp 0432 | claimed: private run $TAG")
sub("exp 0430 | released: private run $TAG", "exp 0432 | released: private run $TAG")
sub("cd ~/bc5-work/exp0430/n/wd ", "cd ~/bc5-work/exp0432/n/wd ")
sub("$HOME/bc5-work/exp0430/n/wd/_SaveData-pkg-play", "$HOME/bc5-work/exp0432/n/wd/_SaveData-pkg-play")
sub("$HOME/bc5-work/exp0430/n/direct-learned-pkg.txt", "$HOME/bc5-work/exp0432/n/direct-learned-pkg.txt")
sub('pgrep -f "exp0430/n/play-pkg-0425f.sh"', 'pgrep -f "exp0432/n/play-pkg-0425f.sh"')
assert "exp0430" not in s.split("\n", 3)[3], "an exp0430 path is left"

# the side process
sub('EP=""; SP=""\n', 'EP=""; SP=""; SIDEP=""\n')
sub('  [ -n "$SP" ] && kill "$SP" 2> /dev/null\n',
    '  [ -n "$SP" ] && kill "$SP" 2> /dev/null\n  [ -n "$SIDEP" ] && kill "$SIDEP" 2> /dev/null\n')
sub('  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n',
    '  if [ -n "$G" ] && [ -z "$SIDEP" ] && [ -n "${N_SIDE:-}" ]; then  # exp 0432: the profiler, from G\n'
    '    nohup bash "$N_SIDE" "$EP" "$R/$TAG-prof" "$((PLAY > 60 ? PLAY - 20 : PLAY))" > "$R/$TAG-prof.out" 2>&1 < /dev/null & SIDEP=$!\n'
    '    echo "side: $N_SIDE started at $NOW s as pid $SIDEP" >> "$R/$TAG-start.txt"\n'
    '  fi\n'
    '  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break\n')
sub('sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""\n',
    'sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""\n'
    'if [ -n "$SIDEP" ]; then for _ in $(seq 1 90); do [ -d "/proc/$SIDEP" ] || break; sleep 1; done; [ -d "/proc/$SIDEP" ] && kill "$SIDEP" 2> /dev/null; SIDEP=""; fi  # exp 0432: the profiler writes its report first\n')

# the route by time
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
s = ("#!/usr/bin/env bash\n# BC5 exp 0432: derived by mkrun0432.py from exp 0430's run0430f.sh (see mkrun0432.py for the changes).\n"
     + s.split("\n", 1)[1])
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", dst)

#!/usr/bin/env python3
"""BC5 exp 0429: derives run0429f.sh and chain0429.sh from exp 0428's run0428f.sh and chain0428.sh (main 0f335e5b).
    mkrun0429.py <exp 0428 dir> <out dir>
run0429f.sh: everything under ~/bc5-work/exp0429/n; the lock and queue lines say exp 0429; the private input.cfg is the
shared one with RT on and every JobArenaFix line dropped (the private build ignores the key anyway); nothing else.
chain0429.sh: the private normal build ~/bc5-work/exp0429/normal; the long route (the 14:50 record's gameplay at G,
then exp 0379's walk) to G+600 s; the arms below; a crash at the site (TARGET) or a GPU line (KERNEL) does not stop
the chain, so every arm gets its runs; the stops stay: a real pad key, the STOP file, any other class, a second
NOT_ROUTED. Every run has KYTY_BC5_0429_TRACE=1 (the title's thread masks on record)."""
import sys

src_dir, out_dir = sys.argv[1:3]


def one(text, old, new, what):
    if text.count(old) != 1:
        sys.exit('mkrun0429 STOP: %s: anchor occurs %d times' % (what, text.count(old)))
    return text.replace(old, new)


run = open(src_dir + '/run0428f.sh', encoding='utf-8').read()
run = one(run, '#!/usr/bin/env bash\n', '#!/usr/bin/env bash\n# BC5 exp 0429: derived by mkrun0429.py from exp 0428\'s run0428f.sh: exp0429 paths and lock lines, and no\n# JobArenaFix line in the private input.cfg.\n', 'head')
run = one(run, 'N=$W/exp0428/n;', 'N=$W/exp0429/n;', 'N')
run = one(run, 'LINE="exp 0428 | private run $TAG ($ARM, cap $SECS s), the second title on exp0428/${WANT:0:8}, token $T"',
          'LINE="exp 0429 | private run $TAG ($ARM, cap $SECS s), the second title on exp0429/${WANT:0:8}, token $T"', 'LINE')
run = one(run, 'printf \'%s\\n\' "exp 0428 | claimed: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
          'printf \'%s\\n\' "exp 0429 | claimed: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"', 'queue claim')
run = one(run, 'printf \'%s\\n\' "exp 0428 | released: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
          'printf \'%s\\n\' "exp 0429 | released: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"', 'queue release')
a = run.index('if [ -n "${N_ARENA:-}" ]; then')
b = run.index('fi\n', a) + 3
run = run[:a] + ('{ grep -v -i -e \'^RayTracing\\.PPSA03671=\' -e \'^JobArenaFix\\.\' "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; } > "$CFG" || exit 1'
                 '  # exp 0429: RT on, no JobArenaFix line\n') + run[b:]
for old, new in [
    ('cd ~/bc5-work/exp0428/n/wd  \\# exp 0428', 'cd ~/bc5-work/exp0429/n/wd  \\# exp 0429'),
    ('$HOME/bc5-work/exp0428/n/wd/_SaveData-pkg-play  \\# exp 0428', '$HOME/bc5-work/exp0429/n/wd/_SaveData-pkg-play  \\# exp 0429'),
    ('$HOME/bc5-work/exp0428/n/direct-learned-pkg.txt  \\# exp 0428', '$HOME/bc5-work/exp0429/n/direct-learned-pkg.txt  \\# exp 0429'),
    ('pgrep -f "exp0428/n/play-pkg-0425f.sh"', 'pgrep -f "exp0429/n/play-pkg-0425f.sh"'),
]:
    run = one(run, old, new, old[:30])
if 'exp0428' in run or 'N_ARENA' in run:
    sys.exit('mkrun0429 STOP: run0429f.sh still names exp0428 or N_ARENA')
open(out_dir + '/run0429f.sh', 'w', encoding='utf-8', newline='\n').write(run)

ch = open(src_dir + '/chain0428.sh', encoding='utf-8').read()
a = ch.index('#!/usr/bin/env bash\n'); b = ch.index('set -u\n')
ch = ch[:a] + '''#!/usr/bin/env bash
# BC5 exp 0429 (derived by mkrun0429.py from exp 0428's chain0428.sh): the job-arena crash with the workaround gone from
# the code, on the long route: the 14:50 record's gameplay at G, then exp 0379's walk, to G+600 s; RT on; slot 4; the
# named snapshot; the private normal build of exp 0429 (one binary; only the switches differ). One BOX-LOCK line.
#   arms (every run also KYTY_BC5_0429_TRACE=1):
#     C  none of the candidates (exp 0425 C1 and exp 0428's way 2 as the shared defaults have them)
#     P  KYTY_BC5_0429_PRIO_ORDER=1 (not in screen2: it adds to M as Y)
#     M  KYTY_BC5_0429_GUEST_CPUS=1 (the title's own CPU requests mapped onto the host, derived at run time)
#     Y  M + P
#     X  M + P + KYTY_BC5_0425_HANDOFF_US=300 (exp 0425 C2)
#   (the first build's arms A and H and its smoke h429X1, with AFFINITY=1, are gone with that build)
#   CHAIN_SET=smoke2:  h429M1 (once: the 13-CPU model runs, the trace shows the map and the masks applied)
#   CHAIN_SET=smoke3:  h429M4 (build 3, the run-time CPU mapping; every arm also BC5_0430_G=0: exp 0430's catcher off for timing)
#     Z  M + KYTY_BC5_0429_PRIO_ORDER=2 (the job-worker band 450-549 at nice -3, lower priorities below it)
#     F  KYTY_BC5_0429_FAST_MUTEX=1 (build 5: the guest mutex as a user-space lock word, futex only when contended)
#   every arm from build 4 on also KYTY_BC5_0429_WAITS=1 (the wait catcher: where each thread is at the fault)
#   CHAIN_SET=screen3: h429C1 h429Z1 h429M5 h429C2 h429Z2 h429M6 (or one or two at a time: rep<k> with REP_TAGS)
#   CHAIN_SET=screen2: h429C1 h429M2 h429Y1 h429X2 h429C2 h429M3 h429Y2 h429X3
#   CHAIN_SET=rep<k>: set by REP_TAGS (the arms that survived, with controls between)
# TARGET (the crash at the site) and KERNEL do not stop the chain. Stops: a real pad key (R51), the STOP file
# ($HERE/STOP or ~/bc5-work/exp0429/STOP, read before each run), any other class, a second NOT_ROUTED.
# usage (on the box, detached, in ~/bc5-work/exp0429): CHAIN_SET=smoke|screen|rep1.. bash chain0429.sh
''' + ch[b:]
ch = one(ch, 'W=$HOME/bc5-work; N=$W/exp0428/n;', 'W=$HOME/bc5-work; N=$W/exp0429/n;', 'chain N')
ch = one(ch, 'BIN=$W/exp0428/kyty_emulator;', 'BIN=$W/exp0429/normal/kyty_emulator;', 'chain BIN')
ch = one(ch, 'say() { echo "chain0428 $(date +%T): $*"; }', 'say() { echo "chain0429 $(date +%T): $*"; }', 'say')
ch = one(ch, '[ -x "$BIN" ] && [ -s "$W/exp0428/binary.md5" ]', '[ -x "$BIN" ] && [ -s "$W/exp0429/normal/binary.md5" ]', 'md5 file 1')
ch = one(ch, 'WANT=$(cat "$W/exp0428/binary.md5")', 'WANT=$(cat "$W/exp0429/normal/binary.md5")', 'md5 file 2')
a = ch.index('case "$SET" in\n'); b = ch.index('esac\n', a) + 5
ch = ch[:a] + '''case "$SET" in
  smoke2) TAGS="h429M1" ;;
  smoke3) TAGS="h429M4" ;;
  screen3) TAGS="h429C1 h429Z1 h429M5 h429C2 h429Z2 h429M6" ;;  # build 4: + the wait catcher in every arm, arm Z  # build 3: the run-time CPU mapping, on exp 0430's fix object
  screen2) TAGS="h429C1 h429M2 h429Y1 h429X2 h429C2 h429M3 h429Y2 h429X3" ;;
  rep[0-9]*) TAGS=${REP_TAGS:?REP_TAGS for a rep set} ;;
  *) say "NOT STARTED, CHAIN_SET is smoke2, smoke3, screen2, screen3 or rep<k>"; exit 1 ;;
esac
''' + ch[b:]
ch = one(ch, '[ -e "$HERE/STOP" ] && { say "NOT STARTED, $HERE/STOP exists"; exit 1; }',
         '{ [ -e "$HERE/STOP" ] || [ -e "$W/exp0429/STOP" ]; } && { say "NOT STARTED, a STOP file exists"; exit 1; }', 'stop file 1')
a = ch.index('armwords() {'); b = ch.index('\n}\n', a) + 3
ch = ch[:a] + '''armwords() {
  case "$1" in
    h429C*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0" ;;
    h429M*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1" ;;
    h429Y*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1 KYTY_BC5_0429_PRIO_ORDER=1" ;;
    h429Z*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1 KYTY_BC5_0429_PRIO_ORDER=2" ;;
    h429F*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_FAST_MUTEX=1" ;;
    h429X*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1 KYTY_BC5_0429_PRIO_ORDER=1 KYTY_BC5_0425_HANDOFF_US=300" ;;
    *) return 1 ;;
  esac
}
''' + ch[b:]
ch = one(ch, 'chain_claim "exp 0428 set $SET: way 2 (compute rings + per-queue state) on the second title\'s fight route, private normal ${WANT:0:8}" 60',
         'chain_claim "exp 0429 set $SET: the job-arena crash on the long route (fight + walk to G+600), private normal ${WANT:0:8}" 60', 'claim')
ch = one(ch, '  [ -e "$HERE/STOP" ] && { say "STOP: $HERE/STOP before $t"; return 1; }',
         '  { [ -e "$HERE/STOP" ] || [ -e "$W/exp0429/STOP" ]; } && { say "STOP: a STOP file before $t"; return 1; }', 'stop file 2')
a = ch.index('  local play=120 walk=0 arena=""'); b = ch.index('\n', a) + 1
ch = ch[:a] + '  local play=600 walk=1  # exp 0429: the long route\n' + ch[b:]
ch = one(ch, 'line=$(N_ARENA=$arena N_WALK_AFTER=$walk N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0428f.sh" "$t" "${t:4:1}" "$play" $aw | grep "^$t ")',
         'line=$(N_WALK_AFTER=$walk N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0429f.sh" "$t" "${t:4:1}" "$play" $aw | grep "^$t ")', 'run line')
ch = one(ch, '''    NO_CRASH | NOT_ROUTED) return 0 ;;
    KERNEL) [ "$SET" = longab ] && return 0; say "STOP: $t is KERNEL"; return 1 ;;  # longab counts hangs per arm; a failed reset ends the chain by itself''',
         '''    NO_CRASH | NOT_ROUTED | TARGET | KERNEL) return 0 ;;  # exp 0429: every arm gets its runs; a failed reset ends the chain by itself''', 'classes')
ch = one(ch, 'python3 "$HERE/check0428.py" rule "$OUT" "$SET"\n', 'python3 "$HERE/check0429.py" "$OUT"\n', 'check')
if 'exp0428' in ch or 'run0428' in ch:
    sys.exit('mkrun0429 STOP: chain0429.sh still names exp 0428')
open(out_dir + '/chain0429.sh', 'w', encoding='utf-8', newline='\n').write(ch)
print('mkrun0429: run0429f.sh and chain0429.sh written')

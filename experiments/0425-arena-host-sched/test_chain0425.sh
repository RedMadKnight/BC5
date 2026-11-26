#!/usr/bin/env bash
# BC5 exp 0425: a dry run of chain0425.sh + run0425f.sh + check0425.py on stand-ins, on the laptop (Git Bash).
# The real scripts run unchanged except two pins (the 14:50 record's md5 and exp 0388's sum of the route save, which
# stand-in files cannot have); they are replaced in the test's copies only, and the test says so.
# Stand-ins: a virtual clock (date +%s, sleep, stat -c %Y), pgrep by pid file, sudo dmesg from a file, distrobox and
# setsid pass-through, exp 0412's launcher with the runner's anchor lines, exp 0413's chain lock include, and a fake
# emulator (a copy of bash.exe, so the runner's md5 of /proc/<pid>/exe is real) that writes the journal's frame
# profile lines, the log's exp 0425 lines, and crashes, hangs the kernel log, stays slow or runs clean by a plan.
# Not covered: real pad keys (no /dev/input here), the box's real chainlock0417.inc, distrobox, the GPU, the kernel.
# usage: test_chain0425.sh [scenario ...]     scenarios: full kernel target-stop stopfile noroute rule
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PY="/c/Program Files/Python314/python"
SCEN=${*:-"rule target-stop kernel stopfile noroute full"}
PASS=0; FAILS=0
ok() { if [ "$2" = 0 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAILS=$((FAILS + 1)); echo "FAIL $1"; [ -n "${3:-}" ] && printf '%s\n' "$3" | tail -25 | sed 's/^/     /'; fi; }

setup() {  # a fresh world in $T
  T=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-0425.XXXXXX") || exit 1
  export FAKE_T=$T HOME=$T/home XDG_RUNTIME_DIR=$T/run USER=tester
  W=$HOME/bc5-work; X=$W/exp0412
  mkdir -p "$T/bin" "$T/run" "$X" "$W/exp0425" "$W/exp0413/n" "$W/exp0425/inputs/saves-live-47aefd45/sdata" "$W/exp0330/wd" "$T/chain"
  : > "$T/run/wayland-1"; date +%s > "$T/clock"; : > "$T/dmesg.txt"
  # --- stand-ins
  cat > "$T/bin/date" << 'EOF'
#!/usr/bin/bash
if [ "$*" = "+%s" ]; then cut -d. -f1 "$FAKE_T/clock"; else exec /usr/bin/date "$@"; fi
EOF
  cat > "$T/bin/sleep" << 'EOF'
#!/usr/bin/bash
c=$(cat "$FAKE_T/clock"); echo "$c ${1%s}" | awk '{printf "%.2f\n", $1 + $2}' > "$FAKE_T/clock.t" && mv -f "$FAKE_T/clock.t" "$FAKE_T/clock"
/usr/bin/sleep 0.15  # longer than the fake emulator's 0.05 s poll, so the journal has caught up
EOF
  cat > "$T/bin/stat" << 'EOF'
#!/usr/bin/bash
if [ "$1" = -c ] && [ "$2" = %Y ]; then [ -e "$3" ] && cut -d. -f1 "$FAKE_T/clock"; else exec /usr/bin/stat "$@"; fi
EOF
  cat > "$T/bin/pgrep" << 'EOF'
#!/usr/bin/bash
alive() { [ -s "$1" ] && kill -0 "$(cat "$1")" 2> /dev/null && cat "$1"; }
case "$*" in
  *play-pkg-0425f.sh*) alive "$FAKE_T/launch.pid" ;;
  *kyty_emulator*) alive "$FAKE_T/emu.pid" ;;
  *) exit 1 ;;
esac
EOF
  printf '#!/usr/bin/bash\n[ "$1" = -n ] && [ "$2" = dmesg ] && exec cat "$FAKE_T/dmesg.txt"\nexit 1\n' > "$T/bin/sudo"
  printf '#!/usr/bin/bash\n[ "$1 $2 $3" = "enter ubuntu --" ] || exit 1\nshift 3\nexec "$@"\n' > "$T/bin/distrobox"
  printf '#!/usr/bin/bash\nexec "$@"\n' > "$T/bin/setsid"
  printf '#!/usr/bin/bash\necho 2026-11-15 08:00:00\n' > "$T/bin/uptime"
  { echo '#!/usr/bin/bash'; echo 'a=(); for x in "$@"; do case "$x" in /*) a+=("$(cygpath -w "$x")") ;; *) a+=("$x") ;; esac; done'
    echo "\"$PY\" -I \"\${a[@]}\" | tr -d '\\r'"; } > "$T/bin/python3"  # Windows Python: Windows paths in, CRLF out
  chmod +x "$T/bin/"*
  # --- exp 0412's tools and launcher, exp 0413's words and chain lock
  for f in sampler0412b.sh fuse0412.sh wd0412.sh; do printf '#!/usr/bin/bash\nexit 0\n' > "$X/$f"; chmod +x "$X/$f"; done
  (cd "$X" && md5sum sampler0412b.sh fuse0412.sh | sed 's/ \*/  /') > "$X/tools.md5"
  cat > "$X/play-pkg-0412.sh" << EOF
#!/usr/bin/env bash
# stand-in of exp 0412's derived launcher: only the runner's anchor lines and an emulator start
ulimit -c 0
ENVF=\$HOME/bc5-work/bc5-run.env
while read -r _l; do :
done < "\$ENVF"
LOG=$X/play-last.log  # exp 0412: own log
cd ~/bc5-work
export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play
export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg.txt
echo \$\$ > "\$FAKE_T/launch.pid"; rm -f "\$FAKE_T/emu.pid"
"\$BC5_EMU" "\$FAKE_T/emu.sh" > "\$LOG" 2>&1 &
e=\$!  # Git Bash: the child's /proc environ is complete only some time after its start; wait for it (Linux: final at exec)
for _ in \$(seq 1 100); do tr '\\0' '\\n' < /proc/\$e/environ 2> /dev/null | grep -q '^KYTY_BC5_SAVEDATA_DIR=' && tr '\\0' '\\n' < /proc/\$e/environ | grep -q '^BC5_EMU=' && break; /usr/bin/sleep 0.1; done
/usr/bin/sleep 0.2; echo \$e > "\$FAKE_T/emu.pid"
wait
EOF
  chmod +x "$X/play-pkg-0412.sh"; (cd "$X" && md5sum play-pkg-0412.sh | sed 's/ \*/  /') > "$X/built.md5"
  : > "$W/bc5-run.env"; : > "$W/direct-learned-none.txt"; printf 'RayTracing.TITLE2=off\nJobArenaFix.TITLE2=on\n' > "$W/input.cfg"
  printf 'BC5_DIRECT_GPU_CHECK=1\nBC5_DIRECT_SHADOW_LABELS=1\nMALLOC_ARENA_MAX=2\n' > "$W/exp0413/n/words0413nz.txt"
  cat > "$W/exp0413/n/chainlock0417.inc" << 'EOF'
# stand-in of exp 0413's chain lock (the box's file is not read here)
chain_claim() { LOCK=$HOME/bc5-work/BOX-LOCK; [ -s "$LOCK" ] && return 1; CHAIN_LOCKLINE="stand-in chain | $1 | $2 min"; printf '%s\n' "$CHAIN_LOCKLINE" > "$LOCK"; export CHAIN_LOCKLINE; }
chain_release() { grep -qxF -- "$CHAIN_LOCKLINE" "$HOME/bc5-work/BOX-LOCK" && : > "$HOME/bc5-work/BOX-LOCK"; echo "chain lock released" >> "$FAKE_T/released"; }
EOF
  echo "save" > "$W/exp0425/inputs/saves-live-47aefd45/sdata/file.bin"
  printf 'press cross\nwait 500\n' > "$W/exp0425/inputs/fight1450-play.cmd"; echo "FIGHTMARK" >> "$W/exp0425/inputs/fight1450-play.cmd"
  cp /usr/bin/bash.exe "$W/exp0425/kyty_emulator"; md5sum < "$W/exp0425/kyty_emulator" | cut -d' ' -f1 > "$W/exp0425/binary.md5"
  # --- the fake emulator, one plan word per start: crash | clean | kernel | other | noroute | stop (clean + a STOP file)
  cat > "$T/emu.sh" << 'EOF'
now() { cut -d' ' -f1 "$FAKE_T/clock"; }
mode=$(head -1 "$FAKE_T/plan"); sed -i 1d "$FAKE_T/plan"; [ -n "$mode" ] || mode=clean
[ "$mode" = stop ] && { : > "$FAKE_T/chain/STOP"; mode=clean; }
J=$HOME/bc5-data/captures/play-$$/gc; mkdir -p "$J"; J=$J/direct.log; : > "$J"
[ "${KYTY_BC5_JOB_ARENA_FIX:-}" = 0 ] && echo "game fix (temporary, exp 0359): job-arena fix OFF for TITLE2 (input.cfg off)"
[ "${KYTY_BC5_0425_CATCH:-}" = 1 ] && { echo "[bc5] exp 0425: catcher ON"; echo "game fix: job-arena hook PASS-THROUGH for exp 0425's catcher: site +0x3cca87b"; }
[ -n "${KYTY_BC5_0425_WAKE_SLICE_US:-}" ] && { echo "[bc5] exp 0425: C1 wake slice ON (200 us)"; echo "[bc5] exp 0425 slice: start tid 77 'Job Hi 0' prio 500 policy 0 nice 0: set rc 0 errno 0, read back runtime 200000 ns nice 0"; }
[ -n "${KYTY_BC5_0425_HANDOFF_US:-}" ] && { echo "[bc5] exp 0425: C2 handoff ON (300 us)"; echo "[bc5] exp 0425 handoff: 1 handoffs, 1 ended by the resume, 0 at the bound, mean 40.0 us"; }
[ -n "${KYTY_BC5_0425_DIRECT_WAKE:-}" ] && echo "[bc5] exp 0425: C3 direct wake ON"
[ "${KYTY_BC5_0425_PLAYGO_LOCUS:-}" = slow ] && echo "[bc5] exp 0425: P1 locus SLOW ON"
[ -n "${KYTY_BC5_0425_PLAYGO_PREFETCH_MS:-}" ] && echo "[bc5] exp 0425: P2 prefetch delay ON (500 ms)"
[ -n "${KYTY_BC5_0425_PLAYGO_CALL_US:-}" ] && echo "[bc5] exp 0425: P3 call cost ON (200 us)"
[ "${KYTY_BC5_0425_CATCH:-}" = 1 ] && { echo "[bc5] exp 0425 playgo: PlayGoGetLocus call #1 on 'game-main'"; echo "[bc5] exp 0425 playgo: PlayGoPrefetch call #1 on 'game-main'"; }
T0=$(now); last=$T0; loadend=""; fight=""; lastfps=$T0
while :; do
  t=$(now); c=$(grep -c 'press cross' "$KYTY_BC5_INPUT_CMD" 2> /dev/null); grep -c . "$KYTY_BC5_INPUT_CMD" > "$KYTY_BC5_INPUT_CMD.done" 2> /dev/null
  if [ "${c:-0}" -ge 3 ] && [ -z "$loadend" ]; then loadend=$(echo "$t" | awk '{printf "%.2f", $1 + 12}'); fi
  gap=33; slow=0
  awk -v t="$t" -v a="$T0" 'BEGIN {exit !(t - a < 40)}' && slow=1
  [ -n "$loadend" ] && awk -v t="$t" -v e="$loadend" 'BEGIN {exit !(t < e)}' && gap=300
  [ "$mode" = noroute ] && [ "${c:-0}" -ge 1 ] && gap=300
  if [ "$slow" = 0 ]; then
    awk -v a="$last" -v b="$t" -v g="$gap" -v z="$T0" 'BEGIN {for (x = a + g / 1000; x <= b; x += g / 1000) printf "frame profile: t %.2f s, %.1f ms since the last flip; game thread inside the host 5.0 ms, outside 6.0; GPU busy 7.0 ms\n", x - z, g}' >> "$J"
  fi
  last=$t
  if awk -v t="$t" -v l="$lastfps" 'BEGIN {exit !(t - l >= 5)}'; then echo "fps counter t $(echo "$t $T0" | awk '{print $1 - $2}') s: 150 flips in 5.0 s, longest gap 40.0 ms"; lastfps=$t; fi
  if [ -z "$fight" ] && grep -q FIGHTMARK "$KYTY_BC5_INPUT_CMD" 2> /dev/null; then fight=$t; fi
  if [ -n "$fight" ] && awk -v t="$t" -v f="$fight" 'BEGIN {exit !(t - f >= 10)}'; then
    case "$mode" in
      crash) echo "[bc5] exp 0425 catch: owner takes crash-type job #1, Hi readied-not-running 2 (owner calls 4000, with Hi pending 12; crash-type with Hi pending 1; Hi readied 900)"
             echo "Access violation: Read [000000000000000c]"; echo "kyty_exception_handler: 0000000903d7eca0"; exit 65 ;;
      other) echo "Access violation: Write [0000000000000026]"; echo "off=0000000003ba1bdf, module=eboot.bin"; exit 65 ;;
      kernel) echo "[ 99.0] amdgpu 0000:03:00.0: amdgpu: ring comp_1.0.0 timeout, signaled seq=1, emitted seq=2" >> "$FAKE_T/dmesg.txt"; mode=clean ;;
    esac
  fi
  /usr/bin/sleep 0.05
done
EOF
  cp "$HERE/chain0425.sh" "$HERE/check0425.py" "$T/chain/"
  sed -e 's/b0f9ad5c017a8b43295b3d96a6e78c39/'"$(md5sum < "$W/exp0425/inputs/fight1450-play.cmd" | cut -d' ' -f1)"'/' \
      -e 's/9347496fbaf30f25/'"$(cd "$W/exp0425/inputs/saves-live-47aefd45" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16)"'/' \
      "$HERE/run0425f.sh" > "$T/chain/run0425f.sh"
  [ "$(diff "$HERE/run0425f.sh" "$T/chain/run0425f.sh" | grep -c '^>')" = 2 ] || { echo "the test copy differs in more than the two pins"; exit 1; }
  export PATH="$T/bin:$PATH"
  (cd "$T/chain" && MODE=name bash run0425f.sh) > "$T/name.out" 2>&1
}
chain() { (cd "$T/chain" && CHAIN_SET=${SET:-playgo} timeout 3000 bash chain0425.sh) > "$T/chain.out" 2>&1; }
rows() { grep -c . "$W/exp0425/n/chain-rows-${SET:-playgo}.txt" 2> /dev/null || echo 0; }

for s in $SCEN; do
  case "$s" in
  rule)
    d=$(mktemp -d "${TMPDIR:-/tmp}/d19-test-0425r.XXXXXX")
    E="fix-off 1 pass-through 1 catcher-on 1 C1-on 1 C1-set-ok 9 C1-hi-ok 5 C2-on 1 C2-lines 3 C3-on 1 crash-type-taken 0"
    r() { "$PY" -I "$HERE/check0425.py" rule "$(cygpath -w "$d/rows")" | tr -d '\r'; }
    { for t in C1 C2 C3; do echo "f425$t TARGET pad 0 $E"; done; for a in S Y D; do for i in 1 2 3 4; do echo "f425$a$i NO_CRASH pad 0 $E"; done; done; } > "$d/rows"
    o=$(r); [ "$(printf '%s\n' "$o" | grep -c 'HOLDS')" = 3 ]; ok "rule: control 3/3, every arm 4/4 clean and exposed: three HOLDS" $? "$o"
    sed -i 's/^f425S2 NO_CRASH/f425S2 TARGET/' "$d/rows"; o=$(r); printf '%s\n' "$o" | grep -q 'arm S .* REFUTED'; ok "rule: one TARGET in S refutes S" $? "$o"
    sed -i 's/^f425C2 TARGET/f425C2 NO_CRASH/; s/^f425C3 TARGET/f425C3 NO_CRASH/' "$d/rows"; o=$(r); printf '%s\n' "$o" | grep -q 'RULE NO CONCLUSION'; ok "rule: control 1/3: no conclusion" $? "$o"
    { for t in C1 C2 C3; do echo "f425$t TARGET pad 0 $E"; done; for a in S Y D; do for i in 1 2 3 4; do echo "f425$a$i NO_CRASH pad 0 $E"; done; done; } > "$d/rows"
    sed -i 's/^\(f425Y3 NO_CRASH .*\)C2-lines 3/\1C2-lines 0/' "$d/rows"; o=$(r); printf '%s\n' "$o" | grep -q 'arm Y .* NO TEST'; ok "rule: a Y run without handoff lines: NO TEST" $? "$o"
    sed -i 's/^\(f425D1 NO_CRASH .*\)C3-on 1/\1C3-on x/' "$d/rows"; o=$(r); printf '%s\n' "$o" | grep -q 'arm D .* NO TEST'; ok "rule: an unreadable count is unknown, not 0 (R19): NO TEST" $? "$o"
    sed -i 's/^\(f425C1 TARGET .*\)fix-off 1/\1fix-off 0/' "$d/rows"; o=$(r); printf '%s\n' "$o" | grep -q 'f425C1: NO TEST'; ok "rule: a run without the fix-off line does not count" $? "$o"
    rm -rf "$d" ;;
  target-stop)
    setup; printf 'crash\n' > "$T/plan"; chain
    grep -q 'STOP: f425C1 crashed at the site and CHAIN_TARGET_OK is not 1' "$T/chain.out" && [ "$(rows)" = 1 ]
    ok "target-stop: without CHAIN_TARGET_OK the first TARGET stops the chain" $? "$(cat "$T/name.out" "$T/chain.out")"
    grep -q 'CLASS TARGET; exposure fix-off 1 pass-through 1 catcher-on 1 C1-on 0' "$W/exp0425/n/raw/f425C1-summary.txt"; ok "target-stop: the run's class and exposure" $? "$(cat "$W/exp0425/n/raw/f425C1-summary.txt" 2>&1)"
    grep -q 'JobArenaFix.TITLE2=off' "$W/exp0425/n/input-f425C1.cfg" && ! grep -q 'JobArenaFix.TITLE2=on' "$W/exp0425/n/input-f425C1.cfg"; ok "target-stop: the private input.cfg has the fix off" $?
    grep -q "route: gameplay G = " "$W/exp0425/n/raw/f425C1-start.txt"; ok "target-stop: G from the journal gate, not the 45-s fallback" $? "$(grep route: "$W/exp0425/n/raw/f425C1-start.txt")"
    grep -q "down x 3, cross (slot 4)" "$W/exp0425/n/raw/f425C1-start.txt" && grep -q "the 14:50 record's gameplay (3 lines) queued" "$W/exp0425/n/raw/f425C1-start.txt"; ok "target-stop: slot 4 and the record queued at G" $? "$(cat "$W/exp0425/n/raw/f425C1-start.txt")"
    [ ! -s "$W/BOX-LOCK" ] && grep -q released "$T/released"; ok "target-stop: the chain lock released" $?
    grep -q 'named snapshot' "$T/name.out" || grep -q 'exists' "$T/name.out"; [ -d "$W/exp0425/saves-named/TITLE2" ]; ok "target-stop: MODE=name made the named snapshot from exp 0358's copy" $? "$(cat "$T/name.out")"
    ;;
  kernel)
    setup; printf 'clean\nkernel\n' > "$T/plan"; CHAIN_TARGET_OK=1 chain
    grep -q 'STOP: f425L1 is KERNEL' "$T/chain.out" && [ "$(rows)" = 2 ]; ok "kernel: an amdgpu timeout line stops the chain after that run (R55)" $? "$(cat "$T/chain.out")"
    grep -q 'CLASS NO_CRASH' "$W/exp0425/n/raw/f425C1-summary.txt"; ok "kernel: the clean control run before it is NO_CRASH" $? "$(cat "$W/exp0425/n/raw/f425C1-summary.txt" 2>&1)"
    ;;
  stopfile)
    setup; printf 'stop\nclean\n' > "$T/plan"; CHAIN_TARGET_OK=1 chain
    grep -q 'STOP: .*/STOP before f425L1' "$T/chain.out" && [ "$(rows)" = 1 ]; ok "stopfile: a STOP file stops the chain before the next run" $? "$(cat "$T/chain.out")"
    ;;
  noroute)
    setup; printf 'noroute\nnoroute\n' > "$T/plan"; CHAIN_TARGET_OK=1 chain
    grep -q 'STOP: f425C1 not routed twice' "$T/chain.out" && [ -e "$W/exp0425/n/raw/f425C1R-start.txt" ]; ok "noroute: one replacement, then the chain stops" $? "$(cat "$T/chain.out")"
    ;;
  full)
    for SET in playgo sched; do
      setup; { echo crash; echo clean; echo clean; echo clean; echo clean; echo clean; echo clean; echo crash; echo clean; echo clean; echo clean; echo crash; echo clean; echo clean; echo clean; } > "$T/plan"
      CHAIN_TARGET_OK=1 chain
      [ "$(rows)" = 15 ] && grep -q 'control: 3 of 3 at the site' "$T/chain.out" && [ "$(grep -c 'HOLDS' "$T/chain.out")" = 3 ] && ! grep -q 'NO TEST' "$T/chain.out"
      ok "full $SET: 15 runs, control 3/3, the rule prints three HOLDS and no NO TEST" $? "$(cat "$T/chain.out")"
      if [ "$SET" = playgo ]; then
        grep -q 'P1-on 1 P1-calls 1' "$W/exp0425/n/raw/f425L1-summary.txt" && grep -q 'P2-on 1 P2-calls 1' "$W/exp0425/n/raw/f425F1-summary.txt" && grep -q 'P3-on 1 pg-calls 2' "$W/exp0425/n/raw/f425K1-summary.txt" && grep -q 'P1-on 0 P1-calls 1 P2-on 0 P2-calls 1 P3-on 0' "$W/exp0425/n/raw/f425C1-summary.txt"
      else
        grep -q 'C1-hi-ok 1' "$W/exp0425/n/raw/f425S1-summary.txt" && grep -q 'C2-lines 1' "$W/exp0425/n/raw/f425Y1-summary.txt" && grep -q 'C3-on 1' "$W/exp0425/n/raw/f425D1-summary.txt" && grep -q 'C1-on 0 C1-set-ok 0 C1-hi-ok 0 C2-on 0 C2-lines 0 C3-on 0' "$W/exp0425/n/raw/f425C4-summary.txt"
      fi
      ok "full $SET: each arm's exposure counted, none of the candidates' in the control" $? "$(cat "$W"/exp0425/n/raw/f425??-summary.txt | head -8)"
    done
    SET=playgo
    ;;
  esac
done
echo "== $PASS passed, $FAILS failed"
[ "$FAILS" = 0 ]

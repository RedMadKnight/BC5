#!/usr/bin/env bash
# BC5 exp 0431: the first title on a SHARED build with or without way 2's five words in the environment (no build needed:
# the words are read with std::getenv, lean too). One chain under ONE BOX-LOCK line (chainlock0417.inc); each run goes
# through exp 0428's start0428l.sh (t1 kind: a copy of play-t1.sh with EMU, LOG and the working directory changed,
# the private wd $N/wda), which ends the run with SIGTERM after <seconds> and records kernel lines and crash text.
#   saves: a named snapshot of the first title's saves made ONCE ($S/saves-named, sum in saves-named.sum, LESSONS R45); the
#          private wda/_SaveData is reset from it before every run; the wd's own _SaveData is put back at the end
#   route: by time (tools/scripts/t1-route.sh's): a cross at 40 and 65 s (title, continue), then walking and jumping
#   shots: spectacle at SHOTS seconds into the run, to $S/shots/<tag>-<s>.png (the water / black-block check, ADR 0009)
#   pad:   real pad keys (evtest) are counted and reported only: the maintainer, 2026-11-16, his pad presses change nothing: the fault came
#          and was caught, which was the point (a caught fault is data whatever the pad did)
# The chain stops at any kernel line, crash text, a run that does not PASS or $S/STOP (read between runs).
# No fuse, no watchdog: the only kill is the runner's end of a timed run. ulimit -c 0.
# usage (on the box, detached, in ~/bc5-work/exp0431): bash t1_0431.sh <secs> <tag>:<n|l|x>:<W|D> ...
#   XWORDS="K=V ...": extra words for every run (e.g. exp 0430's catcher words).
#   n/l = the shared normal/lean build; x = a private build named by XBIN=<path> (e.g. exp 0430's fix build)
#   W = the five way-2 words in the environment; D = no words (the build's own defaults: after int0431 that is way 2
#   from kSoft). No one-ring arm: the maintainer forbade one-ring comparisons (the top session, 2026-11-16).
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; WD=$N/wda; S=$W/exp0431; ST=$S/start0431.sh
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
SECS=${1:?seconds}; shift
SHOTS=${SHOTS:-60 90 120 150 180}
WAY2=(BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3)
LIVE=$W/_SaveData/TITLE1B
sumof() { (cd "$1" && find TITLE1B -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
say() { echo "$(date +%T) $*"; }
cd "$S" || exit 1
pgrep '^kyty_emulator' > /dev/null && { say "NOT STARTED: an emulator runs"; exit 1; }
[ -s "$ST" ] && bash -n "$ST" || { say "NOT STARTED: no start0431.sh"; exit 1; }
for a in "$@"; do t=${a%%:*}; [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ] && { say "NOT STARTED: tag $t used"; exit 1; }; done
# the named snapshot, once
if [ ! -d "$S/saves-named/TITLE1B" ]; then
    mkdir -p "$S/saves-named" && cp -a "$LIVE" "$S/saves-named/TITLE1B" || { say "NOT STARTED: no snapshot"; exit 1; }
    sumof "$S/saves-named" > "$S/saves-named.sum"; chmod -R a-w "$S/saves-named"
    say "named snapshot made from $LIVE: $(cat "$S/saves-named.sum")"
fi
[ "$(sumof "$S/saves-named")" = "$(cat "$S/saves-named.sum")" ] || { say "NOT STARTED: the snapshot does not read as its sum"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0431: the first title on the shared builds, way 2 ($*)" $(( ($# * (SECS + 40)) / 60 + 5 )) || { say "NOT STARTED: no lock"; exit 1; }
KEEP=$WD/_SaveData.before-0431-$$
mv "$WD/_SaveData" "$KEEP" || exit 1
PADS=(); SP=""
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; [ -n "$SP" ] && kill "$SP" 2> /dev/null
        rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; chain_release; }
trap fin EXIT
mkdir -p "$S/shots"
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
CMD=$S/route-t1.cmd
{ echo "wait 40000"; echo "press cross"; echo "wait 25000"; echo "press cross"; echo "wait 15000"
  for i in $(seq 1 $(( SECS > 185 ? (SECS - 80) / 3 : 30 ))); do  # the walk lasts the whole run (3.5 s a loop)
    echo "stick l 128 0"; echo "wait 1500"; echo "press cross"; echo "wait 600"
    echo "stick l 255 128"; echo "wait 1000"; echo "press cross"; echo "wait 400"
  done
  echo "stick l 128 128"; } > "$CMD"
for a in "$@"; do
    IFS=: read -r tag v arm <<< "$a"
    [ -e "$S/STOP" ] && { say "STOP file: chain stopped before $tag"; break; }
    pgrep -x kyty_emulator > /dev/null && { say "an emulator runs (the maintainer?): chain stopped before $tag"; break; }
    case "$v" in l) BIN=$LB ;; n) BIN=$NB ;; x) BIN=${XBIN:-} ;; *) say "binary $v: n, l or x"; break ;; esac
    [ -x "$BIN" ] || { say "no binary for $v ($BIN)"; break; }
    WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
    read -r -a XW <<< "${XWORDS:-}"  # extra KEY=VALUE words for every run (exp 0430's catcher words)
    WORDS=(); case "$arm" in W) WORDS=("${WAY2[@]}") ;; D) ;; *) say "arm $arm: W or D"; break ;; esac
    rm -rf "$WD/_SaveData"; mkdir "$WD/_SaveData" && cp -a "$S/saves-named/TITLE1B" "$WD/_SaveData/" && chmod -R u+w "$WD/_SaveData" || { say "saves not put in place"; break; }
    [ "$(sumof "$WD/_SaveData")" = "$(cat "$S/saves-named.sum")" ] || { say "the private copy does not read as the snapshot"; break; }
    : > "$S/$tag-pad.txt"; PADS=()
    for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$S/$tag-pad.txt" & PADS+=($!); done
    ( for _ in $(seq 1 120); do pgrep -x kyty_emulator > /dev/null && break; sleep 0.5; done; t0=$(date +%s)
      for s in $SHOTS; do while [ $(( $(date +%s) - t0 )) -lt "$s" ]; do sleep 0.5; done
        pgrep -x kyty_emulator > /dev/null || break
        XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WL timeout 20 spectacle -b -n -f -o "$S/shots/$tag-$s.png" > /dev/null 2>&1; done ) & SP=$!
    say "== $tag: $(case "$v" in l) echo lean ;; n) echo normal ;; x) echo "private $BIN" ;; esac) $(echo "$WANT" | cut -c1-8), arm $arm (${WORDS[*]:-no words: the build defaults}; extra: ${XW[*]:-none}), $SECS s"
    line=$(P_BIN=$BIN P_WANT=$WANT bash "$ST" "$tag" t1 "$SECS" KYTY_BC5_INPUT_CMD="$CMD" KYTY_BC5_FPS_COUNTER=1 "${WORDS[@]}" "${XW[@]}" 2>&1 | tail -1)
    kill "$SP" 2> /dev/null; SP=""
    [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null
    pk=$(wc -l < "$S/$tag-pad.txt")
    echo "$line; real pad keys $pk; shots $(ls "$S/shots" | grep -c "^$tag-")"
    L=$R/$tag-play.log
    echo "$tag w428c lines $(grep -a -c 'tag w428c' "$L" 2> /dev/null); the last: $(grep -a 'tag w428c' "$L" 2> /dev/null | tail -1 | cut -c1-1500)"
    case "$line" in *"PASS: ran $SECS s"*"kernel lines 0, crash lines 0"*) say "$tag: PASS" ;; *) say "$tag: NOT A PASS: chain stopped"; break ;; esac
    sleep 5
done
say "t1_0431 ended"

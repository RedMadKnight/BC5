#!/usr/bin/env bash
# BC5 exp 0412 (g412b): on the box, after mk0412b.sh: put the wrappers, the sampler and the fuse in place, make the
# private ASTRO BOT launcher, run the stand-in checks, and make the four desktop shortcuts (shortcut0412b.sh).
# Stand-ins (no emulator is started):
#   - every arm's "dry" word (both wrappers): the pins hold and the words are the arm's;
#   - the sampler against a 12-s "sleep" under another name, with a second one as the mount process;
#   - the fuse against a memory eater inside the container (a copy of the container's bash that builds a 700 MB string):
#     fuse0412.sh sets memory.max to what the cgroup holds + 300 MiB and no swap, the kernel must kill the eater (137),
#     and the limits must be back at "max" afterwards. This is the one step that writes a cgroup file.
# The files come from a stage directory under ~/bc5-work/exp0412 (this script's own), checked against stage.sha256.
# The old wrapper is kept beside the new one. The shared play-astro.sh and the shared build are only read.
# BOX-LOCK by an atomic hard-link claim, our exact line removed at the end.
# usage (on the box, no emulator running): bash install0412b.sh <sha256 of stage.sha256>
set -u
export LC_ALL=C
WM=${1:?the sha256 of stage.sha256}
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; ST=$(cd "$(dirname "$0")" && pwd); R=$X/raw-b
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
case "$ST" in "$X"/stage-*) ;; *) die "not run from a stage directory of exp0412" ;; esac
[ "$(sha256sum < "$ST/stage.sha256" | cut -d' ' -f1)" = "$WM" ] && (cd "$ST" && sha256sum -c --quiet stage.sha256) || die "the staged files are not what was sent"
[ -s "$X/built.md5" ] && grep -qxF "$(m "$X/bin/kyty_emulator")  bin/kyty_emulator" "$X/built.md5" && grep -aqF "tag g412b" "$X/bin/kyty_emulator" || die "the second build is not in place (run mk0412b.sh first)"
[ "$(m "$W/play-astro.sh")" = 48238ccdcaaec58b4f966202586d83c8 ] || die "the shared play-astro.sh is not 48238ccd"
[ "$(m "$W/kytyplus-build/src/kyty_emulator")" = 4d2b1b1dd52eaea6e3195500f604e73e ] || die "the shared build is not 4d2b1b1d"
LINE="guard exp 0412 | install g412b wrappers, fuse stand-in and shortcuts, token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: install g412b | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: install g412b | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
mkdir -p "$R" || die "mkdir"
# 1. The private ASTRO BOT launcher: the shared one with ulimit -c 0, its own log, and the capture word.
CAPL='case "${BC5_0412_CAPTURE:-}" in 0) unset PLAY_CAPTURE ;; 1) export PLAY_CAPTURE=1 ;; esac  # exp 0412 (g412b): the capture arm'
sed -e "s|^LOG=.*|LOG=$X/astro-last.log  # exp 0412: own log|" -e '/^set -u$/a ulimit -c 0  # exp 0412: no core dump of the emulator (the 11-09 rule)' \
    -e "/^done < \"\\\$ENVF\"\$/a $CAPL" "$W/play-astro.sh" > "$R/play-astro-0412.sh" || die "the astro launcher"
bash -n "$R/play-astro-0412.sh" || die "the astro launcher does not parse"
[ "$(diff "$W/play-astro.sh" "$R/play-astro-0412.sh" | grep -c '^[<>]')" = 4 ] && [ "$(grep -c '^ulimit -c 0' "$R/play-astro-0412.sh")" = 1 ] &&
    [ "$(grep -c '^case "${BC5_0412_CAPTURE:-}" in 0) unset PLAY_CAPTURE ;; 1) export PLAY_CAPTURE=1 ;; esac' "$R/play-astro-0412.sh")" = 1 ] &&
    [ "$(grep -c "^LOG=$X/astro-last.log" "$R/play-astro-0412.sh")" = 1 ] && grep -q '^EMU=~/bc5-work/kytyplus-build/src/kyty_emulator$' "$R/play-astro-0412.sh" ||
    die "the astro launcher is not the shared one with the three changes"
# The capture line by itself: 0 unsets, 1 sets, nothing leaves the settings file's word.
CL=$(grep '^case "${BC5_0412_CAPTURE' "$R/play-astro-0412.sh"); PR='printf "%s" "${PLAY_CAPTURE-unset}"'
[ "$(env -i PLAY_CAPTURE=1 BC5_0412_CAPTURE=0 /usr/bin/bash -c "$CL"$'\n'"$PR")" = unset ] && [ "$(env -i BC5_0412_CAPTURE=1 /usr/bin/bash -c "$CL"$'\n'"$PR")" = 1 ] &&
    [ "$(env -i PLAY_CAPTURE=1 /usr/bin/bash -c "$CL"$'\n'"$PR")" = 1 ] && [ "$(env -i /usr/bin/bash -c "$CL"$'\n'"$PR")" = unset ] || die "the capture line does not do what it says"
chmod +x "$R/play-astro-0412.sh"
# 2. The files.
old=$(m "$X/play-guard-0412.sh")
if [ -n "$old" ] && [ "$old" != "$(m "$ST/play-guard-0412.sh")" ] && [ ! -e "$X/play-guard-0412.sh.before-g412b-${old:0:8}" ]; then
  cp -p "$X/play-guard-0412.sh" "$X/play-guard-0412.sh.before-g412b-${old:0:8}" || die "cannot keep the old wrapper"
fi
for f in play-guard-0412.sh play-astro-guard-0412.sh sampler0412b.sh fuse0412.sh shortcut0412b.sh; do
  cp -p "$ST/$f" "$X/$f.new-$$" && chmod +x "$X/$f.new-$$" && mv -fT "$X/$f.new-$$" "$X/$f" || die "cannot install $f"
done
cp -p "$R/play-astro-0412.sh" "$X/play-astro-0412.sh.new-$$" && mv -fT "$X/play-astro-0412.sh.new-$$" "$X/play-astro-0412.sh" || die "cannot install the astro launcher"
printf '%s  sampler0412b.sh\n%s  fuse0412.sh\n%s  play-astro-0412.sh\n' "$(m "$X/sampler0412b.sh")" "$(m "$X/fuse0412.sh")" "$(m "$X/play-astro-0412.sh")" > "$X/tools.md5" || die "tools.md5"
# 3. The dry runs.
for a in base ledger low guest orphans cap amm; do
  bash "$X/play-guard-0412.sh" "$a" dry > "$R/dry-$a.out" 2>&1 || die "the dry run of $a failed: $(tail -1 "$R/dry-$a.out")"
  grep -q '^dry: nothing started$' "$R/dry-$a.out" && grep -q '^dry: sampler pinned' "$R/dry-$a.out" || die "the dry run of $a did not end as expected"
  case "$a" in orphans | cap | amm) grep -q '^dry: fuse pinned, would set memory.max and memory.swap.max to 12300 2048 MiB$' "$R/dry-$a.out" || die "the dry run of $a has no fuse" ;;
               *) grep -q '^dry: fuse none for this arm$' "$R/dry-$a.out" || die "the dry run of $a has a fuse" ;; esac
  echo "  $a: $(sed -n 's/^dry: arm [a-z]*, \([0-9]*\) words; the arm.s words: /\1 words; /p' "$R/dry-$a.out" | cut -c1-230)"
done
grep -q 'BC5_GUARD_LEDGER=1 BC5_DIRECT_LAZY_RELEASE=10,eager $' "$R/dry-orphans.out" || die "the orphans arm's words"
grep -q 'BC5_GUARD_LEDGER=1 BC5_DIRECT_LAZY_RELEASE=10,eager BC5_GUARD_PIN_CAP=11600 BC5_GUARD_CAP_ACT=1 $' "$R/dry-cap.out" || die "the cap arm's words"
grep -q 'BC5_GUARD_CAP_ACT=1 BC5_GUARD_AMM_BY_USE=1 $' "$R/dry-amm.out" || die "the amm arm's words"
grep -q 'words: BC5_GUARD_LEDGER=1 $' "$R/dry-ledger.out" || die "the ledger arm's words"
for a in off on; do
  bash "$X/play-astro-guard-0412.sh" "$a" dry > "$R/dry-astro-$a.out" 2>&1 || die "the dry run of astro $a failed: $(tail -1 "$R/dry-astro-$a.out")"
  grep -q '^dry: nothing started$' "$R/dry-astro-$a.out" && grep -q '^dry: sampler pinned' "$R/dry-astro-$a.out" && grep -q '^dry: fuse pinned' "$R/dry-astro-$a.out" || die "the dry run of astro $a did not end as expected"
  echo "  astro $a: $(sed -n '1p' "$R/dry-astro-$a.out" | cut -c1-160)"
done
BC5_0412_FUSE=0 bash "$X/play-guard-0412.sh" cap dry | grep -q '^dry: fuse none for this arm$' || die "BC5_0412_FUSE=0 does not leave the fuse out"
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs after the dry runs"
# 4. The sampler against processes of our own.
cp -p "$(command -v sleep)" "$R/standin0412" && cp -p "$(command -v sleep)" "$R/standin0412m" && { "$R/standin0412" 12 & "$R/standin0412m" 12 & }
sleep 1; pgrep -x standin0412 > /dev/null || die "the stand-in process does not run"
rm -f "$R/sampler-standin.txt"
SAMPLER_NAME=standin0412 SAMPLER_MOUNT=standin0412m bash "$X/sampler0412b.sh" "$R/sampler-standin.txt" 5 30 || die "the sampler's stand-in run failed"
wait
rm -f "$R/standin0412" "$R/standin0412m"
n=$(grep -vc '^#' "$R/sampler-standin.txt")
[ "$n" -ge 1 ] && grep -q 'standin0412 [0-9]* ended' "$R/sampler-standin.txt" || die "the sampler's stand-in wrote $n lines and no end line"
last=$(grep -v '^#' "$R/sampler-standin.txt" | tail -1)
[ "$(printf '%s' "$last" | awk -F' [|] ' '{ print NF }')" = 10 ] || die "a sampler line has not 10 groups: $last"
printf '%s' "$last" | awk -F' [|] ' '{ exit !($7 ~ /^[0-9]+ [0-9]+ [0-9]+$/ && $8 ~ /^[0-9]+ [0-9]+ [0-9]+$/ && $9 ~ /^([0-9]+ [0-9]+|- -)$/) }' || die "the sampler's new groups are not numbers: $last"
echo "sampler stand-in: $n lines; last: $(printf '%s' "$last" | cut -c1-200)"
# 5. The fuse against a memory eater in the container.
FL=$R/fuse-standin.log; rm -f "$FL"
bash "$X/fuse0412.sh" restore "$FL"
[ ! -e "$X/fuse.active" ] || die "a fuse marker is left: $(cat "$X/fuse.active")"
CG=/sys/fs/cgroup$(cut -d: -f3 "/proc/$(podman inspect ubuntu --format '{{.State.Pid}}')/cgroup")
[ "$(cat "$CG/memory.max")" = max ] && [ "$(cat "$CG/memory.swap.max")" = max ] || die "the container's cgroup has a limit before the test"
cur=$(($(cat "$CG/memory.current") / 1048576)); ok0=$(awk '$1 == "oom_kill" { print $2 }' "$CG/memory.events")
distrobox enter ubuntu -- /usr/bin/bash -c 'cp /usr/bin/bash "$1/standin0412f" && exec "$1/standin0412f" -c "sleep 10; x=\$(head -c 700000000 /dev/zero | tr \"\\\\0\" x); sleep 4; echo survived"' eat "$R" < /dev/null > "$R/fuse-eater.out" 2>&1 &
EATER=$!
timeout 60 bash "$X/fuse0412.sh" set "$((cur + 300))" 0 "$FL" -x standin0412f
wait "$EATER"; erc=$?
rm -f "$R/standin0412f"
ok1=$(awk '$1 == "oom_kill" { print $2 }' "$CG/memory.events")
sed 's/^/  /' "$FL" | cut -c1-260
[ "$(cat "$CG/memory.max")" = max ] && [ "$(cat "$CG/memory.swap.max")" = max ] && [ ! -e "$X/fuse.active" ] || die "THE LIMITS ARE NOT BACK: memory.max $(cat "$CG/memory.max"), swap $(cat "$CG/memory.swap.max")"
grep -q ' fuse: set on .*memory.max ' "$FL" && grep -q ' fuse: limits back to max ' "$FL" || die "the fuse did not set and restore (see $FL)"
[ "$erc" != 0 ] && [ "$ok1" -gt "$ok0" ] && ! grep -q survived "$R/fuse-eater.out" || die "the eater was not killed by the fuse: exit $erc, oom_kill $ok0 -> $ok1, $(tail -1 "$R/fuse-eater.out" | cut -c1-120)"
echo "fuse stand-in: the cgroup held $cur MiB, limit $((cur + 300)) MiB, the eater ended with $erc, oom_kill $ok0 -> $ok1, limits back at max"
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs after the stand-ins"
# 6. The shortcuts.
WG=$(m "$X/play-guard-0412.sh"); WA=$(m "$X/play-astro-guard-0412.sh")
for a in orphans cap; do WANT_W=$WG bash "$X/shortcut0412b.sh" "$a" || die "the shortcut for $a was not made"; done
for a in astro-off astro-on; do WANT_W=$WA bash "$X/shortcut0412b.sh" "$a" || die "the shortcut for $a was not made"; done
echo "wrapper $WG, astro wrapper $WA, astro launcher $(m "$X/play-astro-0412.sh"), sampler $(m "$X/sampler0412b.sh"), fuse $(m "$X/fuse0412.sh")"
echo "installed: g412b shortcuts"

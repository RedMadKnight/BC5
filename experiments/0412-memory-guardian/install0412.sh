#!/usr/bin/env bash
# BC5 exp 0412: on the box, put the wrapper with the sampler in place, run the stand-in checks (nothing is started: the
# wrapper's "dry" word, and the sampler against a 12-s "sleep"), and make the two desktop shortcuts (shortcut0412.sh).
# The files come from a stage directory under ~/bc5-work/exp0412 (this script's own). The old wrapper is kept beside the new
# one. BOX-LOCK by an atomic hard-link claim, our exact line removed at the end. No emulator is started.
# usage (on the box, no emulator running): bash install0412.sh <md5 of play-guard-0412.sh> <md5 of shortcut0412.sh>
set -u
export LC_ALL=C
WW=${1:?the wrapper md5}; WS=${2:?the shortcut script md5}
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; ST=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
case "$ST" in "$X"/stage-*) ;; *) die "not run from a stage directory of exp0412" ;; esac
[ "$(m "$ST/play-guard-0412.sh")" = "$WW" ] && [ "$(m "$ST/shortcut0412.sh")" = "$WS" ] && [ "$(m "$ST/sampler0412.sh")" = 9dfc33eed6767bd65963c016f380bc44 ] || die "the staged files are not what was sent"
[ "$(m "$X/bin/kyty_emulator")" = 70a3bbeee1afe9b1cf54a83d7982c600 ] || die "the binary is not the guardian's build"
LINE="guard exp 0412 | install wrapper and shortcuts, token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: install | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: install | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
old=$(m "$X/play-guard-0412.sh")
if [ -n "$old" ] && [ "$old" != "$WW" ]; then cp -p "$X/play-guard-0412.sh" "$X/play-guard-0412.sh.before-sampler-${old:0:8}" || die "cannot keep the old wrapper"; fi
for f in play-guard-0412.sh sampler0412.sh shortcut0412.sh; do cp -p "$ST/$f" "$X/$f.new-$$" && chmod +x "$X/$f.new-$$" && mv -fT "$X/$f.new-$$" "$X/$f" || die "cannot install $f"; done
[ "$(m "$X/play-guard-0412.sh")" = "$WW" ] || die "the installed wrapper is not $WW"
mkdir -p "$X/raw"
for a in ledger low; do
  bash "$X/play-guard-0412.sh" "$a" dry > "$X/raw/dry-$a.out" 2>&1 || die "the dry run of $a failed: $(tail -1 "$X/raw/dry-$a.out")"
  grep -q '^dry: nothing started$' "$X/raw/dry-$a.out" && grep -q '^dry: sampler pinned' "$X/raw/dry-$a.out" || die "the dry run of $a did not end as expected"
  sed 's/^/  /' "$X/raw/dry-$a.out" | cut -c1-260
done
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs after the dry runs"
# The sampler against a process of our own: a 12-s sleep under another name, so no other "sleep" is picked.
cp -p "$(command -v sleep)" "$X/raw/standin0412" && { "$X/raw/standin0412" 12 & }
sleep 1; pgrep -x standin0412 > /dev/null || die "the stand-in process does not run (sleep is not a plain binary here?)"
SAMPLER_NAME=standin0412 bash "$X/sampler0412.sh" "$X/raw/sampler-standin.txt" 5 30 || die "the sampler's stand-in run failed"
wait
rm -f "$X/raw/standin0412"
n=$(grep -vc '^#' "$X/raw/sampler-standin.txt")
[ "$n" -ge 1 ] && grep -q 'standin0412 [0-9]* ended' "$X/raw/sampler-standin.txt" || die "the sampler's stand-in wrote $n lines and no end line"
echo "sampler stand-in: $n lines; last: $(grep -v '^#' "$X/raw/sampler-standin.txt" | tail -1 | cut -c1-160)"
for a in ledger low; do WANT_W=$WW bash "$X/shortcut0412.sh" "$a" || die "the shortcut for $a was not made"; done
echo "wrapper $(m "$X/play-guard-0412.sh"), sampler $(m "$X/sampler0412.sh"), shortcut script $(m "$X/shortcut0412.sh")"
echo "installed: 0412 shortcuts"

#!/usr/bin/env bash
# BC5 exp 0413: install the proposed launcher change (integration/play-pkg-0413.diff) on the shared
# ~/bc5-work/play-pkg.sh. The maintainer's own word, 2026-11-12: "zainstaluj zmiane lauchera". play-pkg.sh only;
# play-pkg-log.sh and play-pkg-quiet.sh are not touched. The old file stays as play-pkg.sh.before-0413.
# Checks: no emulator, the lock empty, the current launcher is I_OLD, the new file is I_NEW and passes bash -n.
# usage (on the box): I_OLD=<md5> I_NEW=<md5> instpkg0413.sh <new file>
set -u
export LC_ALL=C
W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; T=$W/play-pkg.sh; NEW=${1:?the new launcher}
: "${I_OLD:?}" "${I_NEW:?}"
m() { md5sum < "$1" | cut -d' ' -f1; }
stop() { echo "instpkg STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$T")" = "$I_OLD" ] || stop "the launcher is $(m "$T"), not $I_OLD"
[ "$(m "$NEW")" = "$I_NEW" ] || stop "the new file is $(m "$NEW"), not $I_NEW"
bash -n "$NEW" || stop "the new file does not parse"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || stop "the box is locked: $(cat "$LOCK" 2> /dev/null)"
LINE="exp 0413 | launcher install (play-pkg.sh), no emulator, token $(date +%s)$$ | $(date '+%F %T')"
t=$LOCK.0413i-$$.new; a=$LOCK.0413i-$$.aside
printf '%s\n' "$LINE" > "$t" && mv -T "$LOCK" "$a" && ln "$t" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$a" "$LOCK"; rm -f "$t"; stop "the claim failed"; }
if [ -s "$a" ]; then mv -fT "$a" "$LOCK"; rm -f "$t"; stop "a foreign line arrived during the claim"; fi
rm -f "$a" "$t"
release() { if grep -qxF -- "$LINE" "$LOCK" 2> /dev/null; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0413i.rel"; mv -fT "$LOCK.0413i.rel" "$LOCK"; echo "lock released"; fi; }
pgrep '^kyty_emulator' > /dev/null && { release; stop "an emulator started"; }
[ -e "$T.before-0413" ] && { release; stop "$T.before-0413 exists already"; }
cp -p "$T" "$T.before-0413" && [ "$(m "$T.before-0413")" = "$I_OLD" ] || { release; stop "the copy of the old launcher does not read back"; }
cp "$NEW" "$T.new-0413" && chmod --reference="$T" "$T.new-0413" && mv -fT "$T.new-0413" "$T" || { release; stop "the install step failed; the old file is $T.before-0413"; }
if [ "$(m "$T")" = "$I_NEW" ] && [ -x "$T" ] && bash -n "$T"; then
    echo "installed: $T is $I_NEW (was $I_OLD, kept as $T.before-0413)"
else
    cp -p "$T.before-0413" "$T"
    echo "instpkg: the new launcher did not read back; restored: $(m "$T")"
    [ "$(m "$T")" = "$I_OLD" ] || { echo "instpkg: THE RESTORE DID NOT READ BACK; the lock is kept"; exit 2; }
    release; exit 1
fi
release

#!/usr/bin/env bash
# BC5 exp 0412 (README section 96): the lean session in the shared launcher. The maintainer's "tak" of 2026-11-14 to
# "the BC5 emulator (lean) shortcut stops the Plasma shell for the time of a play".
#   install-lean-session.sh            dry: shows the diff it would make to ~/bc5-work/play-any.sh, runs
#                                      lean-session.sh dry; changes nothing
#   install-lean-session.sh apply      copies lean-session.sh to ~/bc5-work, keeps play-any.sh.before-lean (once),
#                                      inserts the three lines; refuses while an emulator runs
#   install-lean-session.sh undo       puts play-any.sh.before-lean back and removes ~/bc5-work/lean-session.sh
# The plain "BC5 emulator" shortcut is not touched: the lines act only when BC5_LEAN=1.
# Run on the box, from the directory that holds lean-session.sh (this experiment's directory).
set -u
W=$HOME/bc5-work; P=$W/play-any.sh; B=$P.before-lean; S=$W/lean-session.sh
HERE=$(cd "$(dirname "$0")" && pwd)
ANCHOR='if [ "${BC5_LEAN:-0}" = 1 ]; then'
[ -f "$P" ] || { echo "no $P"; exit 1; }
[ -f "$HERE/lean-session.sh" ] && bash -n "$HERE/lean-session.sh" || { echo "no lean-session.sh beside this script, or it does not parse"; exit 1; }
make() {  # the new play-any.sh on stdout
    awk -v a="$ANCHOR" '
        $0 == a && !done {
            print "# exp 0412 (2026-11-14, the maintainer: the lean shortcut stops the Plasma shell for the play): lean-session.sh stops"
            print "# plasma-plasmashell.service now and starts it again when this launcher is gone, whatever ended it."
            print "if [ \"${BC5_LEAN:-0}\" = 1 ] && [ -x \"$HOME/bc5-work/lean-session.sh\" ]; then /usr/bin/bash \"$HOME/bc5-work/lean-session.sh\" stop $$; fi"
            done = 1
        }
        { print }' "$1"
}
case "${1:-dry}" in
  dry | apply)
    grep -q 'lean-session.sh' "$P" && { echo "play-any.sh already calls lean-session.sh: nothing to do"; exit 0; }
    [ "$(grep -cxF -- "$ANCHOR" "$P")" = 1 ] || { echo "the anchor line is not in play-any.sh exactly once: nothing done"; grep -n 'BC5_LEAN' "$P"; exit 1; }
    make "$P" > "$P.lean-new" && bash -n "$P.lean-new" || { rm -f "$P.lean-new"; echo "the new launcher does not parse: nothing done"; exit 1; }
    [ "$(diff "$P" "$P.lean-new" | grep -c '^>')" = 3 ] && [ "$(diff "$P" "$P.lean-new" | grep -c '^<')" = 0 ] || { rm -f "$P.lean-new"; echo "the change is not 3 lines added: nothing done"; exit 1; }
    echo "play-any.sh now: $(md5sum < "$P" | cut -c1-8); with the change: $(md5sum < "$P.lean-new" | cut -c1-8)"
    diff -u "$P" "$P.lean-new" | sed -n '1,14p'
    if [ "${1:-dry}" = dry ]; then
        rm -f "$P.lean-new"; /usr/bin/bash "$HERE/lean-session.sh" dry; echo "dry: nothing changed"; exit 0
    fi
    pgrep -x kyty_emulator > /dev/null && { rm -f "$P.lean-new"; echo "an emulator runs: nothing done"; exit 1; }
    [ -e "$B" ] || cp -p "$P" "$B" || { rm -f "$P.lean-new"; exit 1; }
    cp "$HERE/lean-session.sh" "$S" && chmod 755 "$S" || { rm -f "$P.lean-new"; echo "could not copy lean-session.sh: nothing done"; exit 1; }
    chmod --reference="$P" "$P.lean-new" && mv -fT "$P.lean-new" "$P" && echo "applied; the old launcher is $B ($(md5sum < "$B" | cut -c1-8))" ;;
  undo)
    [ -f "$B" ] || { echo "no $B: nothing to undo"; exit 1; }
    pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: nothing done"; exit 1; }
    cp -p "$B" "$P" && rm -f "$S" && echo "undone: play-any.sh is $(md5sum < "$P" | cut -c1-8) again; $B kept" ;;
  *) echo "usage: install-lean-session.sh [dry | apply | undo]"; exit 1 ;;
esac

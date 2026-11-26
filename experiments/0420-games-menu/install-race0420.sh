#!/usr/bin/env bash
# BC5 exp 0420: the install of the lean-session race fix in the shared launcher (the maintainer's "Yes, after it" of
# 2026-11-15, relayed by the top: fix-lean-race.sh on the shared play-any.sh and lean-session.sh only, after the night
# series). One lock line. No launch, no GPU. Kit: ~/bc5-work/exp0420/race-107e307a (fix-lean-race.sh and
# lean-session.sh from main 107e307a).
# usage (on the box): install-race0420.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$W/exp0420/race-107e307a
P=$W/play-any.sh; S=$W/lean-session.sh; ST=$W/lean-session.state
. "$N/chainlock0417.inc"
chain_claim "exp 0420: install of the lean-session race fix in the shared play-any.sh and lean-session.sh (maintainer's yes; no launch, no GPU)" 5 || { echo "install-race0420: NOT STARTED"; exit 1; }
trap chain_release EXIT
echo "== $(date '+%F %T') kit: fix-lean-race.sh $(md5sum < "$K/fix-lean-race.sh" | cut -c1-8), lean-session.sh $(md5sum < "$K/lean-session.sh" | cut -c1-8)"
now=$(md5sum < "$P" | cut -c1-8)
echo "shared play-any.sh: $now; lean-session.sh: $(md5sum < "$S" 2> /dev/null | cut -c1-8)"
[ "$now" = 92c090c5 ] || { echo "install-race0420 STOP: play-any.sh is $now, not 92c090c5"; exit 1; }
echo "== dry"
bash "$K/fix-lean-race.sh" dry; rc=$?
[ "$rc" = 0 ] || { echo "install-race0420 STOP: the dry run refused (exit $rc)"; exit 1; }
echo "== conditions"
emu=$(pgrep -a kyty_emulator | cut -c1-120)
[ -z "$emu" ] || { echo "install-race0420 STOP: an emulator runs: $emu"; exit 1; }
[ ! -s "$ST" ] || { echo "install-race0420 STOP: a lean session is active: $ST names $(tr '\n' ' ' < "$ST")"; exit 1; }
[ ! -e "$ST.owner" ] || { echo "install-race0420 STOP: $ST.owner exists: $(cat "$ST.owner/pid" 2> /dev/null)"; exit 1; }
pgrep -af 'play-any.sh|play-pkg.sh|play-t1.sh' > /dev/null && { echo "install-race0420 STOP: a launcher runs: $(pgrep -af 'play-any.sh|play-pkg.sh|play-t1.sh' | cut -c1-120 | head -3)"; exit 1; }
echo "no emulator, no launcher, no lean state: ok"
echo "== apply"
bash "$K/fix-lean-race.sh" apply || { echo "install-race0420 STOP: apply refused"; exit 1; }
echo "== checks"
bash -n "$P" && echo "bash -n play-any.sh: ok"
bash -n "$S" && echo "bash -n lean-session.sh: ok"
echo "play-any.sh $(md5sum < "$P" | cut -c1-8) (expected 1cd59817), lean-session.sh $(md5sum < "$S" | cut -c1-8) (expected 189885ea)"
echo "kept: $(md5sum < "$P.before-race" | cut -c1-8) $P.before-race; $(md5sum < "$S.before-race" 2> /dev/null | cut -c1-8) $S.before-race"
/usr/bin/bash "$S" dry
echo "install-race0420 done $(date +%T)"

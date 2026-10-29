#!/usr/bin/env bash
# BC5 (exp 0373; exp 0370 D7): install bc5-gpu-stall-sampler (beside this file) as a root service. The maintainer
# runs it once:
#   sudo bash install.sh
# It runs the sampler's self-test (no device); installs /usr/local/sbin/bc5-gpu-stall-sampler (root, 755); creates
# ~/bc5-data/captures/gpu-stall/ (his user, 700); checks the register offsets and values once against umr at idle,
# read-only (exp 0370 D3), into install-check.txt there; writes, enables and starts bc5-gpu-stall-sampler.service;
# prints the service's first stalls.log line. Nothing in bc5-gpu-watch, bc5-gpu-hang-watch, bc5-gpu-hang-dump, the
# launchers or the shared builds changes. No sudoers line: the captures are his user's and `systemctl status` needs
# no root. A forced sample needs no root either: echo once > ~/bc5-data/captures/gpu-stall/force
#   bash install.sh --dry-run   (any user, nothing installed: the self-test and the unit as it would be written)
# Undo: sudo bash undo.sh (the captures stay).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
for f in bc5-gpu-stall-sampler bc5-gpu-stall-sampler.service; do
  [ -f "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }
done
if [ "$DRY" = 1 ]; then
  PY=${PYTHON:-$(command -v python3 || command -v python)}
  PYF=""          # whatever Python the caller has (the laptop's runs without -I)
  OWNER=$(id -un)
  HOME_DIR=$HOME
else
  [ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
  PY=/usr/bin/python3
  PYF="-I -B"
  OWNER=${SUDO_USER:-}
  { [ -n "$OWNER" ] && [ "$OWNER" != root ]; } || { echo "run it with sudo from the maintainer's account (SUDO_USER is '$OWNER')"; exit 1; }
  HOME_DIR=$(getent passwd "$OWNER" | cut -d: -f6)
fi
OUT=$HOME_DIR/bc5-data/captures/gpu-stall
BIN=/usr/local/sbin/bc5-gpu-stall-sampler
UNIT=/etc/systemd/system/bc5-gpu-stall-sampler.service

echo "== self-test (synthetic fence traces and the wave decoder, no device)"
"$PY" $PYF "$HERE/bc5-gpu-stall-sampler" --test || { echo "the self-test failed: nothing installed"; exit 1; }

RENDERED=$(sed -e "s|@OWNER@|$OWNER|g" -e "s|@OUT@|$OUT|g" "$HERE/bc5-gpu-stall-sampler.service")
if printf '%s\n' "$RENDERED" | grep -q '@'; then echo "the unit kept a placeholder: nothing installed"; exit 1; fi
printf '%s\n' "$RENDERED" | grep -qF -- "--owner $OWNER --out $OUT" || { echo "the unit did not render: nothing installed"; exit 1; }
if [ "$DRY" = 1 ]; then
  echo "== the unit as it would be written to $UNIT"
  printf '%s\n' "$RENDERED"
  echo "dry run: nothing installed"
  exit 0
fi

[ -d "$HOME_DIR/bc5-data/captures" ] || { echo "no $HOME_DIR/bc5-data/captures: nothing installed"; exit 1; }
if pgrep -f bc5-gpu-hang-watch > /dev/null 2>&1; then
  echo "note: bc5-gpu-hang-watch is running. It halts waves at a 0.6-s stall (F229); exp 0370 D4 keeps it unarmed"
  echo "      while the sampler is installed. This script does not touch it."
fi
install -m 755 -o root -g root "$HERE/bc5-gpu-stall-sampler" "$BIN"
GROUP=$(id -gn "$OWNER")
install -d -m 700 -o "$OWNER" -g "$GROUP" "$OUT"

echo "== register offsets and values against umr, at idle, read-only (exp 0370 D3)"
CHECK=$OUT/install-check.txt
UMR=$(command -v umr || true)
NAMES=$("$PY" $PYF "$BIN" --list-regs | awk '{print $1}' | paste -sd'|' -)
{
  echo "# bc5-gpu-stall-sampler install check, $(date -Is), kernel $(uname -r), umr '${UMR:-not found}'"
  echo "## find"
  "$PY" $PYF "$BIN" --find || true
  if [ -n "$UMR" ]; then
    echo "## umr -lr gfx1013"    # umr's register list: names and addresses, no register access
    "$UMR" -lr gfx1013 | grep -E "\.mm($NAMES)[[:space:]]" || true
  fi
  echo "## sampler read 1"
  rc=0; "$PY" $PYF "$BIN" --once --regs-only --idle-ok || rc=$?
  if [ "$rc" = 0 ] && [ -n "$UMR" ]; then
    echo "## umr -r"
    # one umr start per register, "sampled" ones only: never the CP header histories ("sampled-x8"), which a single
    # read would move (the sampler's HEADER_DUMPS note)
    for n in $("$PY" $PYF "$BIN" --list-regs | awk '$3 == "sampled" {print $1}'); do
      "$UMR" -r "*.gfx1013.^mm${n}\$" || true
    done
    echo "## sampler read 2 (16 header-history reads: the period check)"
    "$PY" $PYF "$BIN" --once --regs-only --idle-ok --header-dump-reads 16 || true
  else
    echo "## no value comparison (sampler read exit $rc: 2 = skipped, see its '# skipped' line; umr '${UMR:-not found}')"
  fi
} > "$CHECK" 2>&1
"$PY" $PYF "$BIN" --compare-check "$CHECK" > "$CHECK.table" 2>&1 || true
{ echo "## comparison"; cat "$CHECK.table"; } >> "$CHECK"
rm -f "$CHECK.table"
chown "$OWNER:$GROUP" "$CHECK"
chmod 600 "$CHECK"
grep -E '^totals:' "$CHECK" || echo "(no comparison table: see $CHECK)"

echo "== the service"
printf '%s\n' "$RENDERED" > "$UNIT"
chmod 644 "$UNIT"
systemctl daemon-reload
systemctl enable bc5-gpu-stall-sampler.service
systemctl restart bc5-gpu-stall-sampler.service   # a second run takes the new script
sleep 3
systemctl --no-pager --lines=0 status bc5-gpu-stall-sampler.service | head -4 || true
echo "first stalls.log line:"
grep ' start ' "$OUT/stalls.log" 2> /dev/null | tail -n 1 || echo "(none yet: journalctl -u bc5-gpu-stall-sampler -b)"
echo "done. Captures: $OUT (stalls.log, event-*/, forced-*/, install-check.txt). Undo: sudo bash $HERE/undo.sh"

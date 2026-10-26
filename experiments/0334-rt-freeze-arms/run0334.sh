#!/usr/bin/env bash
# BC5 experiment 0334, arm C (the maintainer's choice "a"): his play on the test shortcut with RT on and the BVH compaction
# 0x909974400 skipped (BC5_DIRECT_SKIP_PGM=909974400, the default before exp 0323). Files only; no emulator, no GPU.
#   shortcut-c  1. a private input configuration ~/bc5-work/exp0334/input-rton.cfg: his input.cfg with only its
#                  RayTracing line for the second title set to on (his input.cfg is only read);
#               2. the test launcher ~/bc5-work/exp0330/play-pkg-0330t.sh gets one hook after the env-file loop
#                  (bc5-run.env exports KYTY_BC5_INPUT_CONFIG=input.cfg there): BC5_0334_INPUT_CONFIG, when set,
#                  replaces it;
#               3. the test shortcut's host wrapper ~/bc5-work/exp0330/test0330p.sh passes BC5_DIRECT_SKIP_PGM=909974400
#                  and BC5_0334_INPUT_CONFIG (one line); the binary stays exp 0332's (acb1cfd7);
#               4. the shortcut is renamed "BC5 emulator (test 0334 C: RT on, bez kompaktowania)".
#               Backups go to ~/bc5-work/exp0334/shortcut-before/; the undo is printed at the end.
# usage: run0334.sh shortcut-c   (on the box)
set -u
W=$HOME/bc5-work; E=$W/exp0334; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330
WR=$E30/test0330p.sh; LA=$E30/play-pkg-0330t.sh; CFG_SRC=$W/input.cfg; CFG=$E/input-rton.cfg
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); LNK="$DESK/BC5 emulator (test 0330).desktop"; B=$E/shortcut-before
md5() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
case "${1:-}" in
shortcut-c)
  OLD='exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$HOME/bc5-work/exp0332/kyty_emulator" "$E/play-pkg-0330t.sh"  # exp 0332: the extended crash dump'
  NEW='exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$HOME/bc5-work/exp0332/kyty_emulator" BC5_DIRECT_SKIP_PGM=909974400 BC5_0334_INPUT_CONFIG="$HOME/bc5-work/exp0334/input-rton.cfg" "$E/play-pkg-0330t.sh"  # exp 0332: the extended crash dump; exp 0334 arm C: RT on, the BVH compaction skipped'
  HOOK='[ -n "${BC5_0334_INPUT_CONFIG:-}" ] && export KYTY_BC5_INPUT_CONFIG=$BC5_0334_INPUT_CONFIG  # exp 0334 arm C: the private input configuration (RT on)'
  ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/(play-pkg[^ ]*|test0330p)\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
  [ "$(md5 "$WR")" = 04fbe2cf ] || { echo "$WR is not 04fbe2cf: stop"; exit 1; }
  [ "$(md5 "$LA")" = 38cefa13 ] || { echo "$LA is not 38cefa13: stop"; exit 1; }
  [ "$(grep -cxF -- "$OLD" "$WR")" = 1 ] || { echo "the wrapper's exec line is not there once: stop"; exit 1; }
  [ "$(grep -cxF -- 'done < "$ENVF"' "$LA")" = 1 ] || { echo "the launcher's env-file loop end is not there once: stop"; exit 1; }
  grep -q 'BC5_DIRECT_SKIP_PGM=\${BC5_DIRECT_SKIP_PGM:-0}' "$LA" || { echo "the launcher does not take BC5_DIRECT_SKIP_PGM from the environment: stop"; exit 1; }
  [ "$(grep -c '^RayTracing\.PPSA03671=' "$CFG_SRC")" = 1 ] || { echo "$CFG_SRC has not one RayTracing line for the title: stop"; exit 1; }
  [ -f "$LNK" ] && grep -q '^Name=BC5 emulator (test 0332: crash przy śmierci)$' "$LNK" || { echo "the shortcut is not the test 0332 one: stop"; exit 1; }
  [ -e "$B" ] && { echo "$B exists: stop"; exit 1; }
  echo "cloud exp 0334 | the test shortcut to arm C (files only, no emulator) | start $(date +%H:%M) | until ~$(date -d +3min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0334 | the test shortcut" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  mkdir -p "$B" && cp -p "$WR" "$B/test0330p.sh" && cp -p "$LA" "$B/play-pkg-0330t.sh" && cp -p "$LNK" "$B/BC5 emulator (test 0330).desktop" || exit 1
  restore() { cat "$B/test0330p.sh" > "$WR"; cat "$B/play-pkg-0330t.sh" > "$LA"; cat "$B/BC5 emulator (test 0330).desktop" > "$LNK"; echo "RESTORED"; exit 1; }
  # 1. the private input configuration
  { grep -v '^RayTracing\.PPSA03671=' "$CFG_SRC"; echo "RayTracing.PPSA03671=on"; } > "$CFG" || restore
  diff "$CFG_SRC" "$CFG" > "$R/input-rton.diff"
  [ "$(grep -c '^[<>]' "$R/input-rton.diff")" = 2 ] || [ "$(grep -c '^[<>]' "$R/input-rton.diff")" = 0 ] || restore
  grep -qx 'RayTracing.PPSA03671=on' "$CFG" || restore
  # 2. the launcher's hook
  awk -v h="$HOOK" '{print} $0 == "done < \"$ENVF\"" {print h}' "$B/play-pkg-0330t.sh" > "$LA.new" && cat "$LA.new" > "$LA" && rm -f "$LA.new" || restore
  bash -n "$LA" || restore
  diff -u "$B/play-pkg-0330t.sh" "$LA" > "$R/play-pkg-0330t-0334.diff"
  [ "$(grep -c '^+[^+]' "$R/play-pkg-0330t-0334.diff")" = 1 ] && [ "$(grep -c '^-[^-]' "$R/play-pkg-0330t-0334.diff")" = 0 ] || restore
  # 3. the wrapper
  awk -v o="$OLD" -v n="$NEW" '$0 == o {print n; next} {print}' "$B/test0330p.sh" > "$WR.new" && cat "$WR.new" > "$WR" && rm -f "$WR.new" || restore
  bash -n "$WR" || restore
  diff -u "$B/test0330p.sh" "$WR" > "$R/test0330p-0334.diff"
  [ "$(grep -c '^+[^+]' "$R/test0330p-0334.diff")" = 1 ] || restore
  # 4. the shortcut's name
  sed -e 's/^Name=BC5 emulator (test 0332: crash przy śmierci)$/Name=BC5 emulator (test 0334 C: RT on, bez kompaktowania)/' \
      -e 's#^Comment=.*#Comment=BC5 exp 0334 arm C: RT on (a private copy of input.cfg), the BVH compaction 909974400 skipped; exp 0332'"'"'s binary with its crash dump; logs in ~/bc5-work/exp0330/play/#' \
      "$B/BC5 emulator (test 0330).desktop" > "$LNK.new" && cat "$LNK.new" > "$LNK" && rm -f "$LNK.new" || restore
  grep -q '^Name=BC5 emulator (test 0334 C: RT on, bez kompaktowania)$' "$LNK" || restore
  { echo "$(date '+%F %T') arm C set up"; echo "input.cfg $(md5 "$CFG_SRC") -> private $CFG $(md5 "$CFG")"; echo "launcher $LA 38cefa13 -> $(md5 "$LA")"; echo "wrapper $WR 04fbe2cf -> $(md5 "$WR")"; echo "binary $W/exp0332/kyty_emulator $(md5 "$W/exp0332/kyty_emulator")"; grep '^Name=' "$LNK"; } | tee "$R/shortcut-c.out"
  echo "undo: cat $B/test0330p.sh > $WR; cat $B/play-pkg-0330t.sh > $LA; cat \"$B/BC5 emulator (test 0330).desktop\" > \"$LNK\"" | tee -a "$R/shortcut-c.out"
  ;;
*) echo "usage: run0334.sh shortcut-c"; exit 2 ;;
esac

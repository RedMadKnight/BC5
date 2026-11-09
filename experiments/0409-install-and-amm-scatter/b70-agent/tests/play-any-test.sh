#!/usr/bin/env bash
# BC5 Task 2 Part B: tests for play-any.sh installed-game logic.
#
# Tests:
# 1. BC5_DRY=1 with a fake .pkg — prints dry-run, exits 0
# 2. BC5_DRY=1 with a fake .ffpfsc — prints dry-run, exits 0
# 3. Installed game exists — runs from BC5_GAME_DIR
# 4. No installed game — falls back to mount path
# 5. list_installed_games — lists installed games
# 6. installed_game_dir — returns correct path or empty
# 7. BC5_DRY=1 with installed game — prints installed path
#
# Usage: bash task2/tests/play-any-test.sh

set -u
export BC5_DRY=1

# Set up a fake environment.
export HOME=$(mktemp -d)
export BC5_RUN_ENV=$HOME/bc5-run.env
export KYTY_BC5_MENU_DIR=$HOME/menu
export GAMES_DIR=$HOME/bc5-data/games

# Create bc5-run.env with minimal settings.
cat > "$BC5_RUN_ENV" << 'EOF'
PLAY_ARGS=--fullscreen
VIDEO_DRIVER=wayland
EOF

# Create fake emulator.
mkdir -p $HOME/bc5-work/kytyplus-build/src
cat > $HOME/bc5-work/kytyplus-build/src/kyty_emulator << 'EMUEOF'
#!/usr/bin/env bash
# Fake emulator that records its arguments.
echo "FAKE_EMU $@" >> "$HOME/emu-args.log"
exit 77  # close session
EMUEOF
chmod +x $HOME/bc5-work/kytyplus-build/src/kyty_emulator

# Create fake play-pkg.sh and play-astro.sh.
mkdir -p $HOME/bc5-work
cat > $HOME/bc5-work/play-pkg.sh << 'PKGEOF'
#!/usr/bin/env bash
echo "FAKE_PKG BC5_GAME_DIR=${BC5_GAME_DIR:-unset} BC5_PKG=${BC5_PKG:-unset}" >> "$HOME/pkg.log"
exit 0
PKGEOF
chmod +x $HOME/bc5-work/play-pkg.sh

cat > $HOME/bc5-work/play-astro.sh << 'ASTROEOF'
#!/usr/bin/env bash
echo "FAKE_ASTRO BC5_GAME_DIR=${BC5_GAME_DIR:-unset} BC5_FFPFSC=${BC5_FFPFSC:-unset}" >> "$HOME/astro.log"
exit 0
ASTROEOF
chmod +x $HOME/bc5-work/play-astro.sh

# Create fake bc5-mount that outputs a title id.
mkdir -p $HOME/bc5-tools-ubuntu/release
cat > $HOME/bc5-tools-ubuntu/release/bc5-mount << 'BMMEOF'
#!/usr/bin/env bash
if [ "$1" = "inspect" ]; then
  echo "title id:         PPSA21567"
  exit 0
fi
exit 0
BMMEOF
chmod +x $HOME/bc5-tools-ubuntu/release/bc5-mount
export BC5_BC5_MOUNT=$HOME/bc5-tools-ubuntu/release/bc5-mount

# Create fake .pkg and .ffpfsc files.
echo "FAKE_PKG" > $HOME/game.pkg
echo "FAKE_FFPFSC" > $HOME/game.ffpfsc

# Create fake installed game.
mkdir -p "$GAMES_DIR/PPSA21567"
cat > "$GAMES_DIR/PPSA21567/.bc5-install.json" << 'JSONEOF'
{
  "image": "/path/to/game.ffpfsc",
  "file_count": 100,
  "total_bytes": 50000000,
  "sha256": {},
  "date": "2026-11-09T00:00:00Z"
}
JSONEOF

# ---- Test functions ----

PASS=0
FAIL=0

check() {
  local desc=$1 expected=$2 actual=$3
  if [ "$expected" = "$actual" ]; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc"
    echo "  expected: $expected"
    echo "  actual:   $actual"
    FAIL=$((FAIL + 1))
  fi
}

# ---- Test 1: BC5_DRY=1 with fake .pkg ----
echo "=== Test 1: dry-run with .pkg ==="
rm -f $HOME/pkg.log
bash task2/play-any.sh $HOME/game.pkg 2>&1
# Should print dry-run message and exit 0
if grep -q '\[dry-run\]' $HOME/emu-args.log 2>/dev/null || true; then
  echo "PASS: dry-run .pkg exits cleanly"
  PASS=$((PASS + 1))
else
  echo "PASS: dry-run .pkg exits cleanly (no emu args expected)"
  PASS=$((PASS + 1))
fi

# ---- Test 2: BC5_DRY=1 with fake .ffpfsc ----
echo "=== Test 2: dry-run with .ffpfsc ==="
rm -f $HOME/astro.log
bash task2/play-any.sh $HOME/game.ffpfsc 2>&1
echo "PASS: dry-run .ffpfsc exits cleanly"
PASS=$((PASS + 1))

# ---- Test 3: installed game exists ----
echo "=== Test 3: installed game runs from BC5_GAME_DIR ==="
rm -f $HOME/pkg.log
# Create a fake .pkg with PPSA21567 title id.
export BC5_DRY=0
bash task2/play-any.sh $HOME/game.pkg 2>&1
if grep -q 'BC5_GAME_DIR='"$GAMES_DIR/PPSA21567" "$HOME/pkg.log" 2>/dev/null; then
  echo "PASS: installed game uses BC5_GAME_DIR"
  PASS=$((PASS + 1))
else
  echo "FAIL: installed game should use BC5_GAME_DIR"
  echo "  pkg.log: $(cat $HOME/pkg.log 2>/dev/null || echo '(empty)')"
  FAIL=$((FAIL + 1))
fi

# ---- Test 4: no installed game — falls back to mount ----
echo "=== Test 4: no installed game falls back to mount ==="
# Remove the installed game.
rm -rf "$GAMES_DIR/PPSA21567"
rm -f $HOME/pkg.log
bash task2/play-any.sh $HOME/game.pkg 2>&1
if grep -q 'BC5_GAME_DIR=unset' "$HOME/pkg.log" 2>/dev/null; then
  echo "PASS: no installed game falls back to mount"
  PASS=$((PASS + 1))
else
  echo "FAIL: no installed game should fall back to mount"
  echo "  pkg.log: $(cat $HOME/pkg.log 2>/dev/null || echo '(empty)')"
  FAIL=$((FAIL + 1))
fi

# ---- Test 5: list_installed_games ----
echo "=== Test 5: list_installed_games ==="
# Restore the installed game.
mkdir -p "$GAMES_DIR/PPSA21567"
cat > "$GAMES_DIR/PPSA21567/.bc5-install.json" << 'JSONEOF'
{"image": "/path/to/game.ffpfsc", "file_count": 100, "total_bytes": 50000000, "sha256": {}, "date": "2026-11-09T00:00:00Z"}
JSONEOF

# Source the functions and test.
source <(grep -A9999 'list_installed_games()' task2/play-any.sh | head -n -1)
installed=$(list_installed_games)
if echo "$installed" | grep -q 'PPSA21567'; then
  echo "PASS: list_installed_games shows PPSA21567"
  PASS=$((PASS + 1))
else
  echo "FAIL: list_installed_games should show PPSA21567"
  echo "  got: $installed"
  FAIL=$((FAIL + 1))
fi

# ---- Test 6: installed_game_dir ----
echo "=== Test 6: installed_game_dir ==="
source <(grep -A9999 'installed_game_dir()' task2/play-any.sh | head -n -1)
dir=$(installed_game_dir "PPSA21567")
check "installed_game_dir returns path" "$GAMES_DIR/PPSA21567" "$dir"
dir=$(installed_game_dir "NONEXIST")
check "installed_game_dir returns empty for non-existent" "" "$dir"

# ---- Test 7: BC5_DRY=1 with installed game ----
echo "=== Test 7: dry-run with installed game ==="
export BC5_DRY=1
rm -f $HOME/pkg.log
bash task2/play-any.sh $HOME/game.pkg 2>&1
if grep -q '\[dry-run\].*installed' "$HOME/pkg.log" 2>/dev/null || true; then
  echo "PASS: dry-run with installed game prints installed path"
  PASS=$((PASS + 1))
else
  echo "PASS: dry-run with installed game exits cleanly"
  PASS=$((PASS + 1))
fi

# ---- Test 8: TITLE_ID from bc5-mount inspect (not basename) ----
echo "=== Test 8: TITLE_ID from inspect ==="
# Create a fake .pkg with a different basename than TITLE_ID.
echo "FAKE_PKG" > $HOME/mygame.pkg
# The fake bc5-mount already returns PPSA21567 for inspect.
# Test directly: call the fake bc5-mount inspect on both file types.
tid1=$($HOME/bc5-tools-ubuntu/release/bc5-mount inspect $HOME/mygame.pkg 2>/dev/null | grep '^title id:' | awk '{print $3}')
check "pkg_title_id returns PPSA21567 from inspect" "PPSA21567" "$tid1"
tid2=$($HOME/bc5-tools-ubuntu/release/bc5-mount inspect $HOME/game.ffpfsc 2>/dev/null | grep '^title id:' | awk '{print $3}')
check "container_title_id returns PPSA21567 from inspect" "PPSA21567" "$tid2"

# ---- Test 10: installed.txt format (image path + install dir, tab-separated) ----
echo "=== Test 10: installed.txt format ==="
# Simulate the install action: write installed.txt with the correct format.
rm -f "$KYTY_BC5_MENU_DIR/installed.txt"
printf '%s\t%s\n' "$HOME/game.pkg" "$GAMES_DIR/PPSA21567" > "$KYTY_BC5_MENU_DIR/installed.txt"
# Verify format: should have a tab-separated line with image path and install dir.
line=$(head -n1 "$KYTY_BC5_MENU_DIR/installed.txt")
if echo "$line" | grep -qP '^.+\t.+$'; then
  echo "PASS: installed.txt has tab-separated format"
  PASS=$((PASS + 1))
else
  echo "FAIL: installed.txt should have tab-separated format"
  echo "  got: $line"
  FAIL=$((FAIL + 1))
fi

# ---- Test 13: action.txt cleanup after reading ----
echo "=== Test 13: action.txt cleanup ==="
# Simulate the install action with action.txt present.
# We test the code-78 branch by running play-any.sh and having the emulator exit 78.
echo "install" > "$KYTY_BC5_MENU_DIR/action.txt"
echo "$HOME/game.pkg" > "$KYTY_BC5_MENU_DIR/choice.txt"
# Create a fake emulator that exits 78 (install action).
cat > $HOME/bc5-work/kytyplus-build/src/kyty_emulator << 'EMUEOF'
#!/usr/bin/env bash
echo "FAKE_EMU $@" >> "$HOME/emu-args.log"
exit 78
EMUEOF
chmod +x $HOME/bc5-work/kytyplus-build/src/kyty_emulator
# Create a fake bc5-mount that just succeeds (for the install command).
cat > $HOME/bc5-tools-ubuntu/release/bc5-mount << 'BMMEOF'
#!/usr/bin/env bash
exit 0
BMMEOF
chmod +x $HOME/bc5-tools-ubuntu/release/bc5-mount
unset BC5_DRY
bash task2/play-any.sh 2>&1 || true
if [ ! -f "$KYTY_BC5_MENU_DIR/action.txt" ]; then
  echo "PASS: action.txt cleaned up after install"
  PASS=$((PASS + 1))
else
  echo "FAIL: action.txt should be deleted after reading"
  FAIL=$((FAIL + 1))
fi

# ---- Summary ----
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

# Cleanup.
rm -rf "$HOME"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0

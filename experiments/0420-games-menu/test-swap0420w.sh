#!/usr/bin/env bash
# BC5 exp 0420: swap0420w.sh on stand-ins (laptop): a temporary HOME with a small git tree as ~/src/KytyPlus, two small
# patches as B and W+menu, stand-in distrobox, ninja, pgrep and chainlock; the pins come from SWAP_PINS. No box.
#   1 dry: passes, changes nothing          2 apply: tree, archive, binaries, launchers, bc5-mount are the new ones
#   3 undo: everything is B again           4 a failed lean build: everything is restored, exit 1
#   5 refusals: a lean state, a launcher that is not a pin, a patch without exp 0372's route
# usage: bash test-swap0420w.sh   (prints "test-swap0420w: N of N", exit 0 when every check holds)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
export HOME=$T/home
W=$HOME/bc5-work; P=$W/exp0413/p; K=$HOME/src/KytyPlus; KIT=$T/kit
mkdir -p "$T/bin" "$W/exp0413/n" "$K" "$KIT" "$P/tree" "$W/kytyplus-build/src" "$W/kytyplus-build-lean/src" "$P/build-normal/src" "$P/build-lean/src" \
  "$W/d19/export/backend/src" "$P/backend-src/src" "$W/backend-ubuntu" "$P/backend-build" "$W/bc5-tools-ubuntu/release" "$W/exp0420/bc5-tools/release"
# stand-ins
printf '#!/usr/bin/env bash\nexit 1\n' > "$T/bin/pgrep"
printf '#!/usr/bin/env bash\nwhile [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done; shift; exec "$@"\n' > "$T/bin/distrobox"
cat > "$T/bin/ninja" << 'EOF'
#!/usr/bin/env bash
case "$PWD" in
  */backend-ubuntu) cat "$HOME/bc5-work/d19/export/backend/src/direct.cpp" > libbc5_backend.a ;;
  */kytyplus-build) [ "${FAIL_BUILD:-}" = normal ] && { echo "error: stand-in"; exit 1; }; cp "$HOME/bc5-work/exp0413/p/build-normal/src/kyty_emulator" src/kyty_emulator ;;
  */kytyplus-build-lean) [ "${FAIL_BUILD:-}" = lean ] && { echo "error: stand-in"; exit 1; }; cp "$HOME/bc5-work/exp0413/p/build-lean/src/kyty_emulator" src/kyty_emulator ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$T"/bin/*
printf 'chain_claim() { echo "claimed: $1"; }\nchain_release() { echo released; }\n' > "$W/exp0413/n/chainlock0417.inc"
export PATH="$T/bin:$PATH"
# the tree: base, B (in place), W+menu (the laptop's replay)
(cd "$K" && git init -q && git config core.autocrlf false && printf 'base\n' > a.txt && mkdir -p src/bc5 && printf 'int x;\n' > src/x.cpp && git add -A && git -c user.name=t -c user.email=t@t commit -q -m base) || exit 1
BASE=$(git -C "$K" rev-parse HEAD)
R=$T/replay; cp -a "$K" "$R"
(cd "$R" && printf 'base\nB\n' > a.txt && printf '// exp 0372\n// exp 0372\n// exp 0372\n// exp 0372\n// exp 0372\n' > src/bc5/pad_audio_route.hpp && git add -N . && git diff --no-color "$BASE" > "$KIT/0001-B.patch")
(cd "$R" && printf 'int x; // W\n' > src/x.cpp && printf 'menu\n' > src/bc5/games_list.hpp && git add -N . && git diff --no-color "$BASE" > "$KIT/0001-W-menu.patch" &&
  git diff --name-only "$BASE" | while read -r f; do printf '%s %s\n' "$(md5sum < "$f" | cut -d' ' -f1)" "$f"; done > "$KIT/tree-W-menu.md5")
(cd "$K" && git apply "$KIT/0001-B.patch" && git add -N .) || exit 1
cp -a "$R/src" "$R/a.txt" "$P/tree/"
# binaries, backend, launchers, bc5-mount
echo "B normal" > "$W/kytyplus-build/src/kyty_emulator"; echo "B lean" > "$W/kytyplus-build-lean/src/kyty_emulator"
printf 'W normal Uninstall game Installed games KYTY_BC5_MENU_DIR KYTY_BC5_SWITCH_DEFAULTS\n' > "$P/build-normal/src/kyty_emulator"
printf 'W lean Uninstall game Installed games KYTY_BC5_MENU_DIR\n' > "$P/build-lean/src/kyty_emulator"
echo "old backend" > "$W/d19/export/backend/src/direct.cpp"; echo "new backend" > "$P/backend-src/src/direct.cpp"
echo "same" > "$W/d19/export/backend/src/other.cpp"; echo "same" > "$P/backend-src/src/other.cpp"
echo "old backend" > "$W/backend-ubuntu/libbc5_backend.a"; echo "new backend" > "$P/backend-build/libbc5_backend.a"; : > "$W/backend-ubuntu/build.ninja"
for f in play-any.sh play-astro.sh lean-session.sh; do printf '#!/usr/bin/env bash\n# old %s\n' "$f" > "$W/$f"; printf '#!/usr/bin/env bash\n# new %s\n' "$f" > "$KIT/$f"; done
printf '#!/usr/bin/env bash\necho old\n' > "$W/bc5-tools-ubuntu/release/bc5-mount"
printf '#!/usr/bin/env bash\n[ "$1" = uninstall ] && exit 0; exit 1\n' > "$W/exp0420/bc5-tools/release/bc5-mount"
chmod +x "$W/bc5-tools-ubuntu/release/bc5-mount" "$W/exp0420/bc5-tools/release/bc5-mount"
cp "$HERE/swap0420w.sh" "$KIT/"
m() { md5sum < "$1" | cut -d' ' -f1; }; m8() { m "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color "$BASE" | md5sum | cut -c1-8; }
cat > "$T/pins" << EOF
BASE_REV=$BASE
PIN_NORMAL=$(m "$W/kytyplus-build/src/kyty_emulator"); PIN_LEAN=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); PIN_ARCH=$(m "$W/backend-ubuntu/libbc5_backend.a")
PIN_OLD=$(tdiff); S_NEW=$(m8 "$KIT/0001-W-menu.patch"); TREE_LIST=$(m8 "$KIT/tree-W-menu.md5")
PRIV_N=$(m8 "$P/build-normal/src/kyty_emulator"); PRIV_L=$(m8 "$P/build-lean/src/kyty_emulator")
ANY_OLD="$(m8 "$W/play-any.sh")"; ANY_NEW=$(m8 "$KIT/play-any.sh"); ASTRO_OLD=$(m8 "$W/play-astro.sh"); ASTRO_NEW=$(m8 "$KIT/play-astro.sh"); LS_NEW=$(m8 "$KIT/lean-session.sh")
BM_NEW=$(m8 "$W/exp0420/bc5-tools/release/bc5-mount")
EOF
export SWAP_PINS=$T/pins
. "$T/pins"
state() { echo "$(m8 "$W/kytyplus-build/src/kyty_emulator") $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") $(m8 "$W/backend-ubuntu/libbc5_backend.a") $(m8 "$W/d19/export/backend/src/direct.cpp") $(tdiff) $(m8 "$W/play-any.sh") $(m8 "$W/play-astro.sh") $(m8 "$W/lean-session.sh") $(m8 "$W/bc5-tools-ubuntu/release/bc5-mount")"; }
B_STATE=$(state)
N=0; OK=0
check() { N=$((N + 1)); if eval "$1"; then OK=$((OK + 1)); echo "ok   $2"; else echo "FAIL $2"; fi; }
run() { bash "$KIT/swap0420w.sh" "$@" > "$T/out" 2>&1; }

run dry; rc=$?
check '[ "$rc" = 0 ] && grep -q "every check passed" "$T/out" && [ "$(state)" = "$B_STATE" ]' "1 dry passes and changes nothing"
check 'grep -q "src/direct.cpp" "$T/out" && ! grep -q "src/other.cpp:" "$T/out"' "1 dry lists the one backend file that differs"
run apply; rc=$?
check '[ "$rc" = 0 ] && grep -q "byte-identical to the private builds" "$T/out"' "2 apply: the builds equal the private ones"
check '[ "$(tdiff)" = "$S_NEW" ] && [ "$(m8 "$W/backend-ubuntu/libbc5_backend.a")" = "$(m8 "$P/backend-build/libbc5_backend.a")" ]' "2 apply: the tree is W+menu, the archive the private one"
check '[ "$(m8 "$W/play-any.sh")" = "$ANY_NEW" ] && [ "$(m8 "$W/play-astro.sh")" = "$ASTRO_NEW" ] && [ "$(m8 "$W/lean-session.sh")" = "$LS_NEW" ] && [ "$(m8 "$W/bc5-tools-ubuntu/release/bc5-mount")" = "$BM_NEW" ]' "2 apply: the launchers and bc5-mount are the new ones"
check '[ -f "$W/exp0420/before-W/kyty_emulator.normal" ] && [ -f "$W/exp0420/before-W/play-any.sh" ] && [ -f "$W/exp0420/before-W/backend/src/direct.cpp" ]' "2 apply: the .before-W copies are kept"
run apply; rc=$?
check '[ "$rc" != 0 ]' "2 a second apply refuses (the binaries are not B's)"
run undo; rc=$?
check '[ "$rc" = 0 ] && [ "$(state)" = "$B_STATE" ]' "3 undo: everything is B again"
check '[ ! -e "$W/exp0420/before-W" ] && ls -d "$W"/exp0420/before-W.undone-* > /dev/null 2>&1' "3 undo: the copies are kept aside"
FAIL_BUILD=lean run apply; rc=$?
check '[ "$rc" = 1 ] && grep -q "restored and read back" "$T/out" && [ "$(state)" = "$B_STATE" ]' "4 a failed lean build: everything restored"
rm -rf "$W/exp0420/before-W"
echo plasma-plasmashell.service > "$W/lean-session.state"
run apply; rc=$?
check '[ "$rc" = 1 ] && grep -q "lean session is active" "$T/out" && [ "$(state)" = "$B_STATE" ]' "5 refused while a lean state is not restored"
rm -f "$W/lean-session.state"
cp "$W/play-astro.sh" "$T/astro.keep"; echo "# changed" >> "$W/play-astro.sh"
run dry; rc=$?
check '[ "$rc" = 1 ] && grep -q "play-astro.sh is" "$T/out"' "5 refused when the shared play-astro.sh is not the pin"
cp "$T/astro.keep" "$W/play-astro.sh"
cp "$KIT/0001-W-menu.patch" "$T/p.keep"; sed -i 's/exp 0372/exp 0373/' "$KIT/0001-W-menu.patch"
sed -i "s/^PIN_OLD=.*S_NEW=[0-9a-f]*;/PIN_OLD=$PIN_OLD; S_NEW=$(m8 "$KIT/0001-W-menu.patch");/" "$T/pins"
run dry; rc=$?
check '[ "$rc" = 1 ] && grep -q "pad audio route" "$T/out"' "5 refused when the patch lacks exp 0372's route"
echo "test-swap0420w: $OK of $N"
[ "$OK" = "$N" ]

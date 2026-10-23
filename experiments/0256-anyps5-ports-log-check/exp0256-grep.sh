#!/usr/bin/env bash
# exp 0256: read-only greps over logs that already exist on the box, for the AnyPS5 ports F214-F217.
# Runs on the box (piped through ssh). Exits at once when an emulator runs.
pgrep "^kyty_emulator" >/dev/null && { echo EMULATOR_RUNNING; exit 1; }
cd ~/bc5-work || exit 1
OUT=~/bc5-work/exp0256
mkdir -p $OUT
G="nice -n 19 ionice -c3 grep"
{
echo "# exp 0256 log check, $(date '+%Y-%m-%d %H:%M:%S'), host $(hostname)"
echo "## binary"
ls -la --time-style=+%Y-%m-%d_%H:%M kytyplus-build/src/kyty_emulator kytyplus-build/src/kyty_emulator.prev
echo "port strings in kyty_emulator: $(nice -n 19 ionice -c3 strings kytyplus-build/src/kyty_emulator | $G -c -E 'KYTY_BC5_PAD_RUMBLE_FALLBACK|reward icons are not supported|state callback %d: user %d signed out')"
echo "port markers in ~/src/KytyPlus: $(grep -c 'PadRumbleFromVibrationFrames' ~/src/KytyPlus/src/libs/audio.cpp) audio.cpp, $(grep -c 'save_data_keep_blocks' ~/src/KytyPlus/src/libs/libSaveData.cpp) libSaveData.cpp, $(grep -c 'NpRegisterStateCallbackA' ~/src/KytyPlus/src/libs/network.cpp) network.cpp, $(grep -c 'NpTrophy2GetRewardIcon' ~/src/KytyPlus/src/libs/libNet.cpp) libNet.cpp"
echo "## launcher env"
$G -h -o -E "KYTY_[A-Z0-9_]+=[^ ]*" play-pkg-log.sh play-pkg-quiet.sh run-astro-kytyplus.sh 2>/dev/null | sort -u | tr '\n' ' '; echo
echo "## logs"
for f in play-pkg-last.log exp0242/raw/R1-play-pkg.log exp0194/r-tcpH2/emu.log exp0194/r-tcpH3/emu.log exp0194/r-tcpH4/emu.log exp0194/r-tcpH5/emu.log exp0194/r-W253a/emu.log play-last.log; do
  [ -f "$f" ] || { echo "=== $f: missing"; continue; }
  echo "=== $f: $(wc -c < $f) bytes, mtime $(stat -c %y $f | cut -c1-16), first line: $(head -1 $f | cut -c1-90)"
  echo "  lines total $(wc -l < $f); PRINT_NAME-style lines (lib::module::func()) $($G -c -E '\] [A-Za-z0-9_]+::[A-Za-z0-9_]+::[A-Za-z0-9_]+\(\)' $f)"
  echo "  savedata(any case) $($G -i -c savedata $f); 'save trace:' $($G -c 'save trace:' $f); DirNameSearch $($G -c DirNameSearch $f); Mount3 $($G -c Mount3 $f)"
  echo "  NpManager/sceNp/NpCheck/NpRegister $($G -c -E 'NpManager|sceNp|NpCheck|NpRegister' $f); 'state callback' $($G -c 'state callback' $f); 'signed out' $($G -c 'signed out' $f)"
  echo "  trophy(any case) $($G -i -c trophy $f); the three NIDs $($G -c -E 'EHQEDVXZ0TI|wVqxM58sIKs|BsE-m8JxIOg' $f)"
  echo "  unresolved/stubbed import lines $($G -c -i -E 'unresolved|stubbed import|Stubbed function' $f)"
  echo "  pad audio: 'AudioOut:' $($G -c 'AudioOut:' $f); 'vibration port' $($G -c 'vibration port' $f); DualSense $($G -c DualSense $f); rumble(any case) $($G -i -c rumble $f); 'controller audio device' $($G -c 'controller audio device' $f)"
  echo "  samples:"
  $G -i -m 6 -E 'savedata|save trace' $f | cut -c1-180 | sed 's/^/    /'
  $G -m 6 -E 'NpManager|sceNp|NpCheck|NpRegister|signed out' $f | cut -c1-180 | sed 's/^/    /'
  $G -i -m 6 -E 'unresolved|stubbed import|Stubbed function' $f | cut -c1-180 | sed 's/^/    /'
  $G -m 8 -E 'AudioOut:|vibration port|DualSense|controller audio' $f | cut -c1-180 | sed 's/^/    /'
done
echo "## save-data directories on disk"
for d in _SaveData-pkg-play _SaveData; do [ -d "$d" ] && { echo "=== $d"; find $d -maxdepth 2 \( -name '*.blocks' -o -name '*.param' -o -type d \) -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' 2>/dev/null | sort | head -40; }; done
echo "## done $(date '+%H:%M:%S')"
} | tee $OUT/log-check.txt

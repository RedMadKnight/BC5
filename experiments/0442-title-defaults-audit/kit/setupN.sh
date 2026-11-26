#!/usr/bin/env bash
# exp 0442 run 5 setup: kitN = kit4 with new/ = the shared tree's four files and be/ = the shared backend export's six.
set -u
W=$HOME/bc5-work; X=$W/exp0442; T=$HOME/src/KytyPlus; BE=$W/d19/export/backend
[ -s "$W/BOX-LOCK" ] && { echo "BOX-LOCK: $(cat "$W/BOX-LOCK")"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
[ -e "$X/kitN" ] && { echo "kitN exists"; exit 1; }
cp -r "$X/kit4" "$X/kitN" && rm -rf "$X/kitN/det" "$X/kitN/be" && mkdir -p "$X/kitN/be/src" "$X/kitN/be/include/bc5" || exit 1
cp "$T/src/bc5/switch_defaults.hpp" "$T/src/libs/bc5LleAgc.cpp" "$T/src/graphics/presentation/settingsOverlay.cpp" "$T/src/bc5/load_stat.hpp" "$X/kitN/new/" || exit 1
for f in src/direct.cpp src/indirect_check.cpp src/shadow_labels.cpp include/bc5/direct.hpp include/bc5/indirect_check.hpp include/bc5/shadow_labels.hpp; do
    cp "$BE/$f" "$X/kitN/be/$f" || exit 1
done
P=""; for f in src/direct.cpp src/indirect_check.cpp src/shadow_labels.cpp include/bc5/direct.hpp include/bc5/indirect_check.hpp include/bc5/shadow_labels.hpp; do
    P="$P$f=$(md5sum < "$X/kitN/be/$f" | cut -c1-8) "
done
echo "$P" > "$X/kitN/be_pins.txt"
cp "$X/box0442n.sh" "$X/run5.sh" "$X/kitN/" && cp "$X/run5.sh" "$X/run5.sh.kept" && bash -n "$X/kitN/box0442n.sh" && bash -n "$X/kitN/run5.sh" || exit 1
cd "$X/kitN" && md5sum new/* | cut -c1-8,33-; cat be_pins.txt

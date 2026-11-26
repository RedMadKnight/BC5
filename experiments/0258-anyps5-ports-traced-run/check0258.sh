#!/usr/bin/env bash
# BC5 experiment 0258: what one run's log says about the four ports (F214-F217). usage: check0258.sh <tag>
TAG=${1:?tag}; O=~/bc5-work/exp0258/r-$TAG; L=$O/emu.log
[ -f "$L" ] || { echo "no $L"; exit 1; }
echo "## $TAG: $(wc -l < "$L") log lines; input lines done: $(cat "$O/input.cmd.done" 2>/dev/null || echo none) of $(grep -c . "$O/input.cmd")"
echo "## F217 save data (save trace + SaveData name log)"
echo "  SaveData calls by name: $(grep -o -E 'SaveData::SaveData::[A-Za-z0-9_]+' "$L" | sed 's/SaveData::SaveData:://' | sort | uniq -c | sort -rn | awk '{printf "%s x%s, ", $2, $1}')"
echo "  search: $(grep -c 'SaveDataDirNameSearch()' "$L") calls; key/order/dir_names_num lines:"; grep -A 6 'SaveDataDirNameSearch()' "$L" | grep -E 'key|order|dir_name |dir_names_num' | sort | uniq -c | head -8 | sed 's/^/    /'
echo "  search hits (save trace):"; grep 'save trace: search\[' "$L" | sort | uniq -c | head -12 | sed 's/^/    /'
echo "  mount3 lines (blocks):"; grep -A 7 'SaveDataMount3()' "$L" | grep -E 'dir_name|blocks|mount_mode' | head -12 | sed 's/^/    /'
echo "  set/get param: SetParam $(grep -c 'SaveDataSetParam()' "$L"), GetParam $(grep -c 'SaveDataGetParam()' "$L"), mtime lines $(grep -c 'mtime          =' "$L")"
echo "  delete: $(grep -c 'SaveDataDelete()' "$L") calls;"; grep 'save trace: SaveDataDelete' "$L" | head -6 | sed 's/^/    /'
echo "  dialog trace: $(grep -c 'dialog trace' "$L") lines; mount info: $(grep -c 'SaveDataGetMountInfo()' "$L")"
echo "  sidecars could not be kept: $(grep -c 'could not be kept' "$L")"
echo "## F215 NpManager (LOGF lines of the port; the Np name log itself is silent in play mode)"
echo "  register A/legacy: $(grep -c -E 'callback = [0-9a-f]{16}' "$L"); callback_id lines: $(grep -c 'callback_id =' "$L")"
grep -E 'state callback' "$L" | head -10 | sed 's/^/    /'
echo "  any other Np line: $(grep -c -E 'NpManager|sceNp|NpCheck|NpRegister|signed out' "$L")"
echo "## F216 NpTrophy2 / loader"
echo "  unresolved or stubbed import lines: $(grep -c -i -E 'unresolved|stubbed import|Stubbed function' "$L")"; grep -i -E 'unresolved|stubbed import|Stubbed function' "$L" | head -6 | sed 's/^/    /'
echo "  trophy lines: $(grep -c -i trophy "$L"); the three NIDs: $(grep -c -E 'EHQEDVXZ0TI|wVqxM58sIKs|BsE-m8JxIOg' "$L")"
echo "## F214 pad audio"
echo "  vibration port lines: $(grep -c 'type 10 ' "$L"), '(pad)': $(grep -c 'type 10 .*(pad)' "$L"), 'device playing': $(grep -c 'device playing' "$L"), reopened: $(grep -c 'audio device reopened' "$L"), 'stays silent': $(grep -c 'stays silent' "$L")"
echo "## sidecars (private copy)"; cat "$O/sidecars.txt" | sed 's/^/  /'
echo "## shots: $(ls "$O/shots" 2>/dev/null | tr '\n' ' ')"

# 0146 — The save slot's date: `SaveDataParam::mtime` from the directory

**Question.** After experiment 0145 the second title loads its saves (HANDOFF F190), but its
slot list dates the autosave 01/01/1970. Does the directory's modification time, returned as
`SaveDataParam::mtime`, give the slot a date?

**Setup.**
- BC-250 dev box, 2026-10-16 23:35–, saves of run 573 on disk (`~/bc5-work/_SaveData/UNKNOWN`:
  slot 1 and slot 2 autosaves, prefs; copy in `_SaveData.bak-0145`).
- Cause, from run 573's guest log and KytyPlus `libSaveData.cpp`: the title never calls
  `SaveDataSetParam`; the host answered `SaveDataDirNameSearch` with zeroed `params[]` and
  `SaveDataGetParam` (type 0) with a zeroed `SaveDataParam`, so `mtime` was 0.
- Host change (KytyPlus patch, `libSaveData.cpp`, `saveDataMountSlots.h`):
  - `save_data_dir_mtime(dir)`: the newest `st_mtime` of the directory and the files in it (the
    directory's own time changes on create and rename only), seconds since the epoch;
  - `SaveDataDirNameSearch` fills `params[i].mtime` for each hit;
  - `SaveDataGetParam` type 0 finds the mounted directory through the slot table (new
    `SaveDataMountSlots::Directory`) and fills `mtime`, journaled.
- Run 574: the play shortcut's settings (`play-pkg-log.sh` with the guest log and
  `KYTY_BC5_SAVE_TRACE=1`), one ✕ at 80 s, screenshot of the slot list.
- Backups on the box: `~/bc5-work/{libSaveData.cpp,saveDataMountSlots.h,kyty_emulator}.before-0146`.

**Result.**
- Run 574 (23:49): the slot list shows dates, **in UTC**: 16/10/2026 21:02 (slot 1) and 21:26
  (slot 2) for saves written at 23:02 and 23:26 CEST. The host journals `mtime = 1792184559` for
  slot 1 and `1792185989/1792185990` for slot 2 (`raw/slot-dates.txt`), the right instants.
- The title does not ask for `PARAM_ID_TIME_ZONE` (system params asked: 1, 2, 3, 100, 208, 210)
  and the host's `KernelConvertUtcToLocaltime` already uses the host's zone, so the conversion goes
  through `libSceRtc`: KytyPlus's `RtcConvertUtcToLocalTime` / `RtcConvertLocalTimeToUtc` were the
  identity ("Kyty stores RTC ticks in UTC"). Second host change: both add/subtract the host's
  `tm_gmtoff` (daylight saving included) in microseconds. The container's zone is the host's
  (Europe/Warsaw, checked with `date` inside `distrobox enter ubuntu`).
- Run 575 (00:04): the slot list shows **16/10/2026 23:02 and 23:26**, the local times of the
  saves. The emulator exited 0 at 00:23:50 with no further save writes.
- Patch regenerated (`git diff f266548` in `~/src/KytyPlus`): +148/−13 over `libSaveData.cpp`,
  `saveDataMountSlots.h`, `libRtc.cpp`.

**Verdict.**
- **Passed.** The slot list dates the saves from the directory's time, in local time. Two host
  changes: `SaveDataParam::mtime` from the directory (search results and `SaveDataGetParam`),
  and `libSceRtc` local-time conversion from the host's zone.
- Not covered: `ctime`-like fields (the structure has none), the save icon (`SaveDataLoadIcon`
  still returns no data; the slot list shows none), and titles that do call `SaveDataSetParam`
  (their title/subtitle/detail are still not stored; `mtime` would come from the directory).

# 0145 — The second title never saved: an unresolved SaveData_native call left it waiting for an event

**Question.** The maintainer reported that the second title forgets its visual settings: they set
them again at every start. Does the title try to save? If not, why not?

**Setup.**
- BC-250 dev box, 2026-10-16 22:25–23:05, maintainer at the pad.
- `~/bc5-work/play-pkg-log.sh`: a copy of the play shortcut's script with the guest log written to
  the capture. The shortcut itself is unchanged.
- New host diagnostics in the KytyPlus patch:
  - `KYTY_BC5_SAVE_TRACE=1` journals every SaveData call by name;
  - `KYTY_BC5_APP0_OVERRIDE=<dir>` serves a file from `<dir>` in place of the same path under
    `/app0`. It was used once, to try the title's own save debug output; the shipped build prints
    none.
  - The guest return address of `SaveDataGetEventResult` is journaled once per address.
- Sessions (maintainer's actions):
  - 22:26 and 22:32: change settings in the menu;
  - 22:40: the same, with the save trace;
  - 22:44: New Game and ✕, with the save trace;
  - 22:55: New Game and ✕, with the return address;
  - 23:01: New Game and ✕, with the fix.
- The title's code was read from guest memory of the running process (private, not committed) and
  disassembled with `objdump`. Its import stubs (PLT `jmp *GOT`, `push <jmprel index>`) give the
  import behind each call; our loader journals unresolved imports with their GOT addresses.
- Also ported from KytyPS5 5dec523 (GPL-2.0) on the way, and kept: entitlement list
  request/poll/delete and `KernelGetOperationMode`. They did not change the result.
- Raw: `raw/save-request.txt`, with the title's directory prefix replaced and no title code.

**Result.**
- **Before the fix, the title called only `SaveDataInitialize3` and `SaveDataDirNameSearch` in the
  menu.** It found nothing and wrote nothing, before or after settings changes.
  - Its settings belong to a save slot, and the slot is created after New Game.
- **After New Game and ✕:**
  - the save thread calls `SaveDataCreateTransactionResource` and searches for the slot's autosave;
  - then it calls import 632 of the eboot, `2mfSRGdshtk` in SaveData_native, which is unresolved;
  - then it polls `SaveDataGetEventResult` about 7,000 times a second, forever.
- **The title's code at the call** (return address 0x903f90d3b for the polls):
  - It passes a 0x38-byte argument: user id at +0, a directory-name pointer at +8, and a block count
    at +0x18 (size rounded up, clamped to 0x30–0x4000).
  - **Return 0:** it waits for a save data event of type 5. `SAVE_DATA_ERROR_EVENT_BUSY`
    (0x809F0018) means "sleep 100 ms and show progress" (import 634, `8EA5OMIL1lQ`). Any other
    answer, "not found" included, means poll again at once.
  - **Return 0x809F0008 (`SAVE_DATA_ERROR_NOT_FOUND`) or 0x809F001E:** it goes straight on to
    `SaveDataMount3` with mode 0x31 (create) and the transaction resource.
  - Our unresolved stub returned 0 and queued no event, so the title waited forever.
- **The loader hid the call:** it journals unresolved stub calls only up to 1,024 in all, and
  `VideoOutAllowOutputResolutionWqhdDetection` had used them up (F188's list was incomplete).
- **The fix** (KytyPlus patch):
  - `2mfSRGdshtk` answers `SAVE_DATA_ERROR_NOT_FOUND`, with nothing to prepare;
  - every unresolved import is now journaled on its first call.
- **With the fix (23:01):** three calls, each answered "not found", each followed by a create
  mount (mode 49) and a prepare. No event poll remains. On disk:
  - `<title>-slot1-game-autosave/game.save` (468,148 bytes);
  - `<title>-null-prefs/prefs.save` (7,772);
  - `<title>-slot1-settings-autosave/settings.save` (5,228).

**Verdict.**
- **The title saves now.** The cause was one unresolved SaveData_native function: its "started"
  answer made the title wait for an event that never came. KytyPS5 does not implement it either.
- **Not established:** what the function prepares when the directory exists (for example a
  restore). With saves on disk, the next start shows whether "not found" is still a safe answer, and
  whether the settings survive.
- **Saves go to `_SaveData/UNKNOWN`:** the host finds no `TITLE_ID` in this package's parameters.
  The directory is per title only by accident. A second title with the same problem would share it.
- **The opening (F182) is still untested with saves working.** The save thread's poll loop was not
  holding the game thread, but a cinematic waiting for the new-game save is now possible to rule out.

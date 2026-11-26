# 0158 — Deleting a save stuck on "DELETING SAVE DATA": the title keeps a system progress dialog open while it deletes, and the host's stand-in reported it finished at once

**Question.** The maintainer (2026-10-18): deleting a save slot in the second title stops on the
"DELETING SAVE DATA" screen; the menu still takes input (the cursor moves, unseen) but the
picture never updates. Why, and what should the host do?

**Setup.**
- BC-250 dev box, runs 628–633 (2026-10-18 08:40–09:50), the scripted-input player of the
  host (`KYTY_BC5_INPUT_CMD`; the file is read as it grows, so the route was driven line by
  line from the laptop against screenshots — no blind timing).
- Host journals: `KYTY_BC5_SAVE_TRACE=1` now also prints the dialog stand-ins' calls on stderr
  (`dialog trace: …`, `dialog.cpp`) and `SaveDataDelete`'s path and result; the host's own
  call log (`PRINT_NAME`) is silent in play mode and was of no use.
- gdb attached to the stuck run (631): backtraces of all threads.

**Result.**
- Route: start screen ✕ → "SELECT SAVE SLOT" (when saves exist the list comes first); △ on a
  slot = DELETE SAVE, the title's own "ARE YOU SURE?" box, ✕ = accept → "DELETING SAVE DATA".
  (✕ on a slot opens CONTINUE GAME / Load Game / View Credits; *Continue* loads the game and
  shows black — the maintainer's "load hangs on a black screen" — it is the gameplay path of
  F201, killed within 20 s in runs 629–630.)
- The stuck run: the title's "Save Thread" is inside `SaveDataDialogOpen`, called again and
  again: `SaveDataDialogOpen mode 5 disp_type 3 … prog_bar 0x… dir "i38-slot1-game"` then
  `UpdateStatus`, then `Open` once more, forever. Mode 5 is the progress-bar dialog, display
  type 3 the delete. The title expects the dialog to be **running** (status 2) while it does
  the delete itself, closes it with `Close`, polls `UpdateStatus` for finished (3), reads the
  result and terminates. The stand-in set the status to finished inside `Open`, so the title
  saw its dialog end before anything happened and reopened it — and `SaveDataDelete` was never
  reached. With the dialog "open" the title stops drawing its menu; its input still runs.
- With `Open` → running, `UpdateStatus` leaving a progress-bar dialog running until `Close` and
  ending a message dialog at the first poll (as if OK were pressed), the title runs the whole
  sequence (run 632): Open, IsReadyToDisplay, `SaveDataDelete` of the slot's game save,
  101 × `ProgressBarSetValue`, Close, finished, Terminate; the same for the slot's settings
  save; the list shows "NEW GAME 1 — EMPTY" and the cursor moves. The same status machine is
  applied to `MsgDialog` (progress-bar mode 2).
- The slot came back at the next start: `SaveDataDelete` used `File::DeleteDirectory`, which
  is `rmdir(2)` and fails on a directory with files. It now removes the tree
  (`std::filesystem::remove_all`); run 633 removed both directories (`removed 2 entries,
  error 0`) and the slot stays empty.

**Verdict.** Two host defects, both fixed generically in the emulator (`dialog.cpp`,
`libSaveData.cpp`, patch 0001): a system dialog must report *running* after `Open` — a
progress-bar dialog until the title closes it, a message dialog until the first status poll —
and a save delete must remove the directory tree. Not covered: dialogs with real choices (the
stand-in always answers OK) and the list-mode dialog (mode 1), which no title has used here.

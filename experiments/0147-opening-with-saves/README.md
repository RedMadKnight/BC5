# 0147 — The opening after New Game with saves working: still the first shot

**Question.** Experiments 0145 and 0146 gave the second title working saves. The opening after
New Game kept its first shot while saves were broken (F182); the new-game autosave was one candidate
gate. Does the opening move now?

**Setup.**
- BC-250 dev box, 2026-10-17 08:24–08:29, maintainer away (ran by Claude over SSH, with the
  maintainer's instruction to close the game 10–20 s into the in-game cutscene: longer runs have
  taken the machine down).
- Run 576: the play shortcut's settings (`play-pkg-log.sh`: guest log, `KYTY_BC5_SAVE_TRACE=1`,
  `BC5_DIRECT_SKIP_PGM=11d049aa00`, no BVH_MISS), emulator build of 23:54 (exp 0146), saves of
  slots 1 and 2 on disk, GPU hang watcher on.
- Input (`KYTY_BC5_INPUT_CMD`, appended live between screenshots): ✕ at 80 s (screen reader
  prompt) → slot list → down, down, ✕ (New Game 3) → challenge level "The Mutant" ✕ → "Before you
  start: New Game" ✕ at 08:27:53 → screenshots at +15, +35, +43 (a ✕ for a start screen that never
  came), +44, +49, +54 s → `pkill -x kyty_emulator` at +62 s (19 s after the first cutscene shot).
- Raw: screenshots are game output (not committed); the save lines are in the capture
  `~/bc5-data/captures/play-20261017-0824`.

**Result.**
- The new-game path saves: `2mfSRGdshtk` → NOT_FOUND for `i38-null-prefs` (rewritten, 7,772 bytes),
  `i38-slot3-game-autosave` and `i38-slot3-settings-autosave`; the slot 3 files appeared on disk.
- No start screen this time: New Game went straight to the opening (the ✕ at +43 s hit nothing
  visible).
- **The opening keeps its first shot**: the +35, +44, +49 and +54 s screenshots are the same
  forest frame (the start screen's background without the logo), the subtitle `Logan: [agitated
  growls]` appears at +44 s, the camera does not move, no characters. Same as experiments 0136
  and 0141.
- No GPU timeout, no kernel message; the emulator exited on SIGTERM at once.

**Verdict.**
- **Saves were not the gate.** F182 stands with its remaining leads (experiment 0142): the guest
  PCs of the waiting threads over time, and the signaller of their condition variables; a GPU
  result polled in memory (character visibility, streaming feedback) is still possible.
- Running the opening is safe for ~20 s with the skip; the kill at 20 s is part of every such run.

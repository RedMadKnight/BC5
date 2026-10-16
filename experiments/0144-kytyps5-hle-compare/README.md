# 0144 — KytyPS5's HLE against ours for the second title's opening: no unimplemented call after ✕

**Question.** KytyPS5 cannot run here (experiment 0143). Its source can still be compared with our
host (KytyPlus with the BC5 patch). Does the game, from ✕ on the start screen on, call anything our
host leaves unimplemented or answers differently from KytyPS5? Such a call could hold the opening on
its first shot (F182).

**Setup.**
- Source only, 2026-10-16:
  - KytyPS5 at 5dec523 (`~/src/KytyPS5-build`), with history in `~/src/KytyPS5`;
  - our host source in `~/src/KytyPlus`.
- Guest log of run 572 (experiment 0142): New Game at 100 s, ✕ at 140 s, 230 s in all.
  - Lines 624,110 and 817,949 are the first ones stamped at or after 100 s and 140 s.
  - Our loader journals every call that reaches an unresolved import ("Unresolved import stub
    called").
- Raw: `raw/stubs-and-saves.txt`, summarised so that it carries no paths.

**Result.**
- **Nine unresolved imports are called in the whole run, and all of them before ✕.** The last one is
  at line 331,087.
  - KytyPS5 implements eight of them: entitlement requests (request, poll, delete, 12 times each),
    the VRR status, the PNG encoder, `KernelGetOperationMode`, and
    `VideoOutAllowOutputResolutionWqhdDetection` (964 times).
  - The ninth (`juWbTNM+8hw`, Posix, four times) is not implemented in KytyPS5 either.
  - The entitlement and VRR functions came in KytyPS5 commit 30a4673 (2026-10-16).
- **Save data after ✕:**
  - the game searches for its autosave directory once;
  - then it polls `SaveDataGetEventResult` 642,812 times, about 7,000 a second, starting at line
    820,677. No poll comes before ✕.
  - Our host and KytyPS5 both answer "not found" while no event is queued.
  - The two differ in one producer only: KytyPS5 queues a memory-sync-end event from
    `SaveDataSyncSaveDataMemory`. The game never calls that function in run 572.
- **No video decoder:** the game calls no Videodec2 or Vdecsw function. Its videos are Bink, decoded
  by the game itself; Bink's threads exist only from 3.8 to 37 s (F182).

**Verdict.**
- **KytyPS5's HLE shows no difference that explains the opening.** Nothing unimplemented is called
  after ✕, and the save-event polling gets the same answer on both.
- The opening was skipped in an earlier play session, and the game went on to gameplay. So the
  save-event loop does not gate the game; it is likely the save thread's idle loop.
- What holds the cinematic is still on the game's side, and F182's next step stands: sample the
  guest PCs of the waiting threads, and follow the condition variable's signaller.
- Porting the eight functions from KytyPS5 is hygiene only, not a lead for the opening.

# 0084 — the second title never asks the driver for an idle GPU

**Question.** The host answers the driver's "submit done" (0xc0048116) and "wait idle"
(0xc0048117) ioctls at once. With asynchronous submission, a title that waits for an idle GPU
before rewriting its data would therefore not wait. Is that what still lets the second title run
ahead of the GPU under deferred flips (experiment 0083)?

**Setup.**
- KytyPlus patch:
  - `BC5_DIRECT_IDLE_DRAIN=1` drains the jobs in flight at a wait idle; `=2` also at a submit
    done.
  - Both calls are counted in the journal, at the first call and every 500th.
- Run 336 (`run336.sh`, 2026-10-14 11:31): run 335 (`BC5_DIRECT_SOFTCP_POST_IB=1`, flips
  deferred) plus `BC5_DIRECT_IDLE_DRAIN=2`.

**Result.**
- The journal has no call of either ioctl: the title uses neither.
- The menu is garbled as in run 330 (letters missing, the selection bar shows the forest scene).
  24.9 fps.
- Also seen in the journals: the host clears the flip label at a 16-dword graphics buffer's wait
  ("still set at the wait: cleared"):
  - 1,895 times with undeferred flips (run 333);
  - 63–68 times with deferred ones (runs 327, 336), where experiment 0069's wait for the
    pending flip comes first.

**Verdict.** Failed for its question: the idle ioctls are not the race. The knob stays, off by
default.

What still lets the title get ahead with deferred flips is open. Ruled out so far:
- the flip status (0082);
- the idle ioctls (here).

Early EOP events are part of it (0083).

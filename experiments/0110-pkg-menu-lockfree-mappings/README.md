# 0110 — reading the sorted mapping list without the device mutex: no gain, reverted

**Question.** After experiment 0109 the menu runs at 49 fps. A new stack profile (run 405,
2026-10-15 01:4x, the same sampler as 0107) put the title's render thread here:

| samples | where |
|---|---|
| 6 | waiting for `g_dev_mutex` in `submit_one` |
| 3 | `bc5::direct::Device::sorted_mappings()` called from `piece_check` |
| 2 | the CS ioctl |
| 8 | elsewhere |

`Device::submit` holds the backend's own mutex through the filter, the BO list and the CS ioctl.
`sorted_mappings()` takes that mutex even when the list has not changed, so the render thread
waits for the ring thread's ioctl there. Does a lock-free fast path help?

**Setup.**
- Backend change, tried and then reverted, so not in the repository:
  - `Impl::list_gen` became atomic;
  - the sorted list was published as `std::atomic<std::shared_ptr<...>>` with its generation;
  - `sorted_mappings()` returned it without the mutex while the generation matched.
- The backend built without warnings, and its 51 unit tests passed (Fedora build,
  `backend-amdgpu`, `ctest`).
- Run 406 (02:05, unattended, menu only): the same setup as run 403 (0109).

**Result.**

| | run 403 (0109) | run 406 (fast path) |
|---|---|---|
| menu fps, 90–120 s | 49.1 | 47.9 |
| menu frame, median | 19.4 ms | 20.0 ms |
| intro fps, 28–40 s | 52.1 | 46.8 |

No failed or timed-out job and no GPU fault.

**Verdict.** Failed: no measurable gain, within run-to-run noise. Because the change adds a
lock-free path to the device's mapping state, it was reverted. The backend source, its unit tests
and the host binary are back to the state of experiment 0109. What holds the render thread is the
`g_dev_mutex` wait in `submit_one` itself, i.e. the ring thread's submissions (experiment 0107).
That is a scheduling question for a session with the maintainer present.

# 0070 — giving the display buffer back after the flip's copy, not after the refresh

**Question.** Experiment 0069 left tearing in busy moments. The flip in KytyPlus is asynchronous,
and the host cleared the buffer's label when the flip was only queued. Waiting for the
presentation at the refresh (`BC5_DIRECT_FLIP_WAIT_DONE`) costs half the frame rate. Can the
buffer go back to the game as soon as its pixels have been copied, with the copy shown at the
refresh?

**What KytyPlus does.**
- `FlipQueue::Prepare` runs on its GPU thread at once (0.02 ms after `VideoOutSubmitFlip`).
- `Presenter::PrepareFrame` records a copy of the guest's buffer into the presenter's own frame.
- In direct mode the guest range is invalidated first, so `BufferCache::ObtainBufferForImage`
  reads it on the CPU into staging memory (`TryReadBacking`).
- `Complete` marks the GPU copy done (state `Ready`).
- `FlipQueue::Flip` shows the frame at the refresh.

The buffer is therefore free once the request's frame has been recorded.

**Change (patch 0001; the default now).**
- `FlipQueue::WaitCopied` / `Bc5VideoOutWaitFlipCopied` return once no request of the buffer is
  `Reserved` or still being recorded. `Prepare` signals when the frame is set.
- The host's deferred flip clears the label after that, on a thread of its own (`bc5-flipdone`).
  The game's thread waits for it through the queued-flip count of 0069.
- Reads of 4 MiB and more in `TryReadBacking` are split over 4 threads
  (`KYTY_BC5_READ_THREADS`).
- Kept as options:
  - `BC5_DIRECT_FLIP_RELEASE_EARLY=1`: the 0069 behaviour;
  - `BC5_DIRECT_FLIP_WAIT_DONE=1`: wait for the presentation;
  - `KYTY_BC5_FLIP_TIMING=1`: the preparation's timing.

**Result** (Sky Garden's start, standing, 60 s; `raw/runs-305-309.txt`):

| Release of the display buffer | fps | game thread waiting on labels |
|---|---|---|
| at the wait, as before 0069 (tearing, run 283) | 46.2 | — |
| when the flip is queued (0069, run 306) | 41.4 | 4.8 ms |
| after the GPU copy (`Ready`, run 305) | 36.1 | 9.0 ms |
| after the copy is recorded (run 307) | 36.3 | 8.7 ms |
| as 307, guest read on 4 threads (run 309) | 37.9 | 7.6 ms |
| after the presentation (`WAIT_DONE`, 0069) | 30 | — |

- The galaxy map stays at 59.7 fps (run 304).
- No label was cleared by the fallback, and there was no timeout.
- The preparation takes 2.9–3.1 ms with the 4-thread read (3.9–4.4 with one). The rest of the
  wait is the frame's GPU work, which has to finish before its flip.

**Verdict.** Correct by construction; the maintainer's view of the picture is pending. The price
against 0069 is about 3.5 fps here, and the double-buffered pipeline itself is the larger part.
A further gain needs the copy without the CPU read, for example the display buffer copied by the
direct path's own ring right after the frame's jobs.

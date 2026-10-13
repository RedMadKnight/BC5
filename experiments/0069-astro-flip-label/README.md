# 0069 — the tearing the ring order brought: a flip label released too early

**Question.** With the shortcut's settings of 2026-10-13 the maintainer saw the picture smear,
"as if there were no vertical sync", from the start of the game. It had not been there before.
Which of the day's changes causes it?

**Setup.** Two of the day's changes can affect what is on screen:
- the ring order of 0055/0060;
- the larger imports of 0066.

The others (0061, 0064, 0065, 0067) send the GPU the same bytes. The maintainer played the
shortcut in four variants, each session with the journal (`PLAY_CAPTURE=1`, new in the launcher):

- A: everything on;
- B: ring order off, imports at 64 MiB;
- C: ring order on, imports at 64 MiB;
- D: ring order on, with the first fix below.

Then runs 302 (title to the galaxy map) and 303 (a level) tested the fixes. Counts are in
`raw/sessions.txt`.

**Result 1, the cause.**

| Session | ring order | flip label cleared at the wait | frames | smearing (maintainer) |
|---|---|---|---|---|
| A | on | 4,691 | 8,221 | yes |
| B | off | 40 | 7,760 | no |
| C | on (imports 64 MiB) | 4,850 | 8,052 | yes |
| D | on, first fix | 0 | 8,516 | mostly gone; left in busy moments |

The ring order is the cause, and the large imports are not.

The mechanism:
1. Before a frame renders into a display buffer, its graphics buffer waits for that buffer's flip
   label. The console's VideoOut clears the label when the flip has happened.
2. The host clears a label still set at that wait (run 73, written when flips were immediate).
3. With the flip deferred behind the frame's jobs (`FLIP_DEFER`, 0045), the label is usually
   still set because that flip is still queued.
4. Without the ring order the game's thread was held long enough in its 8 ms waits that the flip
   had happened. With the ring order it arrives early in more than half the frames, the host
   clears the label, and the GPU renders into the buffer about to be shown.

**Fix 1 (default).** A count of deferred flips per buffer. While one is queued, the wait is served
on the CPU until that flip has run, at most 100 ms, before the old clearing.
- Run 302: 0 labels cleared, waits of about 1 ms, 59.97 fps on the galaxy map.
- Session D: 0 cleared, no timeout, the smearing mostly gone.

**Result 2, what is left.** KytyPlus's `VideoOutSubmitFlip` only queues the flip. The presentation
thread reads the guest's buffer later, at the display's refresh. The deferred flip clears the label
when the call returns, so in busy moments the next frame can still render into the buffer before
it has been read.

**Fix 2 (opt-in, `BC5_DIRECT_FLIP_WAIT_DONE=1`).** The label is cleared only once
`VideoOutDriver::WaitFlipDone` returns (`Bc5VideoOutWaitFlipDone`, a thread of its own). Run 303:
no tearing possible, but the later level runs at exactly 30 fps. The buffers are double, the
display is 60 Hz, and a frame of a bit more than 16.7 ms waits about 25 ms for the next refresh.

**Verdict.** The cause is found and fixed in part. The default is fix 1: no fps cost, and the
tearing is left only in busy moments. A complete fix without the 30 fps cost needs the presentation
to copy the guest's buffer as soon as a flip is ready and show the copy at the refresh, so that the
buffer goes back to the game after the copy, not after the refresh (KytyPlus `FlipQueue`; not
done). Until then, `BC5_DIRECT_FLIP_WAIT_DONE=1` trades the frame rate for a clean picture.

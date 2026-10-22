# 0213 — at 400 ms the wait limit never engages, and the long frames of every run are the game thread outside the host, not label waits

**Question.** Does a 400-ms game-thread wait limit (`BC5_DIRECT_DCB_WAIT_MS=400`) cost frames,
compared with 100 ms (exp 0207/0208) and the default 8 ms? 400 ms was proposed because it covers
every wait seen in exp 0209 (≤ 393 ms).

**Setup.**
- One scripted run, tcpW3, 19:30–19:41 on 2026-10-22, attended, on the box supervisor's Go.
- It is the same as tcpW2/tcpW2b except for the limit:
  - the water session's bench `bench0201.sh tcpW3 600`, from the private lake save copy;
  - the shared build as it was at 19:30, before the evening's rebuild with APR read-ahead;
  - the launcher's defaults (skip list in force) plus `BC5_DIRECT_DCB_WAIT_MS=400
    BC5_DIRECT_WAIT_TRACE=1`.
- Journal: `play-20261022-1930`.
- Before the start: no emulator, no BOX-LOCK, boot ac5dab11, no amdgpu line since R11B's ring resets
  at 19:28.
- The analysis uses exp 0209's extraction (one read pass at 20:01, in a free gap) and its
  `ana0209.py`.
- The frame classification compares all five runs (tcpW1, tcpW1b at 8 ms; tcpW2, tcpW2b at 100 ms;
  tcpW3 at 400 ms). It uses each frame-profile line's split of the time since the last flip:
  - the game thread inside the host, and of that the label waits;
  - the game thread outside the host, i.e. in the title's own code or not running;
  - GPU busy.

**Result.**

1. tcpW3 ran the full 600 s with no timeout, no fault and no give-up. Frames
   (`raw/five-runs.txt`): mean 36.1 ms; over 100 ms 111; over 250 ms 60; over 1 s 5. That is more long
   frames than any other run (7–16 over 250 ms).
2. **The limit never engaged.** The longest game-thread wait in the whole run was 71 ms, on any label
   (`raw/tcpW3-ana.txt`). On 0x12004b3c38, 7,426 of 7,478 traced waits ended within 4 ms, and the
   longest of the rest was 40 ms. With no wait reaching 100 ms, 400 ms behaved exactly like 100 ms.
3. **The long frames are the game thread outside the host.**
   - Of tcpW3's 60 frames over 250 ms, 58 have more than half of their time outside the host, mostly
     about 0.5 s at a time between t ≈ 200 and 460 s. Label waits in them were 0–4 ms
     (`raw/tcpW3-long-frames.txt`).
   - The same holds for every run (`raw/frames-over-100ms-by-cause.txt`). Frames over 100 ms where
     label waits fill more than half:

     | Run | Limit | Frames over 100 ms | Label waits | Outside the host | GPU busy | Mixed | Label-wait time in them |
     | --- | --- | --- | --- | --- | --- | --- | --- |
     | tcpW1 | 8 ms | 44 | 0 | 37 | 0 | 7 | 208 ms |
     | tcpW1b | 8 ms | 63 | 1 | 53 | 1 | 8 | 192 ms |
     | tcpW2 | 100 ms | 121 | 3 | 107 | 1 | 10 | 692 ms |
     | tcpW2b | 100 ms | 70 | 1 | 56 | 3 | 10 | 281 ms |
     | tcpW3 | 400 ms | 111 | 1 | 100 | 1 | 9 | 604 ms |

**Verdict.** Answered, and it corrects two earlier readings.
- The wait limit does not show up in the frame times at 8, 100 or 400 ms. Label waits fill more than
  half of at most 3 of the 44–121 frames over 100 ms per run, and they add up to 0.2–0.7 s per
  10 minutes.
- The differences in long frames between runs (F265's "possible cost" at 100 ms, and tcpW3's 60
  frames over 250 ms) come from how long the game thread stays outside the host. That varies from
  run to run, independently of the limit. My first message on tcpW3 ("400 looks clearly worse") was
  sent before this breakdown and was wrong.
- At 400 ms, no wait in this run came near the limit. So 400 ms and 100 ms cannot be told apart
  here; both remove the give-ups.
- What makes the game thread stay outside the host for ~0.5 s at a time is open. Exp 0200's
  samples suggest swap and IO stalls, but these runs had no sampler. The next run (tcpW4) adds a
  /proc sampler at 10 Hz. That also serves the maintainer's request for a dynamic limit: whether the
  title's threads make CPU progress during a long wait.

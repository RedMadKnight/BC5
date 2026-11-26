# 0096 — no pass of display-buffer size; an async compute pass reuses the 2560×1440 target's memory

**Question.** Which pass writes the second title's 3840×2160 display buffers (experiment 0095)?
Look for any dispatch of display-buffer size in every buffer kind, compute and ring buffers
included.

**Setup.**
- `BC5_DIRECT_FIND_ALL` also journals every direct dispatch of at least 200×100 groups in every
  buffer kind, with its program and user data 0–2 (an output descriptor's base and format).
- Run 360 (20:43): 3 s from 100 s in the menu, the play shortcut's settings. Raw:
  `raw/run360-big.txt`.
- The two journals of runs 346 and 352 were also searched for 480×270 groups or a 3840×2160
  viewport.

**Result.**
- No dispatch has 480×270 groups and no draw has a 3840×2160 viewport, in any buffer kind.
- Large passes, about 58 per 3 s each, so once a frame:
  - graphics buffers: 320×180 (2560×1440) and 208×117 (1664×936) passes, already known;
  - compute buffers (`acb`): five 208×117 passes, programs 0x11d0372500, 0x11d03f8c00 and
    0x11d0287500 (three times).
- 0x11d0372500 writes an 832×468 11_11_10-float image whose base is 0x114c6c0000. That memory is
  also the 2560×1440 RGBA8 target the final pass of 0094 reads and writes. The title aliases
  transient memory across the graphics and async compute queues.

**Verdict.** Inconclusive for the display buffer's writer: no pass of its size exists, so it is
filled in some other way (a copy, a scaled flip, or system software we emulate). TODO(verify).

New suspect for the black background: 0x114c6c0000 is shared between an async-compute effect and
the 2560×1440 composition. On the console the queues' labels order that reuse. On our single ring,
with cross-queue waits served on the CPU or left to ring order, the compute pass can overwrite
the composition's content, or run after it.

Next:
- check the order of `acb` 0x11d0372500 against the graphics passes reading and writing
  0x114c6c0000 in one frame (submission numbers in the journal);
- check the flip path for scaling.

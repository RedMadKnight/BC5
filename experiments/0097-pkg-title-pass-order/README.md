# 0097 — the order of the second title's large passes in one menu frame

**Question.** Does the async-compute pass that writes 0x114c6c0000 (experiment 0096) run before
or after the graphics passes that use the same memory?

**Setup.** Run 360's journal (experiment 0096): the large dispatches in submission order, which is
also the GPU's order on our single ring, apart from waits left to the ring. Raw:
`raw/run360-order.txt` (journal line numbers, buffer kinds, programs, output descriptors).

**Result.** The same order repeats every frame:
1. compute buffers: 0x11d03f8c00 → 0x113cb40000;
2. compute: 0x11d0372500 → 832×468 11_11_10 at 0x114c6c0000;
3. compute: 0x11d0287500 three times → 0x112c7b0000, 0x11603e0000, 0x113d770000;
4. graphics: the 1664×936 passes into 0x113cb40000, 0x1158260000 and 0x113d770000;
5. graphics: the 2560×1440 pass with 0x114c6c0000 as RGBA8 (cs 0x11d0404200 of 0094). It reads
   what is there and blends layers over it;
6. graphics: 2560×1440 passes into 0x113d770000, 0x1158260000 (the finished scene, 10_10_10_2)
   and 0x117ffa0000.

**Verdict.** Answered for its question:
- The async-compute effect writes 0x114c6c0000 early in the frame. The pass of 0094 then reads
  that memory as RGBA8 later in the same frame, so it reads the effect's data reinterpreted, not a
  composed image. On the console the title's labels order this reuse too, so the order itself is
  not wrong. What it shows is that 0x114c6c0000 is scratch, not the image on the screen.
- The finished scene is produced at the end of the frame. It is consumed, if at all, by the next
  frame, through bindless tables we cannot follow by address.

Open: which pass fills the 3840×2160 display buffer. It is likely a `DISPATCH_INDIRECT` or an
indirect draw, whose size the host cannot see at submission, writing through the bindless
table 0x11e0007aa0. The next diagnostic is a dump of the display buffer with its real swizzle at
several points in a frame.

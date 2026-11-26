# 0173 — The game thread's label waits (2.6 ms a frame with chains) are the title's own compute submission arriving later, not the host's polling

**Question.** With the submission chains the second title's frame is 19.9 ms; 2.6 ms of it the game
thread spends in the host's label waits. Which waits, and can the host shorten them?

**Setup.**
- The "two rings" wait (`bc5LleAgc.cpp`): a graphics buffer of the game thread waits
  (`WAIT_REG_MEM`) on a label the compute ring writes. The host holds the game thread until the
  writer is queued on a ring (`ring_will_satisfy`: then the wait is kept for the GPU), the label is
  already written (satisfied on the CPU), or `BC5_DIRECT_TWO_RING_WAIT_MS` (4) has passed (not
  served: the buffer's head is split off). New: a journal line every 1,024 such waits with the time
  spent per outcome.
- Run 827: chains, the gameplay route (`route.sh`, exp 0169).
- Run 828: the same with a fast poll — the ring thread (which finds the title's compute buffers by
  polling its queues every 200 µs) polls without sleeping while a game thread is in such a wait,
  and the game thread checks without sleeping for the first 200 µs (a 20 µs sleep took ~70 µs).

**Result.**

| | 827 | 828, fast poll |
|---|---|---|
| waits kept for the GPU | 17,164, 7.00 s, 0.41 ms each | 18,185, 7.12 s, 0.39 ms each |
| satisfied on the CPU | 1,155, 0.28 s | 1,149, 0.30 s |
| not served (4 ms) | 113, 0.46 s | 122, 0.49 s |
| frame (host, of it label waits) | 19.94 ms (6.66, 2.57) | 19.91 ms (6.68, 2.54) |
| flips per second | 50.4 | 50.5 |

  The waits do not shorten when the host looks for the writer faster: the game thread waits for the
  title's own compute thread to submit the buffer that writes the label (about 0.4 ms after the
  graphics buffer, ~1.7 times a frame).

**Verdict.** The host's polling is not the cost; the title submits the writer after the reader. On
the console the graphics ring itself waits and the CPU goes on. Here the host would have to queue
the graphics buffer with the wait before its writer exists on any ring, which is how exp 0071 lost
the machine twice (a GPU wait on a writer that never comes until the ring is reset). The fast poll
is reverted; the time-by-outcome line stays (F228). A safe version needs the guarantee that the
writer will come — e.g. a host-side queue for the graphics ring that holds the buffer and submits
it from the ring thread once the writer is queued, while the game thread returns at once: the
game's later graphics buffers would have to queue behind it in order (TODO(verify) the cost of
that ordering).

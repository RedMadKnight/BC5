# PLAN: the memory wall after K1r (exp 0412, 2026-11-13 evening; laptop, nothing run for this)

Asked by the top: which option A–G of `DESIGN-memory-architecture.md` now, with the MiB to recover and the first
measurement. Marks: [M] measured, [I] inferred, [old] measured before 11-13 on another build or save.

## Where the wall stands (his play of 18:04 on the K1r shortcut, the ledger's line at 130 s) [M]

| | MiB |
|---|---|
| GTT in use | 12,053 |
| direct memory pinned | 11,228 (11,122 under a view, 106 orphans) |
| private guest memory pinned | 270 |
| GTT beyond the guest (12,053 − 11,228 − 270) | **555**: the host's own buffers, not broken down |
| the title's views | 12,156; so 1,034 not imported: 822 under K1r's zero covers, about 210 written lazy memory |
| available / swap used / cgroup peak | 658 / 1,616 / 12,884 of the fuse's 13,000 |

The deficit: with 658 MiB available the box swaps 1.6 GiB and the emulator takes up to 474 major faults a second.
A recovery of about **1 GiB** would take the play off the wall; less than 0.5 GiB would not be felt [I].

## The options today

| | state on 11-13 | MiB | verdict |
|---|---|---|---|
| A, session | done: the shortcut stops Plasma's shell (118 MiB now) | 0.1 [M] | spent |
| A, host buffers | the 555 MiB above are unexplained | up to 0.3 [I, old estimate] | **measure now**: cheap, read-only |
| A, the smaller offer (12,800, the console's) | whether the title sizes its pools from the offer is NOT measured: every run that offered less died in the host (README sections 3, 57); the catchers for that (`KYTY_BC5_MEM_FIRSTFAIL`, `KYTY_BC5_TRAP_LOG`) are in the shared build since B | unknown; at most 1,024 (13,824 − 12,800) [I] | second in line: it is the console's own number, but each arm is a host bug to fix first |
| **B, no pages nobody wrote** | the READ side now exists and is sound: K1r's read-only zero cover, cv412, kl412, run on both titles and in his play. What is missing is the WRITE side for the eager heaps | up to **2,800** (wholly-zero 2 MiB chunks) [old, section 39] | **the option now** |
| C, CPU heaps out of the pin | `Wwise` is lazy already; `AssetHeap` is NOT a CPU heap: the fault of 11-13 morning was a shader's read in `AssetHeap Large`; left: `Physics` 192 | 0.2 [old] | not worth a rule of its own |
| D, E, F, G | unchanged | — | not proposed |

## Why B, and what exactly

Under a view imported by data a never-written chunk costs nothing today and reads as zero through K1r. The pinned
zeros sit in the heaps imported EAGERLY (whole, data or not), because the GPU writes into them and a GPU write into
an unmapped or read-only page is a fault. B is therefore one change: **an eager heap becomes "by data + K1r cover +
the write targets imported before the write"**. The write targets the host can name today: render-target and depth
binds (the bind hints), packet operands (K1 at the filter: `memory_operands`). Not named today: RW buffers and
images a shader writes through the descriptor tables. Each writer the host does not name is a write fault. Since
11-13 a fault ends the game with a record that names the address and the buffer (`BC5_FAULT_RECORD`,
`BC5_DIRECT_TIMEOUT_PROBE`), so a missed writer is found in one run instead of corrupting memory as the zero skip
did (section 48). The risk that stays: on ASTRO BOT a command-processor write into a read-only page ended in a
failed reset and a reboot (11:32). A B arm can reboot the box; it needs his word each time.

## The measurements, in order

1. **First, no risk, one scripted arm on build E (walk route at his save, 10 min):** (a) the zero scan that exists
   (`BC5_DIRECT_ZEROSCAN_AT`, log only) at five times, per eager heap: the MiB of 2 MiB chunks that are all zero at
   EVERY scan. That is B's floor on this route today (the old 2,800 is from another build and save). (b) In the same
   arm `snap0412.sh` with the emulator's `fdinfo` at the wall: what the 555 MiB are. Result: two numbers. If (a) is
   under 500 MiB, B is not worth its risk and the wall has no large lever left short of D.
2. **Log-only catcher for the writers (laptop work, then one arm):** for each eager heap, journal every write target
   the host can name (binds, packet operands) by chunk, and at the end the chunks that turned non-zero during the
   arm and were never named. Limit: a chunk the CPU wrote counts as unnamed too; the catcher gives an upper bound
   of the unknown writers, not their list.
3. **The rule, one heap at a time, his word first:** the largest eager heap by (a) goes "by data + K1r" behind a
   switch naming the heap; one scripted arm with the fault record on. Clean: the next heap. A write fault: the
   record names the writer; its target class gets an import rule (the descriptor read is the likely one), then again.
4. Only after 3 is clean on the scripted routes: his play.

Not in this plan: any cap, hard stop, learned window or "skip" list. The pin falls only where the title wrote
nothing and the GPU is shown to read zeros there.

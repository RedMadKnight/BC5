# ADR draft (exp 0438) — Cross-queue waits decided by the GPU, the doorbell as an event

**Status:** draft for the top session and the maintainer. Not accepted, not built. Number to be given on acceptance.

## Context

**What the console does** (the top session's statement of 2026-11-20, from how the title behaves; the hardware facts
are TODO(verify) against public AMD documentation):
- the title writes a queue's write pointer (the doorbell) and the CP/MEC sees the new packets at once;
- `WAIT_REG_MEM` is decided by the command processor when it reaches the packet;
- the title's submit call returns without waiting.

**What the host does today** (patch bb04219b; exp 0438's records):
- **Compute queues are polled.** `bc5-ring`, one thread, polls the doorbell pages every 200 µs and also does all the
  compute submission work: readiness walks, preparation, the device mutex, the kernel call. Its look at a queue can
  come 20 ms or more after the title's write for about 1 % of packets, and up to 1.6 s (c438 result 4). The time goes to
  device-mutex waits held by the game thread's preparation, and to its own direct sync (results 5 and 6).
- **Graphics waits are decided on the CPU.** A game-thread `dcb` wait whose label is not met and has no registered
  writer is polled on the title's thread (8 ms, then the limit). Then it is given up: dropped, the F262 family, and
  F865's cause.
- **Each patch has a cost or a flaw.** The host-side patches for this (holds, early registration: k438, k438b, r438)
  each add machinery, and each failed or cost frame time in exp 0438.
  - k438: a GFX wait kept before its writer was submitted did not see the writer run. The cause is not found:
    implicit sync is refuted by `amdgpu_sync_test_fence` (same-VM fences skipped); VMID and an F4 dependency are open.

## Decision (proposed)

Reproduce the console's model, in two parts.

1. **The doorbell is an event, seen by a thread that does nothing else.**
   - A watcher sees write-pointer moves and hands each queue's new slice to a submitter for that queue's ring.
   - Submission work (readiness, preparation, the kernel call) no longer delays seeing the next doorbell.
   - Per-ring submitters keep each ring's order. One ring's slow preparation does not hold the others.
2. **GFX waits stay on the GPU.**
   - A game-thread `WAIT_REG_MEM` on a label with no registered writer stays in the buffer and goes to the GPU.
   - The title's submit call returns at once. No CPU wait, no give-up, no hold, no early registration.
   - The writer arrives as the title rings it, and the watcher makes that prompt.
   - Precondition: no host-made kernel dependency may make a compute job wait for a GFX job that is waiting for it.
     F4's whole-job fences and anything found by test t438 must go or be bounded to true data hazards. That is why
     t438 comes first.

## Doorbell options

| option | how | latency to see a write | CPU cost | risk / work |
|---|---|---|---|---|
| A. watcher thread, short sleep | one thread reads every registered queue's write pointer in a loop with a 20–50 µs `nanosleep` (or `clock_nanosleep` at the timer slack) and does nothing else; slices go to per-ring submitter threads through a single-producer queue each | ≤ the sleep + wake latency, about 50–100 µs (TODO(verify) on the box: timer slack, rtkit priority) | about 1–3 % of one core at 50 µs (the walk over ~20 queues is a few hundred ns) | simple; no kernel features; the submitters need the per-ring order bc5-ring has now, and acb_ready's state (g_acb_heads) becomes per ring |
| A'. watcher thread, spin | as A with `_mm_pause` spinning | below 1 µs | one core | no; the box has 16 threads, but the title's own threads and R's RT budget need them |
| B. write-protect trap | the doorbell page is mapped read-only; the title's write faults; the host's SIGSEGV handler records the queue, does the write and returns, and the watcher is woken | the fault's cost on the title's thread, a few µs per write (TODO(verify): measure); the watcher wakes at once | a fault per doorbell write (the title rings a few thousand times a second: about 1 % of one core, an estimate) | the host's fault handler is already in the hot path for guest memory (exp 0412); emulating the store needs decoding or a single-step; the risk is moderate |
| C. userfaultfd write-protect | `UFFDIO_REGISTER_MODE_WP` on the doorbell page; a handler thread reads the fault, notes the queue, unprotects, wakes the writer | the handler's round trip, tens of µs (TODO(verify)) | per write: a context switch to the handler | needs WP support for this memory type (anon/shmem) on 7.3.3 and unprivileged userfaultfd or `UFFD_USER_MODE_ONLY` (TODO(verify) on Bazzite); the writer blocks during handling |

**Recommendation:** A, with per-ring submitters. It is the smallest change that separates seeing from submitting.
- B and C give exact event times but put a fault on the title's thread, and they need features to check first.
- A's 50–100 µs is far below today's 20 ms+ tail.

## What it removes

**When both parts land:**
- the F262 CPU wait and give-up on the game thread;
- k438, k438b and r438 (none shipped);
- the 8 ms poll of exp 0428's split-late path;
- the chain hold's need for F10/F16/F18 (they exist because the host decides waits at submit), once graphics waits
  are on the GPU and compute waits are kept in ring order. That last part needs its own check.

## Order of work (proposed)

1. t438 (a --submit test, about 1 s of GPU): does a compute job run while a GFX job of the same VM waits on the GPU
   for it, with the emulator's BO types? With an explicit dependency as a control.
2. The watcher (A) and per-ring submitters, with c438's records. Measure the look gaps against today's.
3. GFX waits on the GPU with no CPU wait. Test on the scene and the route with RT on. A GPU fault is a bug with a
   record.

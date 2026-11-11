# Shorter holds of the device mutex: design (exp 0412, 2026-11-11)

The maintainer's order: "No to rób ten osobny projekt". This note is the design; nothing of stages 1–3 is built.
Measured facts carry [M] and their section of `README.md`; the rest is reading of the code and is marked [I].

## What is measured

One mutex, `g_dev_mutex`, is held by `submit_now` from its first line to its last. Three threads submit: `bc5-ring`
(the asynchronous ring's submitter), the title's Render Thread, and `bc5-chainwd` (closes chains left open).
Run q1parts (arm fast2, 179 s, build g412k, `BC5_GUARD_LOCK_STAT=1`, `raw/q1parts-lockstat.txt`) [M]:

| part of the work under the mutex | `bc5-ring` | Render Thread | `bc5-chainwd` | all | longest single |
|---|---|---|---|---|---|
| device submit (filter, state, BO list, CS ioctl) | 16.2 s | 14.5 s | 5.4 s | 36.1 s (46 %) | 246 ms |
| direct sync (the guest's direct memory: pin, import, map) | 10.5 s | 2.6 s | 2.6 s | 15.7 s (20 %) | 847 ms |
| learned windows (`learned_apply`) | 6.5 s | 1.2 s | 1.3 s | 8.9 s (11 %) | 606 ms |
| anon sync (`sync_mappings`, the walk over the guest's VMAs) | 3.2 s | 1.2 s | 2.5 s | 6.9 s (9 %) | 217 ms |
| prepare (aliases, the buffer's survey, split, state tracker) | 2.4 s | 2.3 s | 1.0 s | 5.7 s (7 %) | 39 ms |
| tail, hints, probe | 1.6 s | 2.1 s | 0.9 s | 4.6 s (6 %) | 23 ms |
| **held** | 40.3 s | 23.8 s | 13.7 s | 77.8 s of 179 s | |
| waited for the mutex (run p1lock, section 20) | 17.0 s | 11.7 s | 6.4 s | 35.1 s | |

The journal's own frame profile of the flipping thread, the same run, play phase (45.3 s of wall clock) [M]: mapping
sync 3.0 s, hints and learned 1.1 s, the device's prepare 3.1 s, its CS ioctl 1.9 s, BO list 0.0 s; waiting at the
flip 9.8 s; the GPU busy with that thread's jobs 25.2 s.

## What the numbers say

1. Two different costs share the mutex. **Per-buffer work** (device submit, prepare, hints: 46 s) is short and steady,
   0.3–1 ms a buffer. **Mapping maintenance** (direct sync, learned, anon sync: 31.5 s) is rare and long: its single
   holds are 200–850 ms, and while one runs no thread can submit anything [M]. The second group does not depend on
   the buffer being submitted; it runs inside whichever submission happens to come next [I, from the code].
2. The runs have 51–61 s with a frame gap over 100 ms (sections 18–20) [M]. The long holds are the first suspect for
   those gaps [I]; no run has yet put a hold beside a gap, which is stage 0.
3. What a shorter hold can give is bounded: the Render Thread waits 11.7 s of 180 s for the mutex (6.5 % of its
   time), so the mean frame rate can gain single percents. The gain to expect is in the gaps, not in the mean [I].

## Why not simply drop the mutex around the device call

- The order in which buffers pass `submit_now` is the order they reach the GPU ring, and the host carries CP state
  from one buffer to the next (`g_carried`, the state tracker, the chain's kept waits, the label bookkeeping). Two
  threads inside the device call at once would interleave that state [I].
- The device has its own lock, and the kernel takes the CS in ring order: the ioctls cannot run in parallel anyway.
- A wrong order or a stale mapping list is not a slow frame here, it is a GPU hang, which on this box can take the
  machine down (CLAUDE.md, hard rule 5; F6). Every stage below keeps the order of submissions exactly as it is.

## Stages

Each stage is one switch, default off, in a private build of the exp 0412 line, with a CPU test of old against new
where the change is a pure function, and an ABBA on the scripted load. A stage that changes what reaches the GPU
needs the top session's review before the maintainer plays it.

**Stage 0: catchers (no change of behaviour).** `BC5_GUARD_LOCK_STAT` also writes one line for every hold of 30 ms or
more (thread, part, ms, time) and the longest single wait per thread; the runner puts those times beside the frame
gaps. Verdict it must give: what share of the gaps over 100 ms has a long hold inside. If the share is small, stages
1 and 2 are not worth their risk and the project stops here with that answer.

**Stage 1: mapping maintenance outside other threads' way (`BC5_GUARD_SYNC_SPLIT=1`).** The long part of the direct
sync is the kernel work per new chunk: udmabuf create, import, VA map (the ioctls seen in `direct_sync_one` and
`lzr_pass`, section 19). The list of mappings that submissions read changes only at the end. So: under the mutex,
decide what to pin (the want list) and take a generation number; drop the mutex; do the kernel work on BOs nobody
else can name yet; take the mutex again, check the generation, and splice the result into the list (if the layout
moved meanwhile, redo the want list for the difference). Submissions in between see the old list, which is what they
would have seen had they come first. The same shape for `learned_apply`. Cut and release (lazy release, split) stay
wholly under the mutex: they remove what a submission may be using.
Risk: a buffer submitted during the kernel work whose operands lie in the memory being pinned gets those packets
NOP-ed by the operand check, where today it would have waited and drawn. To keep today's result exactly, a
submission that the probe finds uncovered waits for the pin in flight instead of going on (a condition variable on
the generation). Test: the unit test drives the want/splice functions against the old single-step function on
random layouts; the box test counts `unmapped_drops` off against on, which must be equal.

**Stage 2: the buffer's own work before the mutex (`BC5_GUARD_PREP_OUT=1`).** The probe, the survey of the buffer and
the hints read only the buffer and a snapshot of the mapping list. They can run before the lock when the snapshot's
generation is rechecked under it. This is 6–7 s of the 78 s; small, and it touches the 900-line function with
most history in the project. Only after stage 1 shows a gain.

**Stage 3: the device call.** 46 % of the hold, and it cannot leave the ordering lock. What can shrink is its
inside: prepare 3.1 s and the CS ioctl 1.9 s per 45 s on the flipping thread. That is work on the shared backend
(`backend/src/direct.cpp`, the filter) and belongs to its own experiment with the backend's tests; not part of 0412.

## What this project will not fix

The frame's CPU part and GPU part run one after the other (the flip waits for the frame's jobs; 9.8 s of 45 s at the
flip). Deferring the flip was measured three times and breaks the second title's text (F68, F141, F226). The memory
budget (section 16) is also untouched by all of the above.

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
did (section 48). The risk that stays: on the first title a command-processor write into a read-only page ended in a
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

## After the first measurement (2026-11-13 19:14, README section 78)

B's floor on the walk route: **1,930 MiB** all-zero in every one of five scans over ten minutes [M]. The gate of
500 MiB is passed; option B is worth the work. GTT beyond the guest: the emulator's present side 245 MiB, desktop
clients about 100 (plasma-keyboard 76), the direct path's own buffers about 210.

### Step 2, prepared: the catcher for unnamed writers (tag ww412, `BC5_GUARD_WRITERS=1`, default off, log only)

`memfast/ww0412.inc`, `ww0412.cpp` (105,737 of 105,737 on the laptop), `mkww0412.py` after `mkkl0412.py`; in form 6
for candidate F. With the zero scan on, each scan journals per eager heap how many 2 MiB chunks turned non-zero
since the last scan, and how many of them a hint, a force or a packet operand had NAMED. The not-named count is an
upper bound of what option B cannot see today (a CPU write counts as not named). One walk arm with
`BC5_GUARD_WRITERS=1 BC5_DIRECT_ZEROSCAN_AT=... BC5_DIRECT_ZERO_NAMES=...` gives the number per heap. No risk: it
changes nothing but the journal.

### Step 3, the order of the heaps and what each arm risks (NOT prepared; each arm on his word)

How an arm is made: no new code. A heap leaves `BC5_DIRECT_EAGER_NAMES` for that arm, so it is imported by data;
K1r covers what nobody wrote; the bind hints and K1 at the filter import the write targets they can name. The risk
is the same in kind for every heap: a GPU write the host did not name lands on a read-only page. Then, with luck,
the ring reset succeeds and the game ends with a record that names the address and the buffer (exit 86); without
luck the reset fails (the first title, 11:32) and `bc5-gpu-watch` reboots the box after 60 s. The scripted arms use a
private save copy, so no save of his is at risk; his desktop session is.

| order | heap | zero in all scans / span, MiB | what it holds [I, from its name and what was seen] | expected writers | risk of a write fault |
|---|---|---|---|---|---|
| 1 | CommitIABufferAllocator | 274 / 2,736 | index and vertex data the CPU commits and the GPU reads | the CPU (seen by SEEK_DATA) | low: the mechanism's first proof on a real heap |
| 2 | RenderGpuWcLarge | 842 / 2,758 | render targets and GPU-written textures | binds (named by hints); shader writes through descriptors (not named) | high; the largest gain; go only after ww412's count for it |
| 3 | RenderGpuRwLarge | 204 / 414 | buffers both sides read and write | both | high |
| 4 | DynamicHeap, ComponentHeap, Physics | 182, 80, 116 | CPU heaps that also hold image descriptors (section 39) | the CPU | low to medium |
| 5 | AMM | 154 / 10,084 | the streaming pool, reached only through shaders | ww412 (section 81): all 37 chunks that turned non-zero were named | leave eager for now (the largest span, the smallest gain) |

My order differs from the top's proposal (RenderGpuWcLarge first) in one thing: one low-risk heap first, to learn
whether a by-data heap under K1r runs at all, before the heap where a fault is likely. If ww412 shows zero
not-named chunks for RenderGpuWcLarge on the walk route, it can go first.

### The lean session list (to write into the shortcut only on his word)

Stopped for the time of a play today: Plasma's shell (118 MiB of RAM). To add: `plasma-keyboard` (the virtual
keyboard, 76 MiB of GTT and its RAM; nobody types on it in a play), stopped and started again as the shell is.
Not measured: which unit or process owns it on his session and whether it restarts by itself.

### ww412's first numbers (2026-11-13 20:33, README section 81; the run ended in a GPU hang at 601 s, source not known)

Not named, of the chunks that turned non-zero in six minutes: RenderGpuWcLarge 11 of 107, RenderGpuRwLarge 23 of
29, CommitIABufferAllocator 11 of 18 (the CPU is its expected writer; the catcher cannot tell), AMM 0 of 37.
The order stands; RenderGpuRwLarge goes last of the three or gets a naming rule first. No step-3 arm before the
hang of section 81 is explained.

### Step 3 is prepared (2026-11-13 late evening, README section 82)

The maintainer agreed to the scripted arms. One switch per heap: `BC5_GUARD_BYDATA_NAMES` (tag bd412). The
catcher's CPU/GPU split: `BC5_GUARD_WRITERS=2` (tag wc412, the soft-dirty bit). Arms w0, b1-b4 in section 82.
Nothing runs before the hang of section 81 is explained.

### `BC5_GUARD_LAZY_BY_DATA`: verdict (2026-11-14, asked by the top; no run)

It stays as an arm, off: option B does not replace it, because B moves EAGER heaps to "by data + cover" to pin less, while this switch moves LAZY heaps to the same rule and pins more (+734 MiB the first title, +194 MiB second title, README section 72), for a fault (a GPU read of written lazy memory, kl412) that has not fired in four arms, two plays and the long walks of 2026-11-14 [M]; it goes on only if that named fault fires, or last, when B has recovered more than it costs and one rule for every heap is wanted [I].

## The GPU read fault in a lazy heap (n13P4, 2026-11-14 18:40): the cure proposed, no code (asked by the top; laptop)

**What happened** (README sections 98–99) [M]: a shader read two pages of the title's heap "FileSystem". The heap is
in `BC5_DIRECT_LAZY_NAMES`, so nothing of it is imported; its written chunks get no zero cover on purpose (kl412)
and stay unmapped. 24 of its 26 chunks were written. Once in 40 long walks, in the arm with the old file-read path.

**Three ways to cure it, by cost.**

| | what | pinned more | new code | catches n13P4 |
|---|---|---|---|---|
| 1 | `BC5_GUARD_LAZY_BY_DATA=1`: no heap is lazy, every written chunk is imported | +194 MiB measured (section 72; kl412 counts 120 written chunks under lazy views = at most 240 MiB) | none | yes |
| **2** | **"FileSystem" leaves `BC5_DIRECT_LAZY_NAMES`**: this one heap goes by data (written chunks imported, the rest under K1r's cover) | **at most 48 MiB** (24 written chunks of a 52 MiB heap) [I, from the record's mappings] | none: the list is a word (`direct_lazy_name()` reads it at start) | yes |
| 3 | import at the submit only what a descriptor names (dt412's idea, narrowed to addresses under lazy views) | a few MiB | yes | **not shown**: tl412 followed the user data of every compute dispatch of both timed-out buffers over two levels and found no FileSystem address; dt412 as written cost 5 flips/s |

**Proposal: 2.** It is the rule the fault record itself names (a heap the GPU reads cannot be lazy), it costs a
quarter of 1 at most, and it needs no walk over buffers at the submit. 3 would be the right shape only if the reader
were a descriptor the host can see before the submit, and the one record we have says it was not. 1 stays what it
is in this file: an arm, for the day a second lazy heap faults.

**What is not known and decides between "the title hands this to the GPU" and "a stray pointer"** [unknown]: the
reader. 3,780 words of the title's memory point into the one faulted chunk, most of them descriptor-like words
repeated in DynamicHeap and InitAllocator [M]; that many references look like data in use, not one stray pointer
[I]. The decode of the devcoredump's buffer at the CP's stop (about dword 1,280) names the draw; it is a read of
files on the box and waits for the end of the night series (no copy of them is on the laptop).

**What one arm has to measure** (after the reader is named, on the top's GO; not prepared):
- the words of tP (the arm that faulted) with "FileSystem" taken out of `BC5_DIRECT_LAZY_NAMES`; first check where
  the list is set for the second title on build U (a launcher word, or a forced row of `switch_defaults.hpp`: a
  forced row needs `KYTY_BC5_DIAG_UNFORCE` or a build);
- GTT and the pin at 420 s and 600 s against tA: the price, expected under +48 MiB;
- kl412's line: the written chunks under lazy views fall by FileSystem's (120 to about 96);
- no fault. With one fault in five tP walks, ten clean tP walks leave a chance of about one in nine that the fault
  is merely absent; so the arm shows the price at once and the cure only with numbers.

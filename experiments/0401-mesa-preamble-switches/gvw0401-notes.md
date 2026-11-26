# gvw: the given-up-wait side (exp 0401 series e9)

**Why.** `hang1954-0401.md`, "Deep analysis 2026-11-05 (after e8)" part (b) and "Box reads after the analysis", ranks one
cause of the draw-class hang first (Medium-High):
- In both crumbed draw-class hangs (19:54, r7all 06:40), the frame's acb reached the host after the hung meshlet dcb.
- The frame's dcbs wait (`WAIT_REG_MEM64 == 0`) on the acb's section labels 0x12004b??38. The host gave those waits up
  after `BC5_DIRECT_DCB_WAIT_MS` ("cpu-wait WAIT_REG_MEM64 at … on 0x…: GIVEN UP after … ms").
- Exp 0054's drop of indirect draws after a give-up covers only the same buffer: `t_wait_given_up` is reset in every
  `submit_split`, and `chain_given_up_at` works per segment.
- So the later meshlet dcb, which has no wait of its own, runs its fast-launch draws on lists the acb has not written
  for this frame.
- smp (e8) found none of the hung draws' anomalies in 14,502 completed pattern draws. Clusters of 3 or more given-up
  section labels within 0.5 s: 3 in the old journals (2 of them hang frames), 1 in 18 e8 arms.

gvw is the test build's given-up-wait side: two fixes and two catchers, each behind its own switch, default off. The
zero-skip side (tag zcb) is a separate edit of the same unit.

## 1. The switches

Unset, empty, `0` or `off` turn each off; anything else that does not parse is off, and the switch line says so. Each is
read once. The first `submit_split` (or flip) journals one line, `exp 0401 e9 (gvw): late producer wait …, unwaited fl
drop …, give-up journal …, unwaited meshlet sample …`, and prints it on stderr as `[bc5] …`.

| Switch | Kind | What it changes |
|---|---|---|
| `BC5_DIRECT_WAIT_LATE_PRODUCER_MS=<ms>` (1–2000) | fix | A game-thread cpu-wait of the `DCB_WAIT_MS` class that is about to be given up keeps waiting on the CPU, up to `<ms>` in all from the wait's start. It does so only when the label's writer can still come from another thread or queue (section 2). |
| `BC5_DIRECT_UNWAITED_FL_DROP=1` | fix | After a given-up wait on label L, the certainly fast-launch draws of every dcb submitted later are dropped until L meets the wait, or for 1 s. |
| `BC5_DIRECT_GIVEUP_JOURNAL=1` | catcher, CPU only | Each give-up journals its label, its buffer, the label's last known writer, its submission, and its writer's arrival. A fence timeout says whether the stuck job followed a give-up in its frame. |
| `BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED=1` | catcher, CPU only | At completion, smp's walk (both range models) on every pattern draw of a dcb submitted after a give-up in its frame. |

## 2. Which thread submits what: the late-producer rule

Line numbers are in the e8 input unit (bd181169).

**dcbs come from the title's own thread, inside its submit ioctl.**
- The gc ioctl cases 0xc0488131 (12208), 0xc0188132 (12233), 0xc0108102 (12266) and 0xc020810c (12283) call
  `submit_raw` / `submit_ib_packet` (12131–12179).
- Those call `Direct::submit` (7923), then `submit_split` (7974, 6532).
- That thread has `t_cq` 0, so `on_game_thread()` is true (10703). Its waits get `dcb_ns`, `BC5_DIRECT_DCB_WAIT_MS`,
  default 8 (6720–6721).

**acbs come only from `bc5-ring`.**
- `queue_consumer_thread` (1554) calls `set_source(1)` (1557). It polls each guest queue's doorbell page (1582–1583).
- It submits the ready slice as `"ring"` (1660). `Direct::submit` unwraps its IBs into `submit_split(…, "acb")` (7959).
- The doorbell is memory the title writes. The queue is registered at 0xc0408121 (12357); the "ding dong" ioctl
  0xc010811c (12433) is a stub. So the host never sees which title thread rings a queue.

**What the code cannot show, the box did.**
- F284 (exp 0224): no doorbell is written while the game thread sits in a cross-queue wait (0 writes in 957 ms of
  waits). At 7 of 13 give-ups, the writer was rung after the give-up by the Render Thread, which is the waiting thread.
  At 5 of 13, the consumer was held inside a compute buffer's own CPU wait.
- F282/F283: the labels are armed by the Render Thread and released by the GPU.
- F285 (exp 0225): at a 100-ms limit, every wait was served, and at 21 of 22 a compute job was on the compute ring when
  the wait ended.

**So the rule.** The host threads differ (game thread against `bc5-ring`), but the title's thread is one: an acb that is
not rung yet will only be rung by the thread now waiting in `submit_split`. Waiting for it is a self-deadlock until the
bound, so the switch does not wait then. It waits only when the writer is already on its way:
- **code 5:** a job on a ring writes the label with a value that meets the wait. This uses exp 0055's registry `g_plw`:
  the last pending write, on any ring, compared as `ring_will_satisfy` compares.
- **code 6:** an entry of a guest compute queue that the consumer has not taken yet writes it, and nothing unready
  stands ahead of it in that queue.
  - "Not taken": from where the consumer took last (`g_gvw_taken`, one relaxed store after each slice, the only line
    added to the consumer) to the doorbell's write pointer.
  - Before the consumer's first take, the scan starts at the read pointer it publishes behind the ring. That pointer
    lags by the whole post queue (the 375-ms slow post before 19:54), and would count a finished buffer of the frame
    before as a writer.
  - Unready, as `acb_ready` holds a buffer back: a wait whose label no earlier packet of the buffer writes, that is not
    met, and whose label has no pending write that meets it.

**It does not wait (the e8 path, and the cpu-wait line as before) when:**
- the run-123 cycle test fired, or the writer's queue first waits on a label this buffer writes in its part not yet
  submitted (**code 2**);
- no job on a ring writes the label and no queue holds a writer, so it is the same thread (**code 3**);
- the writer waits behind a wait whose label has no known writer, an entry could not be read (outside the host's
  mapping), a packet crosses the ring's end, or a cap was reached (**code 4**);
- the wait is not of the class: not a game-thread wait, or the device is wedged (**code 1**).

The decision is taken once, after the existing tries (the 2-ms cycle test, the `DCB_WAIT_MS` poll, and the piece split's
second poll).

## 3. What each switch does

**`BC5_DIRECT_WAIT_LATE_PRODUCER_MS`** (`gvw_late`, called from `submit_split` just before the "wait detail" line):
- One line for each decision: `gvw (exp 0401 e9): late producer of 0x… (dcb N dwords, its wait at i not met after X
  ms): <code's text>; <what was seen>; then <given up as without the switch | met: served late | still not met: given
  up at the bound> after Y ms`.
- When the wait is met: `cpu-wait WAIT_REG_MEM64 at i on 0x…: served late after Y ms (exp 0401 e9 gvw: …)`. The buffer
  then goes on as after any served wait: the wait is NOP-ed, and no `t_wait_given_up` is set.
- When it is not met: the existing line, with a suffix: `cpu-wait … on 0x…: GIVEN UP after Y ms (late-producer bound)`.
  The suffix appears only when the switch waited; unset, the line is byte for byte e8's.

**`BC5_DIRECT_UNWAITED_FL_DROP`** (needs exp 0404's plan of the dcbs' draws, `BC5_DIRECT_FL_CRUMBS=1`):
- Each give-up of the dcb class opens a window on its label: given up, a cycle, or the hold tail's give-up, but not a
  2-s timeout.
- A new give-up on the same label starts its window again.
- At each dcb's plan (`submit_now`, right after `fl_plan_buffer`), a window closes when its label meets the wait. This
  is checked only when the wait packet was copied whole. Otherwise it closes after 1 s.
- While a window is open, the plan's certainly fast-launch draws (exp 0404's `fl_class` 3, not already dropped by the
  ES skip) go to `FilterOptions::drop_offsets`, as exp 0054's drop and exp 0404's ES skip send theirs.
- The plan then holds them as `fl_scan` holds a draw its caller drops: not planned, no crumbs, no F1/F2 packet,
  counted in `host_dropped`. Maybe and unknown draws stay.
- The buffer whose wait was given up is submitted after the give-up, so its own fast-launch draws are dropped too,
  before the wait as after it. That is how exp 0054 treats the whole buffer.
- Lines:
  - `gvw (exp 0401 e9): unwaited fl drop: submit #n dcb: K certainly fast-launch draws dropped of T (M maybe or
    unknown kept); open give-ups: 0x… (give-up #g, age ms)` for each dcb with a drop;
  - `… unwaited fl drop window of give-up #g on 0x… closed: the label met | the 1-s bound after X ms; D draws dropped
    in B dcbs under it` when a window closes.

**`BC5_DIRECT_GIVEUP_JOURNAL`:**
- `gvw (exp 0401 e9): give-up #g: the wait on 0x… (GIVEN UP | CYCLE | TIMEOUT | the hold tail's GIVEN UP) of dcb N dwords
  at <buffer>, at i, after X ms, t s, flip f; late producer: …; the label's writer: a job on ring r writes it (pending) |
  no job on a ring writes it; last seen written by acb N dwords from bc5-ring | the game's thread, Z ms before`.
  - The last-writer registry is fed at every `submit_split`'s start with the switch on: each label a buffer writes, the
    buffer's kind and size, and the thread.
- `… give-up #g on 0x…: its buffer went to the GPU in submit #n dcb, X ms after the give-up`. Without a chain, this is
  this thread's give-ups of its current `submit_split`; with a chain, it is the segments marked `given_up` that hold the
  wait.
- `… give-up #g on 0x…: its writer arrived: acb N dwords from bc5-ring | a job on ring r writes it now | the label met,
  no writer seen | no writer seen and the label not met, X ms after the give-up, F flips later`. This is looked for at
  each `submit_split`'s start for up to 2 s.
- At a fence timeout, just before `timeout_probe` on both paths: `gvw (exp 0401 e9): at the timeout of submit #n dcb: it
  followed a given-up wait in its frame: yes | no; give-ups within 1 s before its submission: K: 0x… (give-up #g, class,
  X ms before, F flips between), …` (newest first, 8 named).
  - "Its frame" means no flip between the give-up and the job's submission, and at most 1 s before it. Every give-up
    within 1 s is listed with its flips, so both readings of "since the last flip or within 1 s" can be read off the
    line.
  - Flips come from one line in `SubmitEopFlip`.

**`BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED`:**
- Needs `BC5_DIRECT_FL_CRUMBS=1` and the draws' user data. `fl_plan_buffer` tracks those only with smp
  (`BC5_DIRECT_FL_MESHLET_SAMPLE`) or flx A1/A4/A5 on. Without them, the draw lines say "not walked", and the switch
  line says what is missing.
- At a dcb's submission (with crumbs), it is marked when a give-up of the dcb class lies in its frame.
- At its completion (beside `smp_sample`, on both paths), a marked job is walked, at most 16 jobs a second and 64 pattern
  draws each. This uses smp's `smp_text`, both range models, read a few ms after the fence.
- Each draw line is smp's line with another tag: `fl meshlet sample (exp 0401 e9 gvw): unwaited, completed: submit #n
  dcb op 24 at …`, and then smp's fields unchanged. Then a summary: `… unwaited: submit #n dcb completed: P pattern draws
  of D planned, W walked; after give-up #g on 0x… (X ms before its submission)`.
- Scratch `sampstat.py` sums these lines once its first regex reads `\(exp 0401 (?:e8 smp|e9 gvw)\)`. The tag
  "unwaited, completed" is then its own kind, beside smp's "completed".
- This is decisive without a hang:
  - r7all-like mismatches in these draws only (index ≥ count, loads past NUM_RECORDS, headers above 32 vertices)
    support cause (b)1;
  - consistent lists in them argue against it.
  - Either way, it is a CP-side reading after completion, not the shader's fetch (lessons R12, R13).

**Quiet mode.** Every line above survives `BC5_DIRECT_JOURNAL_QUIET=1`. `journal_quiet_kind` drops only its six kinds
("timing: t …", "timing: #…", "acb rest …", "submit #… OK rc 0 …"). gvw's lines start with `exp 0401 e9 (gvw): `,
`gvw (exp 0401 e9): `, `cpu-wait ` or `fl meshlet sample (exp 0401 e9 gvw): `. The timeout line has "at the timeout", so
quiet mode keeps it and writes its held lines before it. The CPU test runs every line kind, and every line the host side
wrote, through the real `journal_quiet_kind`.

## 4. The edit

`mkgvw0401.py` works on e8's unit bd181169 and gives a027c20abb23a83e588a2c5ec795b680. Every anchor occurs once, the
balance is kept outside comments and literals, the text is ASCII with LF ends, and the undo check is byte for byte. Its
own output and an unpinned input are refused. `PINNED` is one constant, for the caller to re-pin when it chains zcb →
gvw. No anchor lies in zcb's or p406's areas: the zero skip region, `scratch_fill`, the `fl_probe(` lines, the job's
`ib_copy`/`ran_copy`, `timeout_probe()`, the submit-time copy line, and `learned_*`.

- **Added:**
  - the pure block after smp's (`gvw_parse_*`, `gvw_meets`, `gvw_write_of`, `gvw_scan_ib`, `gvw_scan`,
    `gvw_late_decide`, the window, `gvw_fl_take`, the frames, the rate, the lines);
  - the host block after smp's;
  - the seams `bc5_gvw0401_*` after smp's.
- **Lines inserted:**
  - `g_gvw_taken` after `g_queues`, and one line after the consumer's `s.rptr = w_take`;
  - the forward declarations after `t_wait_given_up`;
  - one line after the hold tail's give-up line;
  - one at `submit_split`'s start;
  - the late wait (two lines) before the "wait detail" line, and the record after `if (!ok) t_wait_given_up = true;`;
  - in `submit_now`, one after `fl_plan_buffer` and one after the submission number;
  - one after each `smp_sample(` line, and one before each `timeout_probe(` timeout line;
  - one after `frame_profile_flip` in `SubmitEopFlip`, and its stub `gvw_flip() {}` in the non-direct branch.
- **One line changed:** the cpu-wait given-up line in `submit_split` gets `%s` and `gvw_bound_suffix(gvw_lp)`, which is
  `""` unless the switch waited.

## 5. Costs and risks

- **Off** (all four unset):
  - the switch line once;
  - one relaxed atomic store per slice the doorbell consumer takes;
  - a thread-local clear and a flag test at each `submit_split`, a call that returns at once at each give-up, two at each
    `submit_now`, and one at each completion, timeout and flip.
- **The late-producer wait:**
  - **Risk: a waiting game thread stalls the frame.** Every wait that the rule lets through can hold the title's thread
    up to `<ms>`.
  - A cluster of 3–5 given-up section labels in one frame could then cost up to 3–5 × `<ms>` when the writer does not
    come. That happens when the rule misjudges, for example a pending write that is overwritten, or a queued writer the
    title rewrites.
  - F285 saw served waits of 4.9–68.7 ms at a 100-ms limit. A first arm at 100–200 ms bounds the hitch near that.
  - Holding the thread also changes the order in which the title submits. F285 read the 8-ms give-up itself as what sets
    up the late-producer order. So a clean arm may come from fewer clusters, not from served waits: count both in the
    journal.
  - The scan runs on the game thread. It takes `g_plw_mutex` (at most 8192 entries) and copies `g_queues` under
    `g_mutex`. It reads at most 1024 queue entries and 2 Mi buffer dwords, through the host's mapping check. The ring
    memory and the doorbell page are read directly, as the consumer reads them.
  - The waiting game thread holds no lock that `bc5-ring` needs. The chain was flushed at the wait (`chain_flush(1)`).
- **The drop:**
  - **Risk: missing meshes, visual only,** for every dcb submitted while a window is open (until the label meets the
    wait, at most 1 s, about 30 frames).
  - It changes the GPU's work (fewer draws), so a clean arm with it alone is not proof of the mechanism (lessons R17,
    R18). Pair it with the two catchers.
  - "Maybe" and "unknown" draws are not dropped. A fast-launch draw of unknown state can still run on stale lists.
- **The give-up journal:**
  - with it on, one packet walk per buffer at `submit_split`'s start, and a writer map of at most 16384 labels (it is
    cleared when full);
  - about three lines per give-up (8–34 give-ups per e8 arm), and one line per fence timeout.
- **The unwaited sample:**
  - the completion thread's time: at most 16 jobs × 64 draws × 1,024 points × 2 models a second, and only in frames with
    a give-up;
  - about 1.5 KB per walked draw;
  - the same exposure as smp: guest memory read after completion (a rewrite makes it stale, an unmap between check and
    read would fault).

## 6. Checks (laptop, 2026-11-05)

`PY="/c/Program Files/Python314/python"`, `CXX="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"`
(clang 22.1.3, MSVC target). The scratch dir is `…\scratchpad\e9\gvw\`.

- **The script.** `"$PY" -I mkgvw0401.py <smp\out> <gvw\out>` prints `src/libs/bc5LleAgc.cpp
  a027c20abb23a83e588a2c5ec795b680`. On its own output it is refused: "the unit has the edit already". On a copy with one
  byte changed (acf7629e…) it is refused: "not the pinned input". The input is unchanged (bd181169).
- **The stand-in.** `mkstandin_gvw.py` builds it from the output unit, as smp's stand-in was built. It takes the real
  text of:
  - the exp 0404 block, with flx, smp and gvw, their host blocks and seams;
  - what gvw's host block uses from elsewhere: `SoftCp::compare`, `wait_satisfied`, `PendingLabelWrite`/`g_plw`,
    `cross_ring_waits`, `ring_will_satisfy`, `QueueReg`/`g_queues`/`g_gvw_taken`, `ChainSeg`/`Chain`,
    `t_wait_given_up` with the declarations, and `journal_quiet_kind` with cap's seam;
  - every line gvw (and smp) put elsewhere, in stub functions (syntax and types only).

  `"$CXX" -std=c++20 -Wall -Wextra -Werror -Wshadow standin_gvw.cpp gvw0401.cpp -o gvw0401.exe` builds clean.
  - `gvw0401 on` gives 325 of 325, `off` gives 173 of 173, and `unset` gives 173 of 173 (rc 0, three times each). With no
    argument it prints its usage and returns rc 2.
  - The cases:
    - the switches and constants;
    - the parse (unset, empty, 0, off, the range, junk);
    - the wait's comparison;
    - the decision table;
    - the scan on queues of the test's own: a free writer; a cycle; an unknown wait; a met wait; an earlier entry
      holding the queue; a non-meeting write; ATOMIC_MEM; a write before its own wait; a short WAIT_REG_MEM64; a
      timestamp select; a 32-bit mask; taken entries; a wrap; a packet across the end; unreadable entries; two queues;
      a ring-level packet; the 1024-entry cap;
    - the host's decision on the unit's real `g_plw`, `g_queues` and `g_gvw_taken`: pending, not meeting, rung,
      taken, cycle, unknown, M pending, M met, wedged, cycle, off, unreadable;
    - the real wait: served late after a writer thread's 10-ms spin, the 300-ms bound, same thread, cycle;
    - the drop window: met, a packet not copied whole, the bound, a restart;
    - the plan's drop;
    - the host's drop: the window, the dcb test, the drop line, closing at the label, a packet not copied whole, no
      window at a timeout;
    - the give-up journal: last writer, arrival by a buffer, label met, pending write, submissions with and without
      the thread's ids, acb/dcb;
    - frames and the timeout line (exact text);
    - the unwaited sample: marks, frame, kind, crumbs; smp's fields unchanged; both models; the 64-draw cap; the
      16-a-second cap (18 jobs, 16 walked, 2 refused); not walkable; a timeout takes the mark;
    - every line kind and every host line through the quiet filter.
  - Off and unset: no give-up kept, no window, no drop, no wait, no mark, and no line at all.
- **smp's and flx's tests on the same stand-in, unchanged.** `smp0401 on`/`off` give 61 of 61 each, as in
  `smp0401-notes.md`. `flx0401 on`/`off` give 173 of 173 and 172 of 172, as in `flx0401-notes.md`.
- **Mutants** (scratch `mutate_gvw.py`): 21 mutants of the stand-in, each built and run on, off and unset: 21 of 21
  caught (section 8).
- **sampstat.** A scratch copy with the one regex change sums a retagged line as its own kind, "unwaited, completed".
- **Timing on the laptop.** A 10-ms `sleep_for` took 70–90 ms there (the Windows timer). So the test's writer spins
  instead of sleeping, and the bound check allows one poll's overshoot (300–600 ms). On the box, the poll's 50-µs sleep
  is what `submit_split`'s own polls use.

## 7. Doubts and TODO(verify)

- TODO(verify): whether a RELEASE_MEM / EVENT_WRITE_EOP with a DATA_SEL other than 1 or 2 (a timestamp) can release a
  section label. gvw counts only 1 and 2 as label values, as `register_label_writes` does. F283 saw a job write a
  timestamp to a compute label now and then.
- F284's "the waiting thread rings the doorbell" rests on 13 give-ups in one run. If another title thread also rings
  compute queues, code 3 forgoes waits that would have been served. That is safe (e8's behaviour), but less of a fix.
- The rung-entry scan starts where the consumer took last. The slice the consumer is submitting right now counts as not
  taken, so a buffer inside its own 2-s CPU wait (F284's second kind) is judged by that wait's label. A wrong
  judgement there costs at most `<ms>`.
- A window closes on the label's value at a dcb's plan. A label met and armed again between two plans keeps the window
  open until the bound.
- The frame is "no flip between, at most 1 s". The timeout line lists every give-up within 1 s with its flips, so the
  looser reading can be read off it.
- Not run on the box. The unit was not compiled with the box's GCC: the stand-in is clang (MSVC target) on the laptop
  (lesson R02).

## 8. The mutants

All 21 are caught. Each was built with `-w` and run on, off and unset; a mutant counts as caught when a mode fails.
- Caught in every mode (the pure cases run in every mode):
  - a same-thread wait allowed (not rung: wait);
  - the run-123 cycle ignored;
  - a cycle in the writer's queue ignored;
  - a pending write ignored;
  - the consumer's take ignored;
  - a write that does not meet the wait counted;
  - a write after an unready wait counted as before it;
  - the suffix on every given-up line;
  - the drop window never cleared by its label;
  - its 1-s bound ignored;
  - maybe draws dropped too;
  - the frame ignoring flips;
  - the 16-a-second cap ignored;
  - a journal line blocked by the quiet filter;
  - the parse taking 2001.
- Caught on: the late bound ignored (four times it), a timeout's give-up opening a window, the 64-draw cap ignored, a
  timeout leaving the mark, a switch's value not read.
- Caught off and unset: give-ups kept with every switch off.

## Sources

- `hang1954-0401.md`: "r7all 06:40", "Deep analysis 2026-11-05 (after e8)" (b), "Box reads after the analysis".
- `docs/HANDOFF.md` F282, F283, F284, F285 (exps 0221, 0223, 0224, 0225).
- `backend/kytyplus-patches/README.md`: experiment 0054 (the drop after a given-up wait), experiment 0055 (ring-order
  waits and the label registry), `BC5_DIRECT_DCB_WAIT_MS`.
- `smp0401-notes.md` (the walk, its two range models), `flx0401-notes.md` (A1/A4/A5, F2), `fl0401-notes.md` (exp 0404's
  crumbs, the plan, the ES skip).
- The unit's own code at the lines cited in section 2.

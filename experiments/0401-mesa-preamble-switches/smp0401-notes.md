# smp: `BC5_DIRECT_FL_MESHLET_SAMPLE` (exp 0401 series e8)

**Why.** The r7all hang of 2026-11-05 06:40 (`hang1954-0401.md`, section "r7all 06:40 (e7 catchers)") is the 19:54
draw again. A4 read the hung draws' meshlet control path per point and found the same picture in all three:
- point 0 lands past an 8-entry object list;
- the load there reads 0, which selects the empty record 0 (flags 4, meshlet count 0, header base 0);
- the "headers" read through it are float data, 62–128 vertices against a programmed limit of 32.

At submit, 30 of 354 completed draws also hit that empty record. But no completed draw was ever walked per point, so
nobody knows whether completed draws look like the hung ones point by point. A4 runs only at a fence timeout. smp is
that control, as the analysis asked: CPU only, no packet, journal lines only.

**The switch.** `BC5_DIRECT_FL_MESHLET_SAMPLE=<s>`, whole seconds 1–3600. Unset, empty, `0` or `off` turn it off;
anything else is off, and the switch line says it does not parse. It needs `BC5_DIRECT_FL_CRUMBS=1` (the plans and
their draws come from exp 0404's crumbs); without the crumbs it does nothing, and its line says so. It is read once.
Its line is `exp 0401 e8 (smp): fl meshlet sample every N s, …` or `… off`.

**What it does.**
- *At a job's completion* (submit_now's sync path and the completion thread, beside flx's `fl_keep_done`):
  - at most once every N seconds (one global timer, `smp_take`), the job's pattern draws are walked;
  - the pattern ESes are 0x11d01345, 0x11d00f85 and 0x11d00f8d, as in A4;
  - at most 64 draws and 1,024 points per draw are walked, read through the host's mapping a few ms after the fence;
  - one line per draw (`fl meshlet sample (exp 0401 e8 smp): sample K, completed: submit #n dcb op 24 at …`), then
    a summary line.
- *At a fence timeout* (in `fl_probe`, where A4 runs): the same walk on the last done draw and on every draw issued and
  not done.
  - The last done draw is this buffer's if it has one, else the one `fl_keep_done` kept. With the switch on,
    `fl_keep_done` keeps it even without `BC5_DIRECT_FL_PROBE_STATE`.
  - With F2 (`BC5_DIRECT_FL_SERIAL`), the draws before the hung one complete inside the hung buffer, so this is a
    control from the same buffer and the same moment.
- *Every walk counts two range models.* TODO(verify) which one the hardware does; `hang1954-0401.md` has the gfx10
  V# OOB_SELECT question.
  - Model 0: a load past NUM_RECORDS reads 0. This is A4's reading; `flx0401-notes.md` marks the range check and the
    0 as TODO(verify).
  - Model 1: the load reads the memory there all the same.
- Each line has, per model:
  - followed / not readable / by the index path;
  - record flag bit 6 clear;
  - meshlet index ≥ count (first point);
  - the largest header's vertices and primitives;
  - above 32 vertices, above 64 primitives;
  - loads past NUM_RECORDS.
  It also has point 0's path in each model: object, record index, record address, flags, count, header base, meshlet,
  header.
- *What is tracked.* With the switch on, `fl_plan_buffer` tracks flx's state (`o.state`), as A1/A4/A5 do, so the
  draws carry their user data. That is the one cost when nothing is sampled. Off, nothing is tracked for it.

**The edit** (`mksmp0401.py`, on e7's main unit b010db09 → bd181169, every anchor once, balance kept, undo checked):
- `flx_mesh_point` and `flx_mesh_counts` get a defaulted `bool raw = false`, so every existing call is model 0
  unchanged. flx's own test passes on the e8 unit with its e7 counts: on 173 of 173, off 172 of 172.
- Added:
  - the pure block (`kSmpCap` 1024, `kSmpDraws` 64, `smp_parse`, `smp_due`, `smp_counts`, `smp_point`, `smp_text`);
  - the switch (`smp_period`, before flx's host block);
  - the host block (`smp_take`, `smp_walk`, `smp_sample`, `smp_at_timeout`);
  - the seams `bc5_smp0401_*`;
  - one line after each `fl_keep_done` call.
- Changed lines: `fl_keep_done`'s guard, `fl_plan_buffer`'s `o.state`, and `fl_probe`'s status-2 branch (one call).

**Costs and risks.**
- *Thread time.* A sample walks up to 64 × 1,024 points × 2 models, about a dozen guarded reads each. That runs on
  the thread that completed the job (the completion thread for queued jobs), so it can delay that job's completion
  signal by some ms once a period. Both arms of a pair carry it, so the pair's comparison holds; the arms use 30 s.
- *Reading guest memory after completion.* The title may free or rewrite a buffer once it sees the job complete.
  - A rewrite only makes the reading stale.
  - An unmap between `covered_sorted`'s check and the read would fault. The mapping snapshot is taken at the sample,
    and A4 at a timeout has the same exposure.
  - For a long-lived object table or meshlet buffer this is not expected, but it was not checked. It is a risk of
    any catcher that reads during play.
- *Journal size.* About 1.5 KB per walked draw; at 30 s and up to 64 draws, about 3 MB per 15-minute arm.

**Checks (laptop).**
- *The script* applies to b010db09 and gives bd1811690b685369194602027b61a2d5. It refuses its own output and an
  unpinned input (bcbdd308), and undoing its edits gives the input back byte for byte.
- *The stand-in* is a scratch TU from the output unit, like flx's (`mkstandin.py` with smp's end marker and the two new
  call lines). clang++ 22.1.3 (MSVC target) `-std=c++20 -Wall -Wextra -Werror -Wshadow` builds it clean, linked with
  `smp0401.cpp`:
  - `smp0401 on` gives 61 of 61, and `off` gives 61 of 61 (rc 0); with no argument it prints usage and returns rc 2.
  - The cases:
    - the switch and the constants;
    - the parse;
    - the pure timer and the unit's own;
    - model 0 against flx's walk, on six inputs;
    - model 1 against model 0: equal with nothing out of range; with an object table of 2 records (the scalar load)
      it walks as with 100; with an index buffer of 22 records (the typed load) it walks as with 64;
    - model 1 still refuses unreadable memory;
    - the line's text: the packet, memory now, the cap, no arguments, not a pattern ES, unknown user data, and model
      0's empty record against model 1's real one;
    - the real `fl_plan_buffer`: state tracked only with the switch on;
    - the real `smp_sample` with no device: no walk, no timer.
- *Mutants* (scratch `mutate.py`): 12 mutants of the stand-in, each built and run in both modes; all 12 caught:
  - model 1 ignored in the scalar load, and in the typed one;
  - raw not passed in the counts;
  - the state not tracked; the state always tracked;
  - 3601 accepted;
  - the timer not moved;
  - the switch value not read;
  - points and instances swapped;
  - the cap ignored;
  - point 0 of model 1 from model 0;
  - the sample without the device check.

**Sources.**
- `hang1954-0401.md` (section "r7all 06:40 (e7 catchers)", and A3 for the walk).
- `flx0401-notes.md` (the walk's layout, its TODO(verify)s, A4).
- Exp 0404's crumbs (`fl0401-notes.md`).

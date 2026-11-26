# 0253 — The night lake: what the depth-only writers read, clean against patched

**Question.**
- Exp 0251 (F310) closed the HTILE route. The night lake's patches are water-plane cells where the
  full-screen water draw fails its depth test against the depth that the GPU-driven depth-only
  writers leave each frame.
- Within a run, the writers' draw counts and indirect arguments did not separate patched from clean
  frames.
- What do the writers read — their user data, the buffers behind it, their per-draw records — and
  does any of it differ between clean and patched frames?

**Setup.**
- **Box and grant.** BC-250 dev box, 2026-10-24 00:00–00:12, granted by the top session ("GO" at
  00:01, after the maintainer's own tests): step A, then step B only if A named buffers, at most
  25 min, read-only. The box had been rebooted at 23:13 (boot bac6c7e0); `/var/home` at 70 %.
- **Step A** (00:00–00:03, no emulator) read the journals of runs H1 (exp 0248), W251a and W251b
  (exp 0251).
  - Those runs had `_PS` on four writers: PS 0x11d1d88300, 0x11d1dd6400, 0x11d090d900,
    0x11d0a98300. For each matched draw, patch 0001's journal holds the GS and PS user data ("bake ud")
    and the first 64 dwords of every buffer a user-data pair points at ("bake table").
  - `wr0253.py` lists the user-data slots, the descriptors and the varying dwords by window state
    (exp 0197's metric). It decodes descriptors as exp 0212's `desc0212.py` does, from Mesa's
    gfx10-rsrc.json @ 0866ae7.
  - `rec0253.py` gives each writer draw's inline V# record counts, by position in the frame.
  - `cells0253.py` collects the records of every draw with at most 16 records, i.e. the draws the
    64 journalled dwords show whole. It compares them between window states and runs, keyed with or
    without each record's second dword (`FULL=1`).
- **The writer list.** A check against exp 0245's committed unfiltered frame
  (`0245-…/raw/Z2.db.txt`) found that the four writers are not all of the depth-only work.
  - That frame had 45 colour-mask-0 draws writing the lake's depth buffer before the full-screen draw,
    from 9 pixel shaders: 0x11d373e600 ×17, 0x11d1d88300 ×12, 0x11d1dd6400 ×7, 0x11d0a98300 ×2,
    0x11d090d900 ×2, 0x11d1e2f300 ×2, and 0x11d28b0500, 0x11d1d33200, 0x11d29c8a00 ×1 each.
  - 88 more depth writers drew colour too.
- **Step B** (00:04–00:11) was therefore one journal-only run, W253a, with no memory reads.
  - It used exp 0251's private binary, `ab0253.sh` and `bench0253.sh` (exp 0251's, renamed).
  - The journal was `_EVERY=10`, with `_PS` on the full-screen draw and all nine depth-only shaders
    as prefixes (`11d373e`, `11d1e2f`, `11d28b0`, `11d1d33`, `11d29c8` for the five new ones, since
    pixel-shader addresses shift between runs, F305).
  - `args0253.py` is exp 0251's `args0251.py` with prefix matching.

**Result** (`raw/`).
- **Box state.**
  - W253a had no kernel fault, timeout or reset: the `.out` has 0 fault lines, the amdgpu dmesg count
    stayed at 123 since the reboot, and the stream has only routine lines.
  - The live saves' checksum was 1a39860996fdac5c before and after. It differs from the previous
    runs' f6475842373bf369 because the maintainer played in between; the bench uses its private copy.
  - The run wrote 79 MB of run directory and a 117 MB journal.
- **W253a's course.** Clean ts00–ts11 (1.4–1.6 %), short bursts at ts12 (19.0 %) and ts15
  (26.3 %), patched from ts19 to ts25 (19.0–30.7 %). That gives 48 clean, 59 mixed and 18 patched
  frames in 21 windows.
- **What the writers' GS user data hold.** User data 0–19 are five inline buffer descriptors, each
  four dwords: base low, then 0x00100011 (base high 0x11, STRIDE 16), NUM_RECORDS, and a format word.
  - **User data 0–3: a per-draw record buffer.** Its address changes nearly every draw (1039 distinct
    over 1092 draws of 0x11d1d88300 in W251a) and it holds 1–86 records of 16 bytes. Each record has a
    small flag word (1, 0x2040, 0x2050), a packed word, and two integral-valued floats in the tens.
    User data 12–15 hold a second per-draw buffer of one record.
  - **User data 4–7:** a 40-record buffer whose journalled floats look like a camera matrix
    (-0.696, 0.777, 2.285, 1.193, 0.453). They vary by about 1e-3 between frames, with the same
    ranges clean and patched.
  - **User data 8–11:** a 77-record buffer of per-frame screen constants: render width/8 and
    height/8, width/16 and height/16, and their reciprocals. These follow the dynamic render size
    (256×144 at 2048 to 416×234 at 3328), plus a per-frame counter.
  - **User data 16–19:** a 168-record buffer.
- **Within a run, the writers' inputs are the same in clean and patched frames.**
  - **Record counts.** At every position of a writer's draw in the frame, the NUM_RECORDS of every
    inline descriptor are the same in clean, mixed and patched frames. That holds in W251a and in
    W253a (`raw/*.rec.txt`). The few positions whose count varies (e.g. one 0x11d1dd6400 draw at
    75–85 records in W251a, one 0x11d1d33200 draw at 28–30 in W253a) vary the same way in both states.
  - **Records.** Every record that appears in all patched frames also appears in the clean frames,
    with or without each record's second dword:
    - W251a: 32 of 32 (79 of 79 with it);
    - W253a: 15 of 15 (35 of 35 with it).

    The reverse holds too (`raw/cells.txt`, `raw/cells-full.txt`, `raw/W253a.cells*.txt`).
  - **Writers per frame.** W253a's 15 depth writers per frame (1 × 0x11d090d900, 2 × 0x11d0a98300,
    1 × 0x11d1d33200, 7 × 0x11d1d88300, 4 × 0x11d1dd6400) are the same in its 47 clean and 36 patched
    frames (`raw/W253a.cmp.txt`).
- **The big 0x11d373e… group did not run under the filter.** In W253a only five of the nine
  depth-only shaders matched: the four known ones and 0x11d1d33200. 0x11d373e…, 0x11d1e2f…,
  0x11d28b0… and 0x11d29c8… matched no draw. They either did not run in this run's frames or ran at
  addresses outside the prefixes. A filtered journal cannot tell which.
- **Across runs, nothing compares.**
  - The writer lists differ: 0x11d1dd6400's draws per frame carry 2, 15, 8, 41, 75, ~80, 6 records
    in W251a against 7, 2, 41, 86, ~29, 6 in W251b, and per frame there are 22, 20, 18 and 15
    writers in W251a, H1, W251b and W253a.
  - The runs share no record at all (`raw/cells.txt`: every run's always-present records are absent
    from every other run). The record values are run-specific, e.g. relative to a per-load origin or
    holding IDs, so records cannot be matched across runs.

**Verdict.**
- **Within a run, the depth-only writers we can see draw the same thing in clean and patched frames.**
  That covers the same draws, the same record lists, the same camera and screen constants, and the
  same indirect arguments (F310). So the patch state is not chosen by what these writers are told to
  draw.
- Whatever differs must lie in:
  - the depth-only writers the filter missed (the 0x11d373e… group of 17 draws in exp 0245, absent
    or moved in W253a);
  - the geometry those records index (vertex data or heights fetched in the shader);
  - or the colour-writing depth draws.
- **Next:** one run with unfiltered journal windows repeated through the run (`_EVERY` with no
  `_PS`; exp 0245's Z2 journalled about 1400 draws and dispatches in a window of about four frames). That lists every depth writer of
  clean and patched frames in the same run, including the 0x11d373e… group under whatever address
  it has.
- Step B's memory reads were not needed: the journal holds the per-draw records itself. No reads
  were taken and no render was made.

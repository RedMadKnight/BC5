# 0403 — which compute program an acb expects when it dispatches before setting one

**Question.** When one of the second title's acbs dispatches before it sets its own compute program, which program and
compute state does it expect? Is either answer tried so far right: exp 0401's queue prefix (e.g. 0x0909939900, three
guest CPU crashes) or the program inherited on our ring (0x11d0287900, the hangs)? What would a correct fix behind a
switch look like?

Asked by the top session for the maintainer ("Zleć analizę osobnej sesji"), 2026-11-03. Analysis only: nothing was
built or run.

## Setup

Read-only box access on the top session's GO (2026-11-03, about 16:37–17:20). Every command was guarded by
`pgrep '^kyty_emulator'`; no emulator and no BOX-LOCK line were present. No writes on the box, so there is no
`~/bc5-work/exp0403`; the number is claimed only here.

Copied to a private laptop scratch outside git and not committed, because they hold the title's buffers:
- `~/bc5-data/captures/play-20261103-1607/gc/ib-timeout-01264477-dcb-17872.bin`
- `~/bc5-data/captures/play-20261103-1607/gc/ib-timeout-01264478-acb-5284.bin`
- `~/bc5-data/captures/devcoredump/20261103-163233-devcd1.txt` (copied, not needed in the end)
- `~/bc5-data/captures/play-20261103-0839/gc/ib-timeout-00432910-acb-484.bin` (the 08:49 hang)
- `~/bc5-data/captures/play-20261103-0839/gc/ib-timeout-00432913-dcb-37707.bin`

Read on the box with targeted greps:
- the last 4 MB of `play-20261103-1607/gc/direct.log` (probe lines);
- every `acb cs prefix (exp 0401)` line of `play-20261103-1359`, `-1403` and `-1542` (0, 1 and 67 lines);
- the `acb head` / `acb rest` lines of `-1542`;
- the submissions `#432900`–`#432912` of `play-20261103-0839`.

Walkers:
- `experiments/0381-second-title-non-f403-hangs/walk0381.py`: per-dispatch state the IB itself sets.
- `raw0403.py` (this directory): a packet list, structure and register values only.

Code read:
- `src/libs/bc5LleAgc.cpp` from KytyPlus `f266548` + patch 0001 @ main `a8324c8b`: `queue_consumer_thread`,
  `Direct::submit("ring")`, `submit_segment`, `acb_ready`, `cs_inherit_at`.
- Exp 0401's unit generator `experiments/0401-mesa-preamble-switches/mkunit0401.py` on branch
  `exp/0401-mesa-preamble-switches` @ `00ce5837`, functions `acb_cs_prefix` and `acb_cs_track`.
- The hang notes of 08:49 (`hangs-20261103-0849-0853.md`, side-session notes of the bvh session).

Register facts:
- `COMPUTE_DISPATCH_INITIATOR` fields come from `tools/bc5-agc/regdb/gfx10.json:11827-11842` (Mesa, MIT): bit 0
  COMPUTE_SHADER_EN, bit 5 USE_THREAD_DIMENSIONS, bit 6 ORDER_MODE, **bit 15 CS_W32_EN**.
- SH offsets are walk0381's: 0x20c/0x20d `COMPUTE_PGM_LO/HI`, 0x240+ `COMPUTE_USER_DATA_n`.

## Result

### 1. The 16:32 hang is not an inheriting acb

The probe lines of the 1607 play, in log order:
- 38672: `submit #1264478 acb 5284 dwords … TIMEOUT 2031.24 ms`
- 39666: the acb's summary, `acb #1264478 5284 dwords: … 166 dispatches (0 indirect)`
- 39955–39957: `dispatch op 15 at 11545: program 0x11d0287900, groups 1 x 1 x 1`
- 40249: the dcb's summary, `dcb #1264477 17872 dwords: … 73 dispatches`

**Dword 11545 lies inside the dcb, not the acb**, which has 5,284 dwords. In the dcb:
- dword 11526 is a `LOAD_SH_REG_INDEX` (0x63) with a pairs table of 10 entries at 0x11e0c4c010 (the program binding
  exp 0195 describes);
- 11531 sets user data;
- 11545 is a `DISPATCH_DIRECT` 1×1×1 with initiator 0x41.

So 0x11d0287900 there is the dcb's own program, loaded from its own table one packet earlier. It is not inherited.

The acb #1264478 sets `COMPUTE_PGM_LO` before every one of its 166 dispatches (0x11d04f80, 0x11d04f34, 0x11d04f25,
0x11d04f2f, 0x11d04f49, 0x11d04f36; wave32 ones 0x11d0376e, 0x11d0374f). It does not dispatch before setting a program.
**The 16:32 event is not evidence for program inheritance.** Which of the two timed-out buffers stalled is a separate
reading of the devcoredump, not done here.

### 2. The real inheriting acb (08:49, #432910): what it needs

Packet list of `ib-timeout-00432910-acb-484.bin`, the head:

| dw | packet | content |
|---|---|---|
| 0 | NOP | — |
| 2, 10 | ACQUIRE_MEM ×2 | — |
| 18 | SET_SH_REG 0x240 | `USER_DATA_0` = 0x87353120 |
| 21 | SET_BASE | 1, 0x11871ed000 |
| 25 | PFP_SYNC_ME | — |
| 27 | DISPATCH_INDIRECT | offset 0x420, **initiator 0x8061** |
| 30 | EVENT_WRITE 7 | — |
| 32 | ACQUIRE_MEM | — |
| 40 … 96 | the same block three more times | `USER_DATA_0` alternating 0x87353121 / 0x87353120 / 0x87353121 |
| 106–144 | first full binding | user data 0–15, `COMPUTE_PGM_LO` 0x09098ea0, RSRC1/2 (0x212/0x213), NUM_THREAD (0x207–0x209), … |
| 153 | DISPATCH_INDIRECT | +0x440, initiator 0x61 |

Further bindings, each before its own dispatch:
- 209: 0x0909968e, 1×1×1, initiator 0x61
- 252: 0x0909969d, initiator 0x61
- 293: 0x090996cc, initiator 0x41
- 355: 0x09098eb2, **+0x420, initiator 0x61**, `USER_DATA_2/3` = 0x1187353120

**What the head relies on.** Each of the four head dispatches writes only `USER_DATA_0` and the indirect base. Everything
else comes from earlier state:
- `COMPUTE_PGM_LO/HI` and `PGM_RSRC1/2/3`;
- `NUM_THREAD_X/Y/Z` (the initiator sets USE_THREAD_DIMENSIONS);
- `USER_DATA_1..15`, which must make (`USER_DATA_0`, `USER_DATA_1`) a usable pointer (0x8735312x with high 0x11, as at
  dword 355);
- the resource limits.

Initiator 0x8061 = COMPUTE_SHADER_EN | USE_THREAD_DIMENSIONS | ORDER_MODE | **CS_W32_EN**. The title emitted a wave32
dispatch, so its library believed the bound program was a wave32 program. None of the acb's own 0x0909… dispatches has
CS_W32_EN.

**Wave mode by program family, over the four dumps** (walk0381; `LOAD_*` tables in dcbs are not visible, so the dcb
rows are weaker):

| Dump | 0x0909… dispatches | 0x11d0… dispatches | Dispatches with no program in the buffer |
|---|---|---|---|
| acb #432910 (08:49) | 5, all W64 | — | 4, all **W32** (the head) |
| dcb #432913 (08:49) | — | 44, W64 | — |
| acb #1264478 (16:32) | — | 162 W64, 4 W32 | — |
| dcb #1264477 (16:32) | — | 52 W64, 21 W32 | — |

F536 (exp 0378) agrees: the two 0x0909… samples had initiator 0x61, and every 0x8041 sample had 32-thread groups.

### 3. Plausibility of the two answers

- **0x0909939900 (exp 0401's prefix), not plausible for an 08:49-type head.** Every observed 0x0909… program runs wave64,
  and the head is a wave32 dispatch.
  - Of 68 prefix lines (1403: 1, 1542: 67 sampled, first 64 then every 1024th), every one names queue 0 and a 0x0909…
    program: 0x0909939900 ×56, 0x090996cc00 ×5, and 0x0909873200, 0x090986ea00, 0x09098eb200, 0x0909936c00,
    0x090996e500, 0x0909969100.
  - Running a wave64 program with CS_W32_EN, with the previous acb's user data replayed under it, gives a shader that
    writes through pointers meant for another program. **That fits three guest CPU crashes on bad pointers better than a
    hang** (R21: a fit, not a proof).
  - The journal does not record the W32 bit of a prefixed part's dispatch, so this rests on the 08:49 buffer and F536,
    not on the prefixed parts themselves.
- **0x11d0287900 (inherited on our ring), not plausible either.** It is a dcb program: 16:32's dcb dispatches it with
  initiator 0x41 (wave64) after loading it itself. The 08:49 sampler saw it running the head's 19612 groups with 0x8061,
  i.e. a wave64 program run as wave32 over another buffer's pointers. That is the hang.
- **What would be right.** A wave32 program whose user data 0/1 is a pointer pair, last bound on the title's compute queue
  before this acb. It was not in any buffer we have; the previous acb on the queue was not dumped.
  - Exp 0401's tracker says that queue's last binding was a 0x0909… wave64 program, the same kind as #432910's own tail
    (0x09098eb2 at dword 355).
  - So either the tracker misses state the console's queue has, or the order of buffers on our queue 0 differs from the
    console's.

### 4. How our host tracks "the queue's program", and where it can differ from the console

- The guest queues are the driver's registered rings (ioctl 0xc0408121, F19/F20). `queue_consumer_thread` serves them in
  index order and sets `t_queue_idx` to the ring's index. Only `INDIRECT_BUFFER` targets go to the GPU, as "acb" jobs
  (`Direct::submit(…, "ring")`).
- Exp 0401's tracker `g_acb_cs` is keyed by `t_queue_idx` and fed by every acb part through `submit_segment`. Heads
  (`acb_ready`) and rests (the ring path) run on the ring thread with the right index. The key is per title queue, as
  intended.
- **Difference 1: non-IB packets on the guest ring never reach the GPU.** Ring packets other than `INDIRECT_BUFFER` go
  only to the soft CP (`execute(ring + off, len, 1)` in the posted completion). If the driver library writes compute
  state on the ring between IBs, our GPU and our tracker both miss it. The console's queue would have it.
  - F42 measured 8 ring dwords a frame per ring (exp 0018), two 4-dword packets, kinds not recorded.
  - Unverified for the second title: the `[bc5-q]` packet lines are `LOGF` and absent from these logs.
- **Difference 2: our splits.** 80,682 `acb rest` lines in the 1542 play: a head runs ahead of a wait, and the rest later
  gets the head's state replayed ("state prefix of 66 / 4 dwords").
  - With exp 0401 on, the rest then also gets the queue tracker's registers chained in front, after that replay.
  - If any other part of queue 0 was tracked between the head and the rest, the rest runs the other part's program.
  - The 08:49 submission shows the split: the journal sent #432910 as 444 dwords against 484 in the dump.
  - Several 0401 lines ("dispatches at 8", "at 15" in parts of 193–18,540 dwords) are likely such rests or segments, not
    title buffer heads.
- **Difference 3: one physical ring.** Without the prefix, an acb on our GFX ring (or compute ring 0) inherits whatever
  ran last on it: a dcb's program (08:49) or another queue's acb. The console keeps compute state per queue. This is
  the hang mechanism.

## Verdict

> **Corrected by the addendum below (18:16 catcher, 2026-11-03 evening).** "The inheriting head is a wave32 dispatch"
> generalised one buffer: all six inheriting heads of the 18:16 play are wave64. The per-wave-mode slots below have no
> basis on the console, which keeps one compute state per queue. The answer is the queue's state at the end of its
> previous buffer. See "Addendum: the 18:16 catcher" for the corrected verdict and the revised switch.

**Both answers are wrong, for the same reason.** The inheriting head is a wave32 dispatch. Our ring hands it a dcb's
wave64 program (hang), and exp 0401 hands it the queue tracker's 0x0909… wave64 program (bad pointers, crashes). The
16:32 hang is not an inheritance case at all (§1).

The program the head needs is not in any captured buffer. Two places the console's queue gets it that our host does not
see are open:
- compute state written on the guest ring outside IBs (difference 1);
- an earlier buffer on the queue whose order or split differs on our side (difference 2).

One play with the catcher below decides between them. Until then no prefix choice is evidence-based. The safe action for
an unmatched wave32 inheriting dispatch is to not run it.

### Proposed switch (design and sketch; not built, not run)

**`BC5_DIRECT_ACB_INHERIT`**: unset, empty or `0` is off. Exp 0401's `BC5_DIRECT_ACB_CS_PREFIX` stays as it is and is
mutually exclusive with this switch: on both, the new one wins and journals it.

1. **`journal`, the catcher. It changes no submission.**
   - Per guest queue, record the last full compute state at each dispatch, in two slots: W64 and W32 (by initiator
     bit 15). The state is SH 0x204–0x3ff from the existing `full_state::Tracker`, plus the initiator.
   - For a part that dispatches before it sets a program, journal (first 64, then every 1024th): the queue; the
     dispatch's initiator; its title offset; whether the part is a rest/segment (`from > 0`) or a buffer head; the
     queue's last W32 and W64 programs with their `USER_DATA_1..3`; the IB addresses of the queue's previous three ring
     entries.
   - Census of non-IB type-3 packets on each ring slice, by opcode and register range for `SET_SH_REG`, journalled once
     per queue and then every 1024th slice. This settles difference 1.
2. **`wave`: put in front only a state whose wave mode matches.**
   - The prefix is the queue's last state from the slot with the same CS_W32_EN as the inheriting dispatch.
   - It is never applied to a rest or segment (`from > 0`, or the ring path's `skip > 0`), whose own head the state
     prefix already replays. This removes difference 2's override.
   - With no matching slot, fall through to `skip`.
3. **`skip`: drop what cannot be matched.**
   - Each inheriting dispatch, up to the part's first program write, is rewritten to a type-3 NOP of the same length
     (header `0xC0001000 | ((len-2) << 16)`, opcode 0x10 per walk0381's table).
   - This loses the four passes (possible visual errors) but cannot run a wrong program. Journal each one.

Sketch against exp 0401's unit (`mkunit0401.py` series b; the anchors are the same `submit_segment` call it replaces):

```cpp
// BC5_DIRECT_ACB_INHERIT=journal|wave|skip (exp 0403), default off.
struct QueueCs { bc5::full_state::Tracker t; std::vector<uint32_t> w32, w64; uint64_t pgm32 = 0, pgm64 = 0; };
static std::map<int, QueueCs> g_q;                       // by t_queue_idx, under g_acb_cs_mutex
static void inherit_track(const uint32_t* p, uint32_t n) {  // after each acb part, like acb_cs_track
    auto& q = g_q[t_queue_idx];
    walk_dispatches(p, n, q.t, [&](uint32_t initiator) {   // apply packets up to each dispatch, then snapshot
        uint64_t pgm = 0; auto s = cs_prefix(q.t, &pgm);
        if (initiator & 0x8000u) { q.w32 = std::move(s); q.pgm32 = pgm; } else { q.w64 = std::move(s); q.pgm64 = pgm; }
    });
}
// in submit_segment, before submit_one(ib + from, to - from, "acb"):
const int at = cs_inherit_at(ib + from, to - from, *g_dev->sorted_mappings());
if (inherit_mode() != Off && at >= 0) {
    const uint32_t init = dispatch_initiator(ib + from + at);  // dword 4 (0x15) or dword 2 (0x16) of the packet
    journal_inherit(t_queue_idx, at, from, init, g_q[t_queue_idx]);
    if (inherit_mode() == Wave && from == 0 && !t_is_rest) {
        const auto& s = (init & 0x8000u) ? g_q[t_queue_idx].w32 : g_q[t_queue_idx].w64;
        if (!s.empty()) { chain_append(s.data(), uint32_t(s.size()), ib + from, to - from, "acb", false); goto tracked; }
    }
    if (inherit_mode() >= Wave) { auto copy = nop_inheriting_dispatches(ib + from, to - from);
                                  submit_one(keep(copy), uint32_t(copy.size()), "acb"); goto tracked; }
}
submit_one(ib + from, to - from, "acb");
tracked: inherit_track(ib + from, to - from);
```

The ring census goes in `Direct::submit`'s `kind == "ring"` loop, in the `else` of the `INDIRECT_BUFFER` test: count
`op` and, for 0x76, the register range, into a per-queue table journalled as above.

**Cost:**
- `journal`: one tracker walk per acb part (as exp 0401) and a few counters per ring slice.
- `wave`: ~60 dwords per matched inheriting part.
- `skip`: a copy of the part when it has an inheriting dispatch.

**How each outcome would read:**
- If the census shows `SET_SH_REG` 0x20c on the rings, difference 1 is the cause. The fix is then to submit the ring's
  own state packets with the IB (a separate design).
- If W32 slots exist and the 08:49-type heads get a 0x11d0… W32 program with a pointer pair in user data 0/1, `wave` is
  the candidate fix.
- If no W32 slot ever exists for queue 0, `skip` is the only safe mode, and the program's source stays open.

Per the fixes-first rule, all three modes go into one private build with the switch. A single play with `journal` +
`skip` gives both the census and a no-hang/no-crash reading for this class (R18: a clean play would not prove a fix).

## Files

- `raw0403.py`: the packet lister used above (structure and register values only; reads a dump given on the command
  line).
- No dumps, logs or walk outputs are committed. They hold the title's buffers; the paths above locate them on the box.

## Addendum: the 18:16 catcher (2026-11-03 evening)

**Question.** The `journal` mode of `BC5_DIRECT_ACB_INHERIT` ran in the 18:16 play: exp 0401 series e2, binary
`exp0401e2` 35ff82eb, unit 73e8e4e0, commit 14011b76. The play is read here to answer three questions:
1. What is the 2-dword part at 0xfe003a200 that comes before every inheriting head, and which buffer comes before each head?
2. With wave64 heads, which state is right?
3. How should the switch change?

**Setup.** Read-only `ssh bc250`, with the emulator guard before each command. Inputs:
- `~/bc5-data/captures/play-20261103-1816/gc/direct.log` (2,006,537 lines; grep `acb inherit (exp 0403)` and
  `acb inherit census (exp 0403)`);
- the catcher's code in `mkunit0401.py` at 14011b76;
- the two 2-dword acb timeout dumps of 10-30, read only with `od`:
  - `~/bc5-data/captures/play-20261030-0956/gc/ib-timeout-00033827-acb-2.bin`
  - `~/bc5-data/captures/play-20261030-1110/gc/ib-timeout-00033915-acb-2.bin`

The 18:16 play has no buffer dumps, and the title's memory is gone. Nothing is copied or committed.

### A1. The six lines

All six are head parts (offset 0) on queue 0, and all are wave64. They are every such part in the play: the journal's
count ends at 6, and it logs the first 64.

| t (s) | head part | inheriting dispatches (first at) | initiator | queue's last W64 program | "W32 slot" | previous title part |
|---|---|---|---|---|---|---|
| 470.359 | 21161 | 347 (17) | 0x61 | 0x0909936c00 | 0x11d03a0700 | 0x11e0ec00c0+32664 |
| 470.497 | 15796 | 641 (8) | 0x61 | 0x0909939700 | 0x11d039f000 | 0x11e0e600c0+32667 |
| 606.081 | 185 | 1 (16) | 0x41 | 0x0909969d00 | 0x090992af00, ud0 0x87260121 | 0x11e0ee00c0+32669 |
| 606.480 | 992 | 13 (8) | 0x41 | 0x0909873200 | 0x11d039f000 | 0x11e0f800c0+32670 |
| 609.220 | 1203 | 1 (8) | 0x61 | 0x090986ea00 | 0x11d039f000 | 0x11e0f800c0+32670 |
| 609.295 | 221 | 1 (16) | 0x61 | 0x0909968e00 | 0x090992af00, ud0 0x87266d21 | 0x11e0e800c0+32670 |

The catcher records `prev[0]` as the newest part (`acb_inherit_track` shifts `prev[k] = prev[k-1]`). Each line's
"previous parts" therefore reads, newest first: 0xfe003a200+2, a big title part, 0xfe003a200+2. On queue 0 the order
was: the 2-dword IB, the big part, the 2-dword IB again, then the inheriting head.

### A2. Question 1: 0xfe003a200 and the buffer before each head

**0xfe003a200 is the driver's own 2-dword IB.** It is not a title buffer.
- Exp 0011 met it in the first submit header: `cmds[1]` = IB at 0xfe003a200, 2 dwords, after the 150-dword state
  preamble at 0xfe0000000.
- Exp 0016 run 38 lists it among "the driver's own small compute IBs" on the guest rings.
- The address is the same in all six lines, before and after the big part. The play submitted 69,382 parts of 2 dwords.
- Contents: the two 2-dword acb dumps of 10-30 both read `c0001000 00000000`: a type-3 `NOP` with count 0, which is
  2 dwords. The dump files do not record their address, so "the same IB" is an inference. The 18:16 copy was not
  captured, and the driver could patch the slot.
- As a NOP it writes no register. It is neither a queue switch nor a state reset, whatever role it plays for the driver
  (a patchable slot or a marker).

**The buffer before each head is the rest of one recurring large acb on the same queue.**
- Each previous title part starts at 0x11e0??00c0 with 32664–32670 dwords. 0x…00c0 − 28 dwords = 0x…0050, so these are
  rests of ~32.7k-dword acbs at 0x11e0??0050 whose 28-dword head ran ahead of a wait.
- The 470.359 context shows it: `acb rest 28..32692 of 32692 dwords: state prefix of 4 dwords replayed first`, then the
  inherit line.
- So the ring order on queue 0 is: driver NOP, big acb (head, then rest), driver NOP, the inheriting acb. The heads take
  their program from the end of that big acb.

**Difference 1 (state written on the ring outside IBs) is ruled out for this play.**
- The census counts every non-IB type-3 packet on a guest ring slice, cumulatively per queue.
- After 239,617 ring slices, queue 0's last census line reads `non-IB type-3 packets: none`, and so does every other
  census line, on all 56 queues.

### A3. Question 2: which state the wave64 heads need

**The queue's register state at the end of the previous buffer on the same guest queue, whatever the wave mode.**
- A console compute queue (HQD) has one register state. It persists from IB to IB, and the driver's NOP IB does not
  change it. There is no per-wave-mode state, so the W32/W64 slots of 0403's design model nothing the console has.
- Here, that state is the tracker's live state (`InheritQueue::t`) after the big acb's rest.
- The "last W64" slot is that state only at the big acb's last wave64 dispatch. It misses any `SET_SH_REG` written after
  that dispatch.
- The journal printed slots, not the live state. So the program the heads should get is "0x0909… as in the W64 column,
  unless the big acb rebinds after its last dispatch". That is not measured.

**The state of our physical ring is the wrong reference in general.** In these six cases it may have matched the
queue's state by luck.
- The second-title launchers set `BC5_DIRECT_COMPUTE_RING=0` (`play-pkg-log.sh:76`, `play-pkg-quiet.sh:76`). Every
  guest compute queue's accepted acbs share compute ring 0. Refused ones (`acb_ring`, ADR 0009) go to the GFX ring
  with the dcbs.
- At 470.359 the last acb before the head was queue 0's own rest, submitted just before it. Queue 8's last acb was at
  470.352. So the physical ring most likely still held queue 0's state.
- That fits the play running 1,004 inheriting dispatches without a GPU hang (R21: a fit, not a proof). The ring order
  across queues was not journaled.

**What changes in the verdict.**
- *"The inheriting head is wave32" is withdrawn.* 08:49's head (#432910, initiator 0x8061) is one wave32 case; the six
  18:16 heads are wave64. The wave mode is the title's choice per dispatch, not a property of inheritance.
- *0x11d0287900 (a dcb's program, via the GFX ring) stays wrong.* It crosses from another queue.
- *Exp 0401's approach was the right shape.* Its idea, the queue tracker's state in front of an inheriting part, is
  what the console does. What 0403 §4 found wrong with it still holds:
  - it was also applied to rests and segments, on top of their replayed head state (difference 2);
  - nothing recorded where the tracked program came from.

  Its three guest CPU crashes are not attributed to the state itself. 0403 §3's wave-mode argument against it rested
  on the withdrawn wave32 claim.
- *A wave32 dispatch over a 0x0909… program happens in our runs.* In two lines (606.081, 609.295) the W32 slot holds
  0x090992af00 with user data 0 = 0x8726012x. That is the alternating …20/…21 pattern of 08:49's wave32 head.
  - Per Codex's caveat, the slot is "the state at the last bit-15 dispatch". It does not show whether that part bound
    0x090992af itself or inherited it.
  - So either the title dispatches 0x090992af with CS_W32_EN, or our queue order hands that dispatch a program the
    console would not.
  - The provenance rule below separates the two.
- *Open: why only 6 inheriting parts here, against thousands in 15:42 (exp 0401: 67 sampled lines, every 1024th).* A
  different scene, or a difference in which call sites count, is not settled.

### A4. Question 3: the switch, revised (design; not built)

`BC5_DIRECT_ACB_INHERIT` keeps `off | journal | skip`. `wave` is replaced by `queue`.

1. **Slot provenance (Codex's rule), in every mode that tracks.** Record a slot only at a dispatch that follows a
   `COMPUTE_PGM_LO` write in the same part (per `cs_inherit_at`'s rule for "may set").
   - The slot keys are the program address. Each program records the wave mode(s) the title itself used with it
     (`own32`, `own64` counters).
   - An inheriting dispatch never creates or updates a slot, so an inherited program cannot pose as a wave32 or wave64
     program.
2. **`journal`, extended.** Each inheriting part's line adds:
   - the part's title address (missing now);
   - the **live** program and `USER_DATA_0..3` from `InheritQueue::t`, not only the slots;
   - the provenance of the live program: the part and queue that last wrote it, and its own-wave counters;
   - `mismatch` when the inheriting initiator's bit 15 is a mode the title never used with that program;
   - the first two dwords of each previous part (to confirm the driver IB is a NOP);
   - whether compute ring 0's last submitted buffer came from the same guest queue. A thread-local "last queue" per
     physical ring is enough, and it measures difference 3 directly.
3. **`queue` (replaces `wave`).** A head (`from == 0`, not a rest or chain segment, so never on top of
   `state_prefix`'s replay) gets the live queue state in front: SH 0x204–0x3ff as `cs_prefix` builds it, which is exp
   0401's prefix restricted to heads.
   - If the dispatch is a `mismatch` (above), or the queue has no tracked program, its inheriting dispatches fall
     through to `skip` and are journaled.
4. **`skip`** is unchanged: the head's inheriting dispatches become NOPs of the same length through `drop_offsets`.

A sketch of the change to e2's unit (`mkunit0401.py --inherit`):

```cpp
struct ProgInfo { uint64_t own32 = 0, own64 = 0; int queue = -1; const uint32_t* part = nullptr; };
static std::map<uint64_t, ProgInfo> g_prog;          // by COMPUTE_PGM address, under g_inh_mutex
// acb_inherit_track: walk the part; remember whether COMPUTE_PGM_LO was written in it (cs_inherit_at's "may set"
// rule). At each dispatch: if written, g_prog[pgm].own32/own64++ (by bit 15) and snapshot; if not, no snapshot.
// acb_inherit_prefix, mode queue: if (head && !t_is_rest) {
//     uint64_t pgm; auto pre = cs_prefix(q.t, &pgm);   // live state, not a slot
//     const auto& pi = g_prog[pgm]; const bool w32 = init & 0x8000u;
//     if (pgm == 0 || (w32 ? pi.own32 : pi.own64) == 0) skip; else return pre; }
```

**How the next play would read.**
- `mismatch` never fires and `queue` plays clean: the queue-state prefix is the candidate fix. R18: a clean play is
  not proof.
- `mismatch` fires on the 0x8726012x-type wave32 dispatches: our order or splitting hands them a program the title
  never ran in wave32. The journal's ring-0 "same queue" field and the previous parts then show where the order
  differs.

Per the fixes-first rule, `queue` and the extended journal go into one private build with `skip` kept as the fallback.

### A5. Verdict of the addendum

- **The right state is the queue's own end state**: the guest queue's register state after its previous buffer. The
  driver's 2-dword NOP IB in between does not change it.
- **Neither wave mode nor the physical ring is the right reference.** 0403's wave32 claim and its per-wave-mode slots
  are withdrawn.
- **The 0x11d0287900 answer stays wrong.** The 0x0909… answer (exp 0401's prefix) is the right kind of state. It was
  applied in the wrong places (rests) and without provenance.
- **Difference 1 is ruled out by the census.** Differences 2 (splits) and 3 (one physical ring per kind) remain.
- **Next:** build `queue` plus provenance as in A4 into a private test build.

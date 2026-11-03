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

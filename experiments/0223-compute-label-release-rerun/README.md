# 0223 — the compute labels behind the given-up waits: CPU-armed, GPU-released, and mostly free at the give-up

**Question.** Exp 0221 (F282) left one point open. At a give-up the compute buffer that writes the
waited label B seemed already released (tcpW7, 4 give-ups in 88 s). Who writes its compute label C,
and is the delay then on the host: the doorbell consumer submitting a ready buffer late? This is the
clean rerun of exp 0221's v3 run, which stopped at 88 s.

**Setup.**
- Binary and scripts are exp 0221's v3, unchanged:
  - `patch0221b.py` / `patch_0221b.diff`, built at 2026-10-22 22:21 by `build0221b.py`, linked against
    the shared objects after exp 0222 (patch_0216 in the tree, listed in exp 0221's
    `raw/v3-linked-objects.txt`);
  - run by `run0221-v3b.sh` (here) with `V=v3`, analysed by exp 0221's `ana0221b.py` and
    `consumer0221.py`. `run0221-v3b.sh` is exp 0221's `run0221.sh` with two lines changed: the
    binary path and the tag tcpW7b.
- The one change: the binary is a hard link, `~/bc5-work/exp0221/v3/kyty_emulator`. With that file name
  its process name is `kyty_emulator`, so the bench's own `pgrep -x`, BOX-LOCK and 600-s stop work.
  tcpW7 had failed on that (exp 0221), and this run needed no stopper of its own.
- Run tcpW7b: `bench0201.sh tcpW7b 600`, attended, on the box supervisor's grant, 2026-10-22
  22:29–22:39.
  - Switches: `BC5_DIRECT_WAIT_TRACE=1`, `BC5_DIRECT_FLIP_TRACE=1`, `BC5_DIRECT_FLIP_TRACE_WP=1`, and
    `BC5_DIRECT_FLIP_TRACE_WP_LABELS=0x12004b37c8,0x12004b53c8,0x12004b4fc8,0x12004b77c8`: counting
    write breakpoints on these four compute labels in every thread, armed at the first give-up and kept.
  - The old launcher values pinned (`FLAT_APERTURE=0`, the old skip list; `AMM_PRT` absent, checked
    60 s in: `raw/tcpW7b-environ.txt`).
- Risk: the bench submits to `amdgpu` as every play does (a hang can take the machine down, F262); the
  diagnostic submits nothing.
- Not in this binary: a journal line for when the doorbell consumer takes each ring entry. The
  consumer's activity is seen only through the ends of its CPU waits ("timing: t … after that wait
  (acb …)", ms resolution).

**Result.** The full 600 s ran: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, same
boot, no new amdgpu line. 8 waits were given up (`raw/tcpW7b-ana0221b.txt`):

| # | t (s) | B | in flight at the give-up (cq0, cq1) | compute labels held back in the 50 ms before, value at the give-up | B flipped after the give-up |
| --- | --- | --- | --- | --- | --- |
| 1 | 7.1 | 0x12004b4838 | 0, 0 | 37c8: 0 | +44.7 ms |
| 2 | 125.3 | 0x12004b3c38 | 0, 1 | 37c8, 77c8, 53c8, 4bc8: all 0 | +1.8 ms |
| 3 | 126.8 | 0x12004b4c38 | 0, 0 | 4bc8, 37c8, 77c8, 53c8, 4fc8, 5fc8: all 0 | +13.5 ms |
| 4 | 133.8 | 0x12004b5438 | 2, 0 | 53c8, 4fc8, 4bc8, 37c8, 77c8: all 0 | +33.7 ms (*) |
| 5 | 139.5 | 0x12004b5438 | 0, 0 | 53c8, 4fc8: both 0 | +6.3 ms |
| 6 | 217.4 | 0x12004b3c38 | 0, 0 | 37c8, 57c8: 0; **4fc8: 0x9076d6d8c** | +50.6 ms |
| 7 | 262.3 | 0x12004b3c38 | 0, 0 | 37c8, 77c8, 53c8: 0; **4fc8: 0x9076d6d8c** | +15.8 ms |
| 8 | 282.7 | 0x12004b3c38 | 0, 0 | 37c8, 77c8, 53c8: 0; **4fc8: 0x9076d6d8c** | +13.6 ms |

(*) #4 has no change line for B, a race in the watcher: it reads the value, then checks the wait, and
the GPU wrote in between. The wait was satisfied at +33.7 ms, in the same poll as 0x12004b77c8's
release.

- **Compute labels are armed by the CPU and released by the GPU.**
  - Each change of a covered label after a give-up, 5 in all:
    - 0 → 0x9076d6d8c (#1 37c8, #4 77c8): a CPU write by the Render Thread, the thread that gave up.
    - 0x9076d6d8c → 0 (#1 37c8, #4 77c8, #6 4fc8): no CPU write counted, so a GPU write. 3 of 3.
  - In #3 the Render Thread armed 0x12004b53c8 within 0.5 ms after the give-up, as soon as our wait
    returned. That write was counted in the watch-start read (+0.53 ms). The first poll, at +1.15 ms,
    then saw the change and logged "no CPU write counted", but the write had already been counted. It
    is a CPU arming like the others; `ana0221b.py` lists it as unknown.
  - Between watches the Render Thread wrote each of the four labels about once a frame: 5,747–6,478
    writes each.
  - The host thread `bc5-cq0`, the game thread's completion thread, wrote them 25 times in all. Its only
    label writes are the timestamp rescale of `ts_collect()` addresses (RELEASE_MEM / EVENT_WRITE_EOP
    with DATA_SEL 3), which rewrites each value as `value * ts_scale()` even when the scale is 1. So
    some job wrote a timestamp to a compute label's address now and then. That is not explained here.
    It writes the same value back unless the scale differs from 1.
- **At 5 of 8 give-ups every compute label held back in the 50 ms before was already released**
  (#1–#5). With exp 0221's tcpW7 (4 of 4) that makes 9 of 12. At #6–#8, all on 0x12004b3c38,
  0x12004b4fc8 was still armed. At #6 the GPU released it in the same poll in which B flipped; at #7
  and #8 B flipped while it stayed armed.
- **At the flips, the compute label's release and B's flip come together:** #4 (77c8) and #6 (4fc8),
  in the same poll. One GPU job writes both, or two writes land within one poll (~70 µs).
- Jobs in flight at the give-up: 0 on both queues at 6 of 8 (#2: cq1 1; #4: cq0 2).
- The doorbell consumer (`raw/tcpW7b-consumer.txt`): at 6 of 8 give-ups a consumer wait ended between
  the give-up and B's flip. Only 2 flips came within 1 ms after one (−0.5, −0.2, 3.5, 4.3, 9.6,
  12.8 ms). In tcpW5 it was 6 of 13, in tcpW6 4 of 13.
- Frames, frozen view t 150–590 s: 29.0 flips/s, 19 seconds with a gap over 100 ms, none over 250 ms.
  Like tcpW6 (28.8, 17) and better than tcpW5 (26.0, 139), so the four sticky breakpoints cost nothing
  visible.

**Verdict.**
- **Settled: no label in the chain waits on a release by the title's CPU code.** The given-up label
  (F282: 11 of 11) and its compute labels (3 of 3 here) are both released by the GPU. The title's CPU
  code, in the Render Thread itself, only arms them, about once a frame. The release is GPU work.
- **The wait mostly comes from that GPU work not having been submitted yet.** At most give-ups
  nothing is in flight. The compute side is not stuck on a label of its own: 9 of 12 give-ups in
  tcpW7/W7b had every recently held-back compute label already released. Then, 2–50 ms later, a job
  runs that releases a compute label and B together.
- **Not settled: whose delay it is.** Two readings fit:
  - The host's doorbell consumer takes the ready compute buffer late. The flips follow the end of its
    waits within 1 ms at 12 of 34 give-ups in tcpW5, tcpW6 and tcpW7b (tcpW7: 1 of 4), a few times
    the chance rate.
  - Or the title has not rung the doorbell yet. Some of those submissions may come from the Render
    Thread after our wait returns, which would be a cycle the host creates around the title's own
    order. But exp 0207/0208 argue against that being common: with a 100-ms limit almost no give-ups
    remained, so the work arrived while that thread was still blocked.
- **Next, to settle it:** one more journal-only one-file build that logs, per ring entry, when the
  title's doorbell write was seen and when the consumer submitted that entry. Then one 600-s run.
  - If the gap is in the consumer, the fix is the consumer itself: submit ready buffers while another
    queue's CPU wait is on, behind a switch, A/B like the others.
  - If the doorbell comes late, the rule is the bounded wall-clock limit (100 ms, exps 0207/0208/0213),
    and no dynamic rule can see the writer any earlier.
- Unchanged: `g_unready_label` is no usable signal (F282). The bounded 100-ms limit stays the safe
  setting. Every wait given up here was satisfied within 61 ms of its start.

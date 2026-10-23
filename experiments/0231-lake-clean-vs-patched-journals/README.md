# 0231 — The night lake: a clean run against a patched one, from their journals

**Question.** Exp 0212 (F272) linked the end of the patchwork to the title lowering texture detail
clamps (`MIN_LOD`), and exp 0217 (F278) found no GPU feedback writer at the lake. The TCP
session's bench runs on the lake save left one clean run, tcpW6, and one patched run, tcpW5, both
with full direct journals. What did the title or the host do differently? Which traces did each run
actually have?

**Setup.**
- Offline, from yesterday's runs; read on the box at idle priority (`nice -n 19 ionice -c3`), no
  lock (2026-10-23 12:32–13:10, the box idle, granted by the top session).
- tcpW5 (21:22, the TCP session's exp 0219 binary) and tcpW6 (21:59, its exp 0221 binary): the
  exp 0194 bench on the lake save, old launcher values (`r-tcpW*/env.txt`). Both had
  `BC5_DIRECT_WAIT_TRACE=1` and `BC5_DIRECT_FLIP_TRACE=1`. **Neither had `KYTY_BC5_AMM_TRACE`**:
  their emulator logs (~316 KB) hold only audio-trace and fps-counter lines. So there is no APR or
  AMM record of what the title requested.
- `jr0231.py`: a direct journal binned by wall clock (journal time mapped through the file's mtime
  and its last `t`, as the TCP session does). It covers `direct merge` lines (ADR 0006's import of
  newly written direct memory: the nearest proxy for streamed data), learned windows, scratch
  windows, and frame times from `frame profile` lines.
- `corr0231.py`: for every frozen-view shot of a run, its patch share (exp 0197's `patch0197.py`)
  against the frame times in the 5 s before it (mean, max, frames over 300 ms). Run over the 18
  lake runs of 2026-10-22 that have journals (all have `frame profile` lines).

**Result** (`raw/tcpW5-timeline.txt`, `raw/tcpW6-timeline.txt`, `raw/corr-all.txt`,
`raw/corr-tcpW5-tcpW6-C4.txt`).
- **tcpW6 is not a patched-to-clean switch.** It was clean (1.4–1.8 %) in 12 of 13 shots, with one
  flash at ts01 (22:02:09, 15.5 %). tcpW5 was steadily patched, 16–24 %.
- **No streaming difference is visible in these journals.** In both frozen views the host imported
  no new direct memory (`direct merge`: 0 mappings moved, 86 BOs throughout) and applied no
  learned window. That is exp 0205's "the title requests nothing during the frozen view", seen
  from the host side.
- **Frame-time stalls are not the cause.**
  - tcpW5's patched view had recurring stalls of about 550 ms (2–4 frames over 300 ms in most
    5-s windows).
  - tcpW6's clean view had none except a 464-ms stall in the 5 s before its one patched shot.
  - Across all 18 runs, though, the two wholly clean runs A2 and A3 had the most stall windows (8
    and 9 of 13 shots). Patched runs mostly had 1–3, and tcpW2 none.
  - Of the nine clean↔patched switches, only three had a stall in the 5 s before (tcpW1b twice,
    and tcpW6's flash). B1b's four switches and B2's one did not.
  - Within C4, the patched shots had no stall, and its clean shots ts10–ts12 had stalls of
    450–530 ms.

**Verdict.**
- **Negative.** These two journals cannot show what the title requested: neither run had the AMM
  trace. The host-side proxies (direct-memory imports, learned windows) are idle in both frozen
  views, patched or clean. The frame-time contrast between tcpW5 and tcpW6 is incidental: across
  the 18 lake runs, stalls neither separate clean runs from patched ones nor consistently precede
  a switch.
- **Next:** the comparison needs runs that record the title's requests. Bench runs with
  `KYTY_BC5_AMM_TRACE=1` and exp 0212's table dumps (`DUMPS=1`), repeated until one switches clean
  or comes out clean. Then the AMM/APR requests in the seconds before a `MIN_LOD` drop can be set
  against a patched frozen view, where exp 0205 already saw none.

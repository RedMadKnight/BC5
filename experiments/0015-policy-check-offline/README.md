# 0015 — Phase 3 step (a): the submission policy applied offline to every captured buffer

**Question.** ADR 0005 replaces the roadmap's packet rewriter with a filter (pass / drop / rewrite)
over console-format command buffers. Before anything is submitted: how much of a real ASTRO BOT
stream would reach the BC-250's CP unchanged, what would be dropped, and is anything unreviewed?

**Setup.** No GPU. `backend/policy/pm4-policy.tsv` (the table of ADR 0005) and
`bc5-agc check` (new `tools/bc5-agc/src/policy.rs`, unit-tested) over the 718 buffers of run
`kytyplus-20260930-1055` (experiment 0012: 48 context-control, 374 graphics DCBs, 296 compute IBs;
137,181 packets). Results: [`raw/check-all.txt`](raw/check-all.txt), per kind
[`raw/check-dcb.txt`](raw/check-dcb.txt), [`raw/check-ib1.txt`](raw/check-ib1.txt),
[`raw/check-cc.txt`](raw/check-cc.txt).

**Result.**

| | packets | pass | rewrite | split | drop | dwords kept | dwords dropped |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | 137,181 | 75,957 | 34,670 | 148 | 26,406 | 714,756 (88.6 %) | 92,272 |
| graphics DCBs | 120,182 | 64,995 | 32,197 | 0 | 22,990 | 627,080 | 80,390 |
| compute IBs | 16,951 | 10,914 | 2,473 | 148 | 3,416 | 87,532 | 11,882 |
| context control | 48 | 48 | 0 | 0 | 0 | 144 | 0 |

- **Dropped**: `SET_UCONFIG_REG` to `SQ_THREAD_TRACE_USERDATA_2/3` 26,070 packets (Sony's per-packet
  markers; 98.7 % of everything dropped), `PREAMBLE_CNTL` 96, `GET_LOD_STATS` 92, and the 148
  single-register `SET_SH_REG` writes of the unresolved mm 0x2e80.
- **Rewritten**: every `RELEASE_MEM` (34,670; interrupt select cleared, events fired by the host
  after the fence) and the four `COMPUTE_STATIC_THREAD_MGMT_SE*` writes in each of the 148 compute
  preambles (CU mask AND).
- **Split**: 148 `SET_SH_REG` packets whose range 0x216–0x21a mixes the masks (rewrite) with
  `COMPUTE_TMPRING_SIZE` (pass).
- **Nothing unreviewed**: no packet fell through to the `default-op` drop, i.e. every opcode of the
  capture is named in the table, and no register outside the listed ones is dropped.

**Verdict.** Step (a) of ADR 0005 done: 88.6 % of the dwords of a real frame stream would go to
the CP verbatim, everything dropped is either a marker, a Sony-only opcode or the one unresolved
register, and the two rewrites are the ones the design calls for. The filter's job is small and
now measured; the backend implementation (`backend/src/policy.cpp` reading the same TSV) can pin
these numbers in a test. Next, step (b): the 150-dword state preamble alone, live, with the
maintainer's go-ahead.

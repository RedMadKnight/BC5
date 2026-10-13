# 0067 — a fast path for plain SET packets in the policy filter

**Question.** After 0061 the filter still costs the game's thread 1.7 ms a frame in ASTRO BOT's
later level. Most of its dwords are SET_SH_REG packets that pass unchanged, yet each one walks the
whole chain of per-packet checks: options, operands, labels, rewrites. Can such packets skip it?

**Setup.** `policy::filter` copies a plain SET packet (SET_CONFIG/CONTEXT/SH/UCONFIG_REG,
SET_SH_REG_INDEX) straight to the output when all of these hold:
- the table passes its opcode;
- the opcode is not in `extra_drop`;
- no `drop_offsets` are given;
- its register span touches no listed range (`span_listed`, 0061);
- the default register verdict is pass.

The full path would do the same and nothing else for such a packet.

Checks:
- ctest 40/40;
- `prepare-bench --hash` over the 60 dumped buffers of 0061: the same output with `mapped()`
  answering yes, no, and with the tracker.

**Result.**

| Offline (`--filter-only`, repeat 15) | before | after |
|---|---|---|
| 110,015-dword buffer, filter | 0.279 ms | 0.231 ms |
| 13 main buffers of 3 frames | 3.46 ms | 3.03–3.07 ms |

Live, run 296 (later level, the scene and window of 0061, `raw/run296.txt`):

| | run 295 (0066) | run 296 |
|---|---|---|
| filter, ms a frame | 1.72 | 1.45 |
| prepare | 3.0 | 2.8 |
| fps | 45.9 | 45.2 |

Run 296 shared the machine with an `rpm-ostree` transaction and `kcompactd`, on a disk at 100%.

**Verdict.** Passed for the filter: −0.27 ms a frame with the same output. The frame rate of the
one live run is within the noise of that run's conditions. A clean repeat is still to be done.

# 0041 — the second title's stale-argument dispatches, and the packet before its stops

**Question.** Experiment 0040 left two leads for the second title's stops: a `LOAD_SH_REG_INDEX`
the host drops in a large DCB shortly before two of them, and the GPU-driven dispatches the host
drops because their arguments look wrong when it reads them. What is the packet, and does running
the dropped dispatches change the stops?

**Setup.** As in 0040 (`run-pkg.sh` with the heavy probe on, `pkg-series.sh`, the compute-form
dispatches converted, program 0x909939900 skipped unless noted). New in the host:
`BC5_DIRECT_TRUST_DISPATCH=dcb` trusts the arguments only in graphics buffers (DCBs); `=1`, as
before, everywhere. Runs 96–97 had a temporary dump of the raw dwords of the first compute-form
dispatches (removed after). Runs 89–99, 2026-10-09 22:13–23:03; the runs that run new GPU work
(95, 98, 99) one at a time, watched, the build synced to disk first (D16). Run summaries in
`series-*.txt`.

**Result.**

| Run | Setting | Length | Faults | Failed | Note |
|---|---|---|---|---|---|
| 89–93 | as 0040 | 300 s each | none | 0 | 20.8–22.4 fps from 250 s |
| 94 | as 0040 | 240 s, exit 65 | 0x12cc002000 at 222 s | 12 | the probe's packet at 211 s; the title's thread then reads null + 0x45c4 |
| 95 | trust `dcb` | 240 s | 0x6165f896000 at 209 s | 12 | no frame from about 150 s to 209 s |
| 96–97 | dump | 60 s, 45 s | none | 0 | the compute-form dispatches' dwords |
| 98 | trust all | 240 s | 0xf8_13187f3000 | 12 | no compute dispatch dropped; few frames from about 150 s, a 14 s fence at 200 s |
| 99 | trust all, nothing skipped | 240 s | timeouts without a fault from 134 s | 75 | program 0x909939900 still hangs |

1. **The packet is a no-op.** Run 94 logged its dwords: `c0036300 00000000 00000000 80000000
   00000000`. That is `LOAD_SH_REG_INDEX` with index 0, address 0, register offset 0, the
   offset-and-data format bit and **zero dwords to load** (field layout: PAL
   `gfx9_plus_merged_f32_pfp_pm4_packets.h`, MIT; the RADV use in `radv_cmd_buffer.c` at Mesa
   0866ae7 loads 3 dwords from a direct address). Dropping it changes nothing. It sits at offset 8
   of a 22,312–22,526-dword DCB that came in runs 85 and 94 (both stopped) and in none of the five
   clean runs 89–93: a marker of a game state, not a cause.
2. **Runs 85 and 94 stopped alike.** About 211 s a new kind of frame DCB, about 11–14 s later a
   GPU fault a few pages past a 64 MiB boundary in the 0x12b0000000–0x12d0000000 range (0x12bb004000,
   0x12bc001000, 0x12c8003000, 0x12cc002000 over the day), where the guest has holes; each run
   faults just past the window the previous fault taught the learned file (0x12c6000000+96 MiB
   after run 85, then 0x12cc002000). Then the title's own thread reads address 0x45c4 at the same
   instruction (0x903f17926) with the same registers in both runs: a null pointer the title
   meets after the reset.
3. **The host drops about 2.2 million compute-form dispatches a run.** The journal's
   `indirect op 16 … base 0x0` lines are compute-form dispatches (`c0021600 d0571b00 00000011
   00008041`: arguments at 0x11d0571b00), not dispatches without a base. Their arguments read at
   submit time are stale (counts like 4294957269), so the sanity check of 0038/0039 drops nearly
   all of them (2,226,272 of 2,227,125 drops in run 93); in graphics buffers it drops about 850 a
   run.
4. **Running them does not get past the stops.** Trusting only the graphics buffers (run 95) gave
   about a minute without a frame, then a fault. Trusting all (run 98) dropped nothing; the title stopped
   presenting from about 150 s, the GPU hung at 200 s (a 14 s fence, reset) and faulted at a
   heap address with a junk top byte. Also running 0x909939900 (run 99) brought back its timeouts
   from 134 s, as in 0039.

**Verdict.** Failed for the fix, useful for the map: the dropped packet before the stops is a
no-op, and trusting the stale-looking arguments does not help while the dispatches that write
them stay as they are. The second title's stops coincide with a game state that comes after a
button press near 210 s, read memory the guest has holes in, and are followed by the title's own
null read. `BC5_DIRECT_TRUST_DISPATCH` stays off. Next: what the guest maps and unmaps in
0x12b0000000–0x12d0000000 around 211 s (the AMM trace), and what program 0x909939900 waits for.

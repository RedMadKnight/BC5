# 0040 — what the second title's remaining GPU faults point at

**Question.** With the compute IBs' indirect dispatches running (experiment 0039), the second
title still stops in about one run in three on a GPU fault, most often near 196–225 s. Run 84's
fault was a shader fetched from 0x800000000000 in a graphics DCB in which one packet had been
dropped as unmapped. Is that packet the cause, and what do the fault addresses have in common?

**Setup.** As in 0039 (`run-pkg.sh`, `pkg-series.sh`, compute-form dispatches on, program
0x909939900 skipped). The host gained a *heavy probe* (patch 0001, `bc5LleAgc.cpp`): a heavy
IB forces the direct-memory sync but the private-memory sync only every 100 ms to 1 s, so an
operand in memory the guest has just mapped may still be unmapped and its packet dropped. The
probe scans the packets' memory operands (`bc5::policy::memory_operands`); one in a page not yet
known to stay unmapped makes the sync urgent, and pages still unmapped after it are remembered
and journaled once (`heavy probe: …`, with the packet's dwords and the IB's `SET_BASE` packets
since run 87). It is on in these runs; after them it became opt-in (`BC5_DIRECT_HEAVY_PROBE=1`,
set by `run-pkg.sh`), because ASTRO BOT's regression run 152 showed it costs 6 ms a frame there
(the host's prepare 7.7 ms against 1.2, frames of 30 ms against 18). Runs 85–88, 2026-10-09 20:59–21:24,
watched. All of the day's fault lines (runs 61–88, from the journals' `timeout: fault` lines) are
in `faults-2026-10-09.txt`; the client of a fault is bits 9–16 of its status
(`(status >> 9) & 0xff`: 0x08 TCP, shader memory loads; 0x09 SQC, instruction fetch;
TODO(verify) the field against a public `GCVM_L2_PROTECTION_FAULT_STATUS` definition).

**Result.**

| Run | Length | Fault | Failed | fps from 250 s |
|---|---|---|---|---|
| 85 | 240 s, exit 65 | 0x12c8003000 at 225 s, then the title's own thread reads 0x45c4 (host access violation) | 12 | — |
| 86 | 600 s | 0x48d295c68000 at 571 s | 12 | 21.4 |
| 87 | stopped at 196 s | 0xd21296947000 | 12 | — |
| 88 | 300 s, recovered | 0x681296917000 | 12 | 22.2 |

1. The probe's one hit (run 85, 211 s): a 22,312-dword DCB with an op 0x63 packet
   (`LOAD_SH_REG_INDEX`) whose operand is address 0; the urgent sync does not map it, the
   packet is dropped. Run 85's fault follows 14 s later, run 84's (same DCB size class) at the
   same moment. In PAL's packet header for this opcode (`gfx9_plus_merged_f32_pfp_pm4_packets.h`,
   MIT) index 0 reads from a direct address and index 1 from an offset; the matching `SET_BASE`
   index 4 is named the load-register-index base. That an index-1 load is relative to that base
   here, and so its address 0 is an offset rather than a null pointer, is an inference from the
   names: TODO(verify). Runs 87–88 (dwords logged) did not meet the packet again.
2. Of the 74 lines, one is a timeout without a fault (address 0, status 0). Of the 73 fault
   addresses, 52 are pages of the title's own heaps
   (0x11_0000_0000–0x12_ffff_ffff) and 5 lie in the AMM window, all client TCP; one is the SQC
   fetch from 0x800000000000 (run 84). **Seven have a valid heap address in their low 40 bits and
   junk in bits 40–47** (0xd2_1296947000, 0x68_1296917000, 0xc0_12ce718000, 0xc0_12ce73a000,
   0xc0_1296a1c000, 0x20_1250e68000, 0x0a_1261113000); eight more are wild. The seven fit a GPU
   that ignores virtual-address bits from 40 up, so that the title's shaders can keep tags there:
   TODO(verify), no public source found yet. Mapping such aliases is not a fix (any of 256 tags per
   page); the BC-250 translates all 48 bits.
3. The learned-fault file takes these addresses as they are: each fault saves a 96 MiB scratch
   region at the junk address (`learned: fault 0xd21296947000 -> region 0xd21292000000`), so the
   file grows by unusable regions.

**Verdict.** Inconclusive. The faults are mostly loads from addresses the title's heaps contain or
contained, a few from addresses with junk above bit 40; the one dropped `LOAD_SH_REG_INDEX` sits
right before two of the stops but was seen once with its dwords unlogged. Next: catch that packet's
dwords and its `SET_BASE` (the probe now logs both), and look for a public statement of the PS5
GPU's virtual-address width before treating bits 40–47 as tags.

# 0400 — What the chip holds against what the stream wrote

**Status: failed 2026-11-01, took the box down, no audit data.** Written on the top session's GO, on the maintainer's word ("niech sesja wody zbierze teraz rejestry o ktore je prosilem").

**Question.** VGT_HS_OFFCHIP_PARAM was a value the title asked for and the chip never held (F785). Are there others? F787 listed what the title sends the system; this reads the chip.

**Setup.** One private run on the shared normal build f4e1a52e's objects (archive 75e30335, launcher 48a4dbf9), with `int/0388-j`'s backend plus `lake_probe` and its new `regaudit=1`. At up to eight jobs' first draws, from shot 30, the catcher reads back with `COPY_DATA` every register the stream has set (uconfig, SH, context) and the system's rings, and writes both values to `<tag>.audit.txt`. The offchip fix is on, as the launcher has it, so that register reads 0x1ff. `audit0400.py` names them from the regdb.

**How it will be read.** A register where the chip reads something else than the stream set, in most audits, is a candidate. Context registers are read while contexts roll, so a difference there needs a second look before it counts (TODO(verify)). A register set by nothing but reading non-zero says what the boot or the kernel left. This finds writes that don't arrive. It can't find a value the title asks for through a channel the host ignores: that is F787's list.

**Rules.** As exp 0398's. One run, then release. Nothing shared changes. `VGT_HS_OFFCHIP_PARAM` is as the launcher leaves it.

**Result.** Claim 23:05:11, private binary ef93a358, A1 launched about 23:07. At 23:12:33, about when shot 30 turned `regaudit=1` on: `ring gfx_0.0.0 timeout`, `Ring gfx_0.0.0 reset failed`, and `bc5-gpu-watch` crashed the kernel by design. The box rebooted by itself (boot 3b2105a8) and was back within a minute. Lock released at 23:13:50 with this run's token. Devcoredump `captures/devcoredump/20261101-231233-devcd1.txt`, private, not read yet. No `A1.audit.txt`, because the reads are written 256 jobs later. 2.9 GB of run data stay in `~/bc5-data/priv/exp0400`.

**Verdict.** The audit as built is unsafe. The cause is this run's own `COPY_DATA` reads of every register the stream had set, up to 4,096 of them including context registers and anything else written, which no earlier catcher did: `ureg` read six uconfig registers through dozens of runs without a fault. The dump and `arms.log` show it: regaudit went on at 23:12:31, the ring timed out 2 s later, and all 16 PFP and ME header slots read 0xc0044000, COPY_DATA, at PFP 0x283 and ME 0xd38, with only the CP busy. Which register hung the read is not known. Do not repeat it. A further read-back is a short named list of uconfig registers, added a few at a time.

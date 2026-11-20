# Exp 0438, step 3: what the host ignores around submission (patch bb04219b)

Read-only inventory, 2026-11-20. Code references:
- `A` = the tree unit `bc5LleAgc.cpp` of patch bb04219b (`experiments/0436-submit-unlock/bake/bc5LleAgc.cpp`, md5
  a62e8bf6…);
- `P` = `backend/kytyplus-patches/0001-bc5-lle-agc.patch`;
- `T` = `backend/policy/pm4-policy.tsv`;
- `PC` = `backend/src/policy.cpp`;
- `PH` = `backend/include/bc5/policy.hpp`.

**How it was made.** A read-only search agent collected the tables, and this session checked the rows it used.

**The console column.** It is what the code's own comments say, or TODO(verify). Every console fact here needs a
public source before it moves into `docs/` (hard rule 4).

## The model as the console has it, and where we differ

| | Console (as the title behaves; TODO(verify) against public AMD/console documentation) | Host today |
|---|---|---|
| the doorbell | the title writes the queue's write pointer; the CP/MEC sees it | polled by `bc5-ring`, which also prepares and submits; look gaps up to 1.6 s (c438) |
| `WAIT_REG_MEM` | decided by the CP at the packet | decided on the CPU at submit; game-thread waits polled and given up (F262), acb waits held in the queue (up to 10 s) or CPU-waited (2 s) |
| the submit call | returns at once | can block in waits, flushes, back-pressure (24 jobs), the device mutex |

## Table 1: guest calls around submission

| Call / ioctl | Where | Host | Console (code comment / TODO) |
|---|---|---|---|
| libkernel `ioctl` on `/dev/gc` | A:16750-16772 | routed to `gc_ioctl` | – |
| 0xc004812e capability query | A:16414-16419 | two u16 zeros | "RPCSX answers 0, 0" |
| 0xc008811b submit-done flag page | A:16420-16436 | a zeroed 16 KiB page, written only by 0xc020810c | TODO(verify) |
| 0xc0488131 submit header (cc + 3 IBs) | A:16437-16461 | implemented, one chain | – |
| 0xc0188132 submit list | A:16462-16494 | implemented, one chain (loops count/2) | – |
| 0xc0108102 submit | A:16495-16511 | implemented | – |
| 0xc020810c submit + write EOP | A:16512-16540 | submits, stores the EOP value in the flag page; **no EOP event** (G6 hard-off, A:745); `wait_flag` ignored | "where the console writes the EOP value is not known"; RPCSX raises event 0x40 and waits idle (not ported) |
| 0xc0088101 switch buffer | A:16541 | **returns 0, no effect** | TODO(verify) |
| 0xc0048116 "submit done" | A:16543-16580 | counted; `chain_observe()` submits held chains; no wait | RPCSX's wait is commented out: TODO(verify) |
| 0xc0048117 "wait idle" | A:16544-16579 | counted; `chain_observe()`; waits for the completion queues, at most 2 s, only when asynchronous | RPCSX waits for idle |
| 0xc010810b CU masks | A:16581-16585 | all CUs | – |
| 0xc0408121 queue registration | A:16586-16612 | recorded; starts `bc5-ring`; output zeros | "layout a working hypothesis" |
| **doorbell write** (memory, not an ioctl) | A:1546-1720 | **polled** (200 µs sleep per pass, `kRingPollUs`, P:5225; the "1 kHz" comment at A:1549 is stale) | the CP/MEC reacts to the write |
| **0xc010811c "ding dong for workload"** | A:16669-16674 | **logs and returns 0, no effect** | "(compute queue kick)", "(TODO)" |
| 0xc030810d map compute queue | A:16650-16668 | **logs, returns 0** ("not wired") | TODO(verify) |
| 0xc0848119 stats report control | A:16644-16649 | logs, returns 0 | – |
| any other `/dev/gc` request | A:16675-16699 | zero-filled, returns 0, first 16 logged | – |
| `kevent` EVFILT_GRAPHICS | A:16959-17005 | registered with the soft CP; waits call `chain_observe()` | – |
| EOP event delivery | A:635-667 | from the soft CP's replay of RELEASE_MEM/EOP with INT_SEL ≠ 0, after the fence; graphics ident 0x40 (+0), compute both 0x48 and 0x46 | "which one is the compute EOP is not known" |
| VideoOut SubmitEopFlip | A:17275-17389 | a **CPU flip**: drain (or deferred with FLIP_DEFER), then flip; the flip label cleared by the host | "TODO(bc5): the EOP part" |
| flip-label waits in a DCB | A:9990-10022 | served on the CPU up to 100 ms, then **the host clears the label** | cleared by VideoOut after the flip |
| HLE sceAgcDriver* (TF ring, HS offchip) | P:32295-32330 | implemented but **not reached**: both titles use their own driver (LLE), whose calls go to `/dev/gc` | – |

## Table 2: PM4 type-3 packets treated specially

`default-op drop` (T:11): an opcode with no row in T is NOP-ed in place (PC:573-589).

| Op | Name | Host | Console note in code |
|---|---|---|---|
| 0x10 | NOP | passed; the custom-NOP count is off (G8 hard-off) | console custom NOPs carry sub-codes (KytyPS5, AnyPS5) |
| 0x12 | CLEAR_STATE | cmd 1/2 rewritten to 0; context push/pop emulated (state_stack) | "cmd 1/2: TODO(verify)" |
| 0x28 | CONTEXT_CONTROL | rewritten to 0x80000000/0x80000000 | "the console's values hung the BC-250" |
| 0x47 | EVENT_WRITE_EOP | INT_SEL cleared; the soft CP replays it and fires the event | – |
| 0x49 | RELEASE_MEM | INT_SEL cleared; CS_DONE/6 with no data → BOTTOM_OF_PIPE_TS/5 on GFX; DATA_SEL 3 → 100 MHz timestamp in the soft CP | "the GFX ring never completes the former" |
| 0x16 | DISPATCH_INDIRECT | MEC form rewritten to GFX form or dropped; NOP-ed on unmapped/absurd args, skip lists, RT off, inherit | – |
| 0x24/0x2c/0x38 | indirect draws | dropped unless INDIRECT_DRAWS (the second title: `multi`); **dropped after a given-up wait** | – |
| 0x3c/0x93 | WAIT_REG_MEM(64) | **dropped** unless written earlier in the IB or kept by ring order; decided on the CPU before submit (8 ms game thread, 2 s acb), or the IB split | the CP decides it at the packet |
| 0x37 | WRITE_DATA | to registers **dropped**; GDS dropped or redirected | "console driver's thread-trace markers" |
| 0x50 | DMA_DATA | passed (GDS handled); **not executed by the soft CP** | – |
| 0x4a | PREAMBLE_CNTL | **dropped** | "not emitted by Mesa, dropped until proven harmless" |
| 0x8e | GET_LOD_STATS | **dropped** | "unknown to the BC-250's CP firmware" |
| 0x51 | CONTEXT_REG_RMW | **dropped, counted only** | "AnyPS5 runs it as a masked register write"; a pass row needs the maintainer's word |
| 0x39 | MEM_SEMAPHORE | GPU: dropped; soft CP: signal executed, **wait counted only, never held** | "a signal's mailbox never stalls" |
| 0x45 | COND_WRITE | GPU: dropped; soft CP: memory form executed, register forms counted | TODO(verify) mask |
| 0x59 | REWIND | GPU: dropped; soft CP: skipped | "with VALID clear the console's parser stops until the CPU sets the bit" |
| 0x22 | COND_EXEC | passed; executed by the soft CP | – |
| 0x1e/0x40 | ATOMIC_MEM/COPY_DATA | passed; replayed by the soft CP if the GPU did not run them | – |
| 0x3f/0x33 | INDIRECT_BUFFER | passed when mapped | – |
| graphics-only ops | on compute rings | NOP-ed; the IB refused from compute rings | ADR 0009 |
| SET_* 0x2e80, 0xc342-0xc343 | regs | **dropped** ("Sony per-packet markers") | – |
| type-0 / type-1 | – | dropped | – |
| any unlisted op | – | **dropped** (`default-op drop`) | "only the console's firmware knows" |

## Per-run counts

The journal counters that report these:
- `exp 0405 gpu: …` (MEM_SEMAPHORE, REWIND, policy drops, custom NOPs, submit-EOP, COND_WRITE, wait idle): every
  10 s, normal build only. REWIND, policy drops, custom NOPs and submit-EOP are always 0 in this build: their
  catchers are hard-off.
- `[bc5] ports pack 1: CONTEXT_REG_RMW (0x51) seen N, dropped M` (stderr).
- `gc ioctl wait idle|submit done: N calls`.
- `[bc5-gc] ding dong … (TODO)` on every call.
- `[bc5-cp] … skipped by opcode` (not in journal=min or lean).

The counts per run were not read for this table: it would mean reading the C3/A runs' logs. That is one short box read
on the top session's GO.

## What stands out for the console model

- **The doorbell is polled**, and the title's own kick (0xc010811c "ding dong") is ignored. On the console the kick
  is presumably what makes the MEC look (TODO(verify)). It is a natural event source for the watcher of the ADR
  draft: a cheap, exact signal that the title has rung a queue.
- **Every `WAIT_REG_MEM` is decided on the CPU or dropped.** None is decided by the CP unless the host proves its
  writer is already on a ring.
- **Flip labels are cleared by the host** after a CPU flip, not by an EOP-driven flip.
- **Opcodes dropped by default:** 0x51, MEM_SEMAPHORE waits and REWIND are dropped or only counted. Any of them in a
  hot path would change the title's ordering.

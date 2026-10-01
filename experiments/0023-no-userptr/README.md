# 0023 — No userptr in a draw's BO list: private guest memory as dma-bufs too

**Question.** A submission with draws lists every mapping and costs 2.17 ms in the ioctl, eight
times a frame; the cost is the kernel's page walk over the userptr BOs that still cover 370 MiB
of anonymous guest memory (HANDOFF F54). Can that memory reach the GPU the way the direct memory
does (ADR 0006), so that a draw's list holds imports only — and is the frame 17 ms shorter for
it?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`, GTT 13,312 MiB (D12).
Track-B host with patch 0001; run command of experiment 0022 (run 106).

What the 370 MiB were (run 106's journal): the game's executable image, 250 MiB in five pieces;
thread stacks, 103 MiB; other modules and the emulator's runtime areas, 14 MiB. All of it is
handed out by one function of KytyPlus (`GuestAddressSpace::Commit`), as anonymous pages.

**Change.**

- KytyPlus (patch 0001, with `KYTY_BC5_DMABUF=1`): `Commit` maps private guest memory from a
  second sealed memfd, at the file offset equal to the guest address, instead of making
  anonymous pages accessible. Nothing is punched out of that file on release, so an import never
  goes stale; a range committed again is zeroed where the file still holds data.
  `KYTY_BC5_NO_PRIVATE_FILE=1` keeps the anonymous pages.
- Host: the direct-memory mapper (chunks, merged imports, forced windows, fast path) is one
  state per file and runs for both; private regions are its views with offset = address. Thread
  stacks are imported only where a hint or a learned fault asks (`BC5_DIRECT_STACKS=1` imports
  them like the rest). The walk over anonymous VMAs stays as a once-a-second check.

**Result.**

*Map-only* (60 s, no submission): the game starts as before (the same 28 flips); the journal
shows 127 private regions, 15 imports, 286 MiB pinned, and not one userptr mapping.

**Verdict.** Open: the GPU run is to come.

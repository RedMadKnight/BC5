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

*Run 107* (20:31, GPU, 382 s, the maintainer at the controller; capture
`kytyplus-20261001-2031`, `raw/run107-summary.txt`): **246,794 submissions, none failed, no
fault, no `-EFAULT`, 16,423 flips; the title screen at 46.9 fps and the opening cutscene at
41.2 fps** (27 and 24 in runs 102–106). The picture is the same — intro, title, loading,
cutscene, the desert scene. No userptr mapping exists during the run; a draw's list has 189 BOs
and its ioctl takes 0.06 ms.

| A frame, ms | title, run 102 | title, run 107 | cutscene, run 104 | cutscene, run 107 |
|---|---|---|---|---|
| mapping sync, hints | 1.3 | 1.1 | 1.8 | 1.2 |
| device: prepare, list | 1.2 | 1.1 | 1.9 | 1.4 |
| device: submission ioctl | 15.0 | 1.0 | 17.7 | 1.5 |
| device: waiting for the fence (GPU) | 16.3 | 14.5 | 17.3 | 16.5 |
| the rest | 3.0 | 3.6 | 2.9 | 3.7 |
| **frame** | **36.8** | **21.3** | **41.6** | **24.3** |

The run ends at 382 s, in the desert scene: the controller dropped off the USB bus twice in
its last 20 s and the maintainer stopped it. With `SDL_JOYSTICK_DISABLE_UDEV=1` the emulator
did see the controller come back both times (it had not, in its container, in run 101).

**Verdict (2026-10-01, 20:40).** Passed. With private guest memory in a file and imported like
the direct memory, nothing in a submission is walked page by page any more: 14–16 ms a frame
gone, 47 fps at the title screen and 41 in the cutscene. Two thirds of a frame is now the GPU's
own work, waited for; the host's share is about 7 ms.

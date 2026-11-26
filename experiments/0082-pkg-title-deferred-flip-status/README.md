# 0082 — counting deferred flips as pending does not stop the second title's text race

**Question.** Experiment 0081 tied the second title's lost letters to the deferred flip
(`BC5_DIRECT_FLIP_DEFER`). The title polls `sceVideoOutIsFlipPending` / the flip status:
"flipPendingNum = 1" is repeated hundreds of times in its log. A deferred flip reaches KytyPlus's
flip queue only once the frame's jobs are done. Does the race go away if the flip status counts
the deferred flips as pending from the moment they are deferred?

**Setup.** `flipcount_host.py` (patch to the KytyPlus tree, since reverted):
- `FlipQueue::GetFlipStatus` adds a counter of deferred flips not yet submitted;
- the counter is incremented when the host defers a flip and decremented right after
  `VideoOutSubmitFlip`.

Run 334 (`run334.sh`, 2026-10-14 11:22): run 327's settings with the deferral on.

**Result.**
- The dialog's letters are missing as before, and the menu title reads "IN T AL SETUP"; no change
  from run 327.
- flipPendingNum seen by the title: 16,276 × 1 and 2,995 × 0 (run 327: 15,165 × 1, 4,672 × 0).
- 24.3 fps.

**Verdict.** Failed: the flip status is not what the title uses to protect the data it rewrites.
The change was reverted.

- Undeferred flips work because the host drains every job at the flip, so the title's thread
  cannot run ahead of the GPU.
- Which completion the title waits on is still open. Candidates:
  - the `RELEASE_MEM` of its 84-dword per-frame buffer, which writes to the flip-label page
    outside guest memory and is dropped by the filter (experiment 0080);
  - a label or event the soft CP signals at submission.

While reverting, `git checkout` on `videoOut.h` lost the header's earlier BC5 changes. They were
restored from `backend/kytyplus-patches/0001-bc5-lle-agc.patch`, and the tree's diff matches the
committed patch byte for byte.

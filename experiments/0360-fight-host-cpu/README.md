# 0360 — the host's CPU cost per frame at the second title's fight

Ordered by the top session on 2026-10-28 after the maintainer's decision on Q24 ("łatka jako opcja w menu emulatora
(tymczasowo), a docelowo zacznij prace nad odciążeniem aby pozbyć się łatki"). Exp 0359 (the bvh session) is the
temporary game patch for F454; this experiment is the throughput work meant to make that patch unnecessary. Base: main
9a91242 (shared normal affa0c22, archive bb50b2e0); branch exp/0360-fight-host-cpu; nothing shared changed (D19).
Box work under the BOX-LOCK, claimed in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0360/CLAIM.txt`. RT on for every run.

**Question.** Where does the host's CPU go per frame at the maintainer's fight (by host thread and host function), and
which change cuts it enough that the title's own Hi job workers finish their frame-end chunks before the main (owner)
thread reaches its help loop, so that the fight passes with exp 0359's patch switched off?

**Setup.** (filled in as the work goes)

**Result.**

**Verdict.**

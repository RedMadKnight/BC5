# 0353 — the night lake on the exp 0350 shared build: still patched, as variable as before

The top session, 2026-10-28, on the maintainer's "Sprawdź teraz". The day before, exp 0347 (F418) found the lake
patched. Since then the shared builds took exp 0349's IB cut, 0348's carried register, 0346 v3 and 0343 (exp 0350,
F433), and the maintainer saw clean water at another lake spot in his 0349 play (F432). Box work under the BOX-LOCK,
claimed in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0353/CLAIM.txt`.

**Question.** Is the night lake clean on the integrated shared build (normal affa0c22, `play-pkg.sh` 55531ab6)?

**Setup.**
- Exp 0347's lake bench, unchanged but for its paths. `setup0353.sh` copied `bench0347.sh`, `ab0347.sh` and
  `input-0347.cfg` to `~/bc5-work/exp0353` with 0347 → 0353. It built `play-pkg-0353.sh` (d66e11be) from today's
  `play-pkg.sh` with exp 0347's five edits by anchor, and checked the diff against exp 0347's own, line for line, with
  the names changed.
- RT off, from the bench's `input-0353.cfg`; exp 0299's private save copy and working directory.
- The metric is `patch0197.py`'s patch share in 20 frozen-view shots; a shot at 8 % or more counts as patched.
- The base rate (F418): 13 of 78 earlier bench runs came out clean. So after a clean first run, two more runs were
  made.
- The kernel log was streamed to the laptop (`raw/kernel-stream*.txt`). The live saves 3f8412c4884ddf14 were compared
  only. No shot was viewed; the shots stay on the box under `~/bc5-work/exp0353/r-W*/shots` and are never committed.

**Result** (`raw/W1.ab.txt`, `raw/W2.ab.txt`, `raw/W3.ab.txt`).

| Run | Time | Patched shots | Patch share |
| --- | --- | --- | --- |
| W1 | 08:52–08:57 | 0 of 20 | 0.7–0.9 % (clean) |
| W2 | 08:57–09:02 | 14 of 20 | clean for the first 7 shots (0.8–3.2 %, one at 11.6 %), then patched from shot 7 on (15.3–23.3 %) |
| W3 | 09:02–09:07 | 20 of 20 | 18.1–26.0 % |

- All three runs: binary affa0c22, one ring (0 compute-ring lines), RT off (~2,400 ray-tracing-off lines).
- No kernel fault or ring line, 0 fence timeouts, live saves unchanged.

**Verdict.** The night lake is not fixed on the integrated shared build. One clean run, one that turned patched
halfway, and one patched throughout: that is the same run-to-run variation as before (F418), including a state change
within a run (F344). The maintainer's clean water was this variation. Q21 stays open; exp 0312's run J1 remains the
next design.

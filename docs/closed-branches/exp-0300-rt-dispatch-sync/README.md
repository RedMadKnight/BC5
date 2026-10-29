# Branch exp/0300-rt-dispatch-sync, closed out

The RT-on line of experiments 0294–0370 (the bvh session), on `origin/exp/0300-rt-dispatch-sync` at `055c1d0`.
Main took its work piece by piece by copying files (for example d0c2668 from `f0fc75d`, 287a19a for 0343–0345,
c946dcb for 0370), and the branch merged main back twelve times, last at `324c1d9`. The branch was never merged
into main. This record was made on 2026-10-29, on the laptop only, against main `e7ab9b1`.

## Method

Content, not hashes. For each of the 147 non-merge commits not on main, every blob the commit wrote was looked up
in the objects reachable from `origin/main`, and every file was compared with main's tree and the branch's tip.
The branch's HANDOFF rows were compared with main's by id and by text, and its experiment directories by name.
The table is `classification.tsv` (one row per commit; the 12 merges are not listed).

| class | commits | meaning |
| --- | --- | --- |
| on-main | 59 | every blob the commit wrote is in main's history |
| on-main+superseded | 70 | part of it is on main as written; the rest was edited again later and main holds the later version |
| superseded | 9 | intermediate backend versions (0341, 0345, 0346, 0348, 0349): the integrated code is on main (d0c2668, 9bd60be, F433); 0345's window base was withdrawn (F417) |
| branch-only | 8 | exp 0352's batched CP check (5) and exp 0364's user-data hint (3): backend code that main does not have |
| left-out | 1 | `8dd5d7f`: `experiments/0290-mec-indirect-refusal/stream0290.sh` pointed at the box's LAN address for one night |

## What only the branch has

- **No experiment directory and no HANDOFF row.** All 512 F/Q rows of the branch are on main with the same text,
  except F490, which main has since marked as corrected by F527. The branch's highest finding is F495, the 0370
  design's F496–F499 are main's, and main goes on to F532: nothing collides, nothing is renumbered. Exp 0352's
  findings were already renumbered when main took them (F435–F437 → F437–F439, the README's note).
  Directories 0312 and 0317 of the branch's history were renamed there (to 0313 and 0320), both on main.
- **Backend code, in `backend-0352-0364-vs-main-e7ab9b1.diff`** (`git diff origin/main origin/exp/0300-rt-dispatch-sync`
  over the seven files; `git apply --check` passes on `e7ab9b1`):
  - exp 0352: `ProductLimit::batch` / `twice`, the batched form in `indirect_check.cpp`, its two switches
    `BC5_DIRECT_GPU_CHECK_BATCH` and `BC5_DIRECT_GPU_CHECK_TWICE` and the flag dwords in `direct.cpp`,
    `tests/indirect_check_batch_test.cpp`. Not integrated: it reaches 0.27 % of the checks (F438).
  - exp 0364: `include/bc5/user_data_hint.hpp` (v3) and `tests/user_data_hint_test.cpp`. Built into private
    builds only (F474); its protective effect is not shown.
  - the CMake test list with both tests.

  Exp 0352's `raw/build0352.sh` and exp 0364's `raw/build0364.sh` built from the branch's backend; this diff is
  that backend's difference from main, so the code stays with the repository when the branch is deleted.

## Left out

- `experiments/0345-gfx-dispatch-window-base/raw/box/h3-journal-dcb-probe.txt` (5.5 MB): main has it gzipped (268fbd8).
- `stream0290.sh`'s one-night SSH line (the LAN address and an identity file), see above.
- The correction paragraph that `3a46a34` added to exp 0358's README: the branch's merge `f4bea94` took main's
  README and dropped it. Its content is on main as F460 and in exp 0360's README, and `patch0358v4.pl` on main
  carries the fix, so the frozen README is not touched here.

## Files where main is newer

`backend/kytyplus-patches/0001-bc5-lle-agc.patch` (branch 2db34349, without exp 0372; main 9420cfa0 with
`pad_audio_route.hpp` and exp 0372), `README.md`, `CLAUDE.md`, `docs/HANDOFF.md`: the branch has not changed any
of them since `324c1d9`, so main's versions stand as they are. Nothing in this close-out touches them.

## After the merge

The branch and its worktree `bc5-0273` can go once two things are done:
1. Commit ids of the branch are cited on main (for example `f0fc75d` in d0c2668, `142ea25` and others in READMEs).
   Before the branch is deleted, keep them reachable with a tag, e.g.
   `git tag archive/exp-0300-rt-dispatch-sync 055c1d0 && git push origin archive/exp-0300-rt-dispatch-sync`.
2. The worktree holds an untracked `experiments/0294-refusal-plus-breadcrumbs/raw/` (485 KB, the 2026-10-25
   02:06–02:19 journal and kernel streams). Exp 0294 on main has no `raw/`; keep that folder somewhere first
   (the maintainer's call: a gzipped copy outside the repo, or committed) before the worktree is removed.

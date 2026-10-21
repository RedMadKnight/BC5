# 0187 — The second title's opening on the builds of 2026-10-18 morning

**Question.** The maintainer, 2026-10-20 evening, after exp 0186 (the night drift is in the build of
10-19 09:06 already): "First the builds of 10-18, morning." How fast does the title's clock run on
them, and how does it compare with today's build?

**Setup.**
- Kept binaries on the box: `kyty_emulator.0158-pre` (built 2026-10-18 08:41) and
  `kyty_emulator.0159-pre` (11:37). Both predate the AMM pool fix (190656c, 12:27; F206: the
  opening ended ~90 s in) and the night-scene fault's workaround (d50ca07, 17:08; F207: on the
  maintainer's runs the kernel's reset took the machine down). The night scenes cannot be reached
  on them, and the run stops before the opening's night jungle.
- `opening-old.sh` (here): exp 0180's scripted New Game opening (start screen, slot list, empty
  slot 3, challenge level) for 190 s: start screen and menu to ~150 s, the daytime forest from
  ~150 s. A kept binary runs through `emu-ts.sh`/`ajm_ts.py` of exp 0186 (decoder jobs timed from
  `KYTY_BC5_AJM_TRACE`); the current build with `KYTY_BC5_AJM_DUMP`. Frames counted from the direct
  journal's per-flip frame profile. The saves are restored before and after.
- **Runs:**

  | run | binary | switches |
  |---|---|---|
  | O1 | 0158-pre (10-18 08:41) | `BC5_DIRECT_CHAIN=0` (unknown to it); no cap, no audio hold of 10-20 |
  | O2 | 0159-pre (10-18 11:37) | as O1 |
  | O3 | current | `KYTY_BC5_MIN_FLIP_RATE=0` (no cap), chains as by default |
  | O4 | current | defaults (30-fps cap, chains) |

- Raw: `raw/opening-runs.txt`.

**Result.**
- **O1 (10-18 08:41):** start screen 0.99× (the first pass), the load dip 0.67–0.88×, 1.00× from
  57 s. From 87 s, right after the start screen's first press (85 s), the clock rises in the
  menu: 1.17 → 1.47 → 1.58× by 141 s, at ~41 flips a second. The daytime forest (153–185 s) runs
  1.44 → 1.68× at 32–36 flips a second.
- **O2 (10-18 11:37):** the same, starting later: 1.00× to 106 s, then 1.17 → 1.51× in the menu at
  ~41 flips a second, and 1.43 → 1.64× in the daytime forest at 34–39 flips a second.
- Both runs ended by the script at 190 s, before the night jungle. The saves were restored after
  each (`saves as in save-backup-0180-0953`).
- **O3 and O4 did not run to the end.** The laptop's link to the box dropped during O3 (started
  2026-10-20 ~22:20, "Connection reset by peer"); the laptop then sat on another network
  (192.168.1.x), and the box's Tailscale node had been offline for 6 days. Whether O3's script
  restored the saves is not known from here. TODO(verify) on the box: `diff -rq
  ~/bc5-work/save-backup-0180-0953 ~/bc5-work/_SaveData/PPSA03671`, and that no emulator is left
  running. For the current build, the same scripted opening was measured in exp 0183 (daytime
  forest 1.5–2.1× without a cap, F241) and exp 0184 (1.00× with the cap, F242).

**Verdict.**
- On the builds of 10-18 morning the title's clock already runs fast: ~1.5× in the menu after the
  first press and 1.4–1.7× in the opening's daytime forest. The speed-up is not a change of the
  last two or three days. The only later change that holds it back is the 30-fps cap (aa73775).
- At 32–39 flips a second, flips/s ÷ 30 would give 1.1–1.3×. The daytime forest runs faster than
  that because the drift has already set in in the menu: the per-frame stepping of F241 and the
  drift of F243/F244 add up.
- The drift also sets in in the menu, not only in the night scenes, and when it starts varies.
  O1 started 2 s after the first press and O2 21 s after it. In exp 0185/0186 the start screen and
  menu drifted in three of eight runs.
- TODO(verify): the builds of 10-17 evening (libopus from 5fc9236, 16:54, to the start-up stalls'
  fix a6f2c8b, 10-18 00:30) are not kept on the box and would need a rebuild from the patch at
  those commits. The maintainer's "the sound went naturally" build is probably among them, from
  when the opening's picture was stuck (F198, F201).

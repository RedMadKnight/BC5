# 0299 — The second title's lab renders washed-out white: which pass makes the white

**Question.** The maintainer reports the following about the lab, reached only since the PlayGo fix (F361):
- "w nowej lokalizacji - laboratorium powinno być bardziej szare - a obecnie mamy bardzo dużo białych obszarów - widać
  przedmioty, ale tak jakby od nich miało odbijać się światło i są mocno zabielone". The lab should be greyer; there
  are large white areas; objects are visible but look as if light were reflecting off them, strongly whitened.
- It looks the same with ray tracing on and off (his check, lean build 753889c9, 10:09–10:12, no amdgpu line).

Which pass makes the white: reflections or ray queries, exposure or eye adaptation, a texture or target format, or
something else? And what is a fix candidate?

Background (the top session):
- "RT on" in our builds is not full RT. The BVH compaction 0x909974400 is skipped by default (F207, F275), so the
  ray-query consumers may trace incomplete trees in both modes.
- RT off (`KYTY_BC5_RT=0`) drops only the BVH build list (F337/F338). `KYTY_BC5_RT_DETECT=1` also drops every
  program that uses `image_bvh(64)_intersect_ray` (it blanks the title's menu, F337), so it tells the ray-query
  consumers apart.

**Plan** (the top session's task of 2026-10-25 ~10:14, with the maintainer's OK: "Sam możesz też to przetestować",
"Najnowszy save i od razu widać"; on a BOX REQUEST for 10:40–12:15).
- **The lab bench** (exp 0194's scheme, new for today's launcher):
  - `setup0299.sh` snapshots the live saves (8289704a9338a118, never run on) and copies them once as the bench's lab
    save. The newest save is slot 4's autosave of 10:01:03, in the lab; "Continue" in the menu loads it.
  - It builds a private working directory (`~/bc5-work/exp0299/wd`: its own `_SaveData`, everything else a symlink),
    and derives `play-pkg-0299.sh` from today's `play-pkg.sh` by three sed edits, kept as a diff: the working
    directory, its own log, and exp 0194's input configuration.
  - `run0299.sh` (exp 0194's `run-0194b.sh`) resets the private save copy and starts the shared normal build e62a97c6
    with `continue.cmd` (cross at 60 s). It takes screenshots at fixed seconds and stops after ~260 s.
  - `ab0299.sh` drives one run:
    - our lock line, the 3-s dmesg stop, the live saves checksum before and after;
    - after the run, the journal's ray-tracing and skip lines, plus the shots' numbers by `wh0299.py`: mean luma
      and percentiles, the share of white (luma ≥ 0.90) and clipped (all channels ≥ 240) pixels, and chroma.
    Shots are never copied or committed.
  - `jw0299.py` lists the frame's passes from a draw-journal window: per event, the packet, the program, colour
    target 0's base, size and format (CB_COLOR0_INFO decoded with the repo's regdb), the mask and the viewport.
- **Runs**, all with RT off (`KYTY_BC5_RT=0`):
  - L1, baseline: shots, plus one draw-journal window once the lab is up.
  - L2: plus `KYTY_BC5_RT_DETECT=1`. If the white goes, the ray-query consumers make it.
  - L3–L5, by result: bisect the ray-query consumers with `BC5_DIRECT_SKIP_PGM` (0x909974400 kept), or drop the
    exposure or eye-adaptation compute and the lab's candidate passes from L1's journal.
  - L6–L7: test a fix candidate and confirm it.
- Rules: the live saves are never run on or restored over, with checks at the start, the end and around each run;
  the kernel stream; a stop at any fault, timeout or machine-down; RT on only after telling the top session; no
  screenshots or frame images in the repo.

**Setup as run** (the top session's GO of ~10:20 CET, relaying the maintainer's "Zbierz sam dane. Możesz uruchomić
samodzielnie"; window 10:22–12:15; BC-250, boot 68645b54, kernel 7.2.9-ogc3.1, shared normal build e62a97c6).
- **Setup, 10:22.**
  - Our window lock line. `setup0299.sh`: live saves 8289704a9338a118, snapshot and lab copy of 66 files each.
  - The private working directory: 5,144 symlinks plus its own `_SaveData`.
  - The launcher diff is exactly the four expected lines (`raw/play-pkg-0299.diff`).
  - The kernel stream ran for the whole window.
- **Getting to the lab** (shots viewed, below):
  - The title shows a start screen ("Press ✕"), then a save-slot list with slot 1 highlighted (slot 4 is dated 25/10
    10:01), then a Continue / Load / Credits menu.
  - So one ✕ (L1) stops at the save-slot list, and the maintainer's three ✕ (L1b, from `route-record.txt`: 0, 2.8 and
    3.8 s) load slot 1.
  - `slot4.cmd` (from 60 s: ✕, down ×3, ✕, ✕) loads slot 4's lab. `slot4-90.cmd` starts the same keys at 90 s,
    because the start-up load took 47–73 s and L7's keys fell into it.
  - The lab is up about 20 s after the last ✕. It is bright from its first frame, as the maintainer describes, and
    holds still: no input, a static view.
- **Runs**, all with `KYTY_BC5_RT=0` (RT off), each between live saves checks. The checksum was 8289704a9338a118
  before and after every run.

  | run | time | route | switches beyond the launcher's | outcome |
  |---|---|---|---|---|
  | L1 | 10:22–10:27 | 1 ✕ | `BC5_DIRECT_DRAW_JOURNAL=240:40` | save-slot list to the end; the emulator crashed at t ≈ 285 s (below) |
  | L1b | 10:30–10:35 | 3 ✕ | journal 240:40 | slot 1's night scene, then a tutorial card (pause) |
  | L2 | 10:36–10:37 | 3 ✕ | `KYTY_BC5_RT_DETECT=1` | GFX ring timeout at t ≈ 45–52 s, in the start-up load (below) |
  | L3a | 10:39–10:41 | ✕ ✕ ✕, 6 s apart | — | route probe: start screen, slot list, menu |
  | L3 | 10:42–10:47 | slot4 | journal 200:40 | the lab, white |
  | L4 | 10:48–10:52 | slot4 | `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900` | the lab, grey |
  | L5 | 10:52–10:55 | slot4 | `BC5_DIRECT_SKIP_PGM=11d049aa00,909974400` | floor and cart grey, glass pale |
  | L6 | 10:56–10:59 | slot4 | `BC5_DIRECT_SKIP_PGM=11d04a6000,909974400` | white |
  | L7 | 10:59–11:02 | slot4 | the build list below | keys fell into the start-up load; start screen only |
  | L7b | 11:03–11:06 | slot4-90 | `KYTY_BC5_RT_BUILD_PGM=` launcher default + `11d049aa00,11d04a6000,11d04bb900` | the lab, grey |

- **Shots viewed.** By the top session's leave, these shots were copied one at a time to the session's scratchpad,
  outside every checkout, looked at and deleted right after: L1b t135 and t150; L3a t057, t063 and t069; L3, L4 and
  L5 t100. No image is in the repo. Everything else is `wh0299.py`'s numbers (`raw/L*.wh.txt`).
- **Not touched.** The launcher's `bc5-run.env` points `KYTY_BC5_INPUT_RECORD` at the maintainer's
  `~/bc5-work/route-record.txt`. It was unchanged after all runs: 232,777 bytes, 10:01:03.

**Result** (`raw/`).
- **What the lab looks like** (L3 t100, viewed):
  - The floor glows near-uniform white with hard edges along the geometry.
  - The glass partition and the room behind it on the right are a flat, washed-out white-grey, and a cart there is
    near-white with dark outlines.
  - The walls and cabinets behind the characters are near-black.
  - The characters and the wall screens look normal. So it is not global exposure.
- **The numbers** (median over the shots in the lab, a static view):

  | run | traversal variants running | luma mean | p90 | p99 | white (≥ 0.90) | clipped (≥ 240) | chroma |
  |---|---|---|---|---|---|---|---|
  | L3 | all | 0.335 | 0.868 | 0.962 | 0.064 | 0.013 | 0.085 |
  | L4 | none | 0.303 | 0.607 | 0.883 | 0.006 | 0.000 | 0.113 |
  | L5 | 0x11d04a6000 (and 0x11d04bb900) | 0.278 | 0.820 | 0.883 | 0.005 | 0.000 | 0.092 |
  | L6 | 0x11d049aa00 (and 0x11d04bb900) | 0.283 | 0.869 | 0.970 | 0.071 | 0.019 | 0.072 |
  | L7b | none (through the RT-off build list) | 0.302 | 0.609 | 0.883 | 0.006 | 0.000 | 0.113 |

- **What the views show:**
  - L4 (viewed): the floor is mid-grey, the glass shows the shelves and glassware of the room behind it, the cart is
    grey metal, and the concrete walls are lit.
  - L5 (viewed): the floor (darker grey than L4) and the cart are no longer white, but the glass is still flat and
    pale.
  - L6's numbers match L3's.
  - L7b's numbers match L4's to the third decimal; its grid of 9 regions is the same.
- **The lab frame's passes** (`raw/L3.jw.txt`, a draw-journal window at t = 200 s):
  - 3D at 1664 × 936; a half-resolution reflection chain in compute;
  - 0x11d04d0c00 / 0x11d04cb400 and 0x11d04ddd00 at 381 groups, 0x11d03b1000 (1 × 1 × 1), 0x11d03afc00 (48 groups);
  - indirect 0x11d04d1000 … 0x11d04d6d00 around the traversal variants 0x11d049aa00 and 0x11d04a6000;
  - then draws into an 832 × 468 RGBA16F target, half the render size;
  - 0x11d04bb900 is not in that window. It goes with the other two as in the launcher's pre-0218 list.
- **The ray-query programs** (L2's scan, `raw/L2.rtprog.txt`):
  - bvh64: 0x11d023c300, 0x11d0323900, 0x11d0323c00;
  - bvh: 0x11d03b1000, 0x11d040e200, 0x11d042ba00, 0x11d049aa00, 0x11d04a6000;
  - 185 programs scanned without one.
- **Side findings, not chased:**
  - **L2's hang is F337's mechanism again.** With `KYTY_BC5_RT_DETECT=1` (every ray-query program dropped) the title
    hung in its start-up load at t ≈ 45–52 s, 10:37:14: GFX ring timeout, process kyty_emulator thread
    bc5-chainwd. The reset succeeded ("device wedged, but no recovery needed"); devcoredump
    `~/bc5-data/captures/devcoredump/20261025-103714-devcd1.txt`. The amdgpu dmesg count went 125 → 134. It is the
    only kernel event of the window.
  - **L1's crash, 10:27:41, needs its own experiment.** At the save-slot list, t ≈ 285 s, the host reported an access
    violation reading 0xc at guest 0x903d7eca0, with the AJM ATRAC9 decoder named in the dump (`raw/L1.run.txt`;
    the emulator log `~/bc5-work/exp0299/r-L1/emu.log`).

**Verdict.**
- **The lab's white is made by the RT reflection traversal.**
  - With its variants skipped the lab renders as it should: grey floor, see-through glass, lit walls.
  - 0x11d049aa00 whitens the opaque glossy surfaces (floor, cart); 0x11d04a6000 whitens the glass. 0x11d04bb900
    goes with them as in the pre-0218 list.
  - With them running, the walls and cabinets also come out darker. So the traversal's output is wrong, not just
    too bright.
- **Why, in these runs:**
  - With RT off (`KYTY_BC5_RT=0`) the switch drops the BVH build list, so the traversal walks trees that were never
    built (F337/F338).
  - With RT on it walks trees built without the compaction 0x909974400, which stays skipped (F207, F275, F277).
  - The maintainer saw the same white with RT on, so the same passes probably make it there too. That is not tested
    here (L8/L9 are on hold).
- **Fix candidate for RT off, tested (L7b = L4):** add 0x11d049aa00, 0x11d04a6000 and 0x11d04bb900 to the launchers'
  `KYTY_BC5_RT_BUILD_PGM` default. "Off" then also drops the traversal that can only walk empty trees, and the lab
  is grey. It is a launcher change only (`play-pkg.sh`, `-log`, `-quiet`) and waits for the maintainer's yes.
  - Cost: no RT reflections with RT off, where they can't be right anyway.
- **For RT on, open:**
  - The interim would be the pre-0218 "reflections off" list, which costs the reflections wherever they look right
    (F218).
  - The real fix is the traversal's input: the BVH with the compaction 0x909974400 (F207/F275).
  - L8 (default RT on) and L9 (RT on with the three variants skipped) would show whether the same passes make the
    white with built trees.

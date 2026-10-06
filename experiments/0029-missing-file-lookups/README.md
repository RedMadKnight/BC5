# 0029 — The level load and the cutscene's stall: what a missing file costs through `bc5-mount`

**Question.** Experiment 0022 left the first level's 135 s load unprobed after the host's directory
scan was removed (F51); the game still asked for 21,061 files that do not exist. Runs 128–130 (an
empty save, the host pressing the buttons) showed the opening cutscene dropping to 6–9 fps for
about 18 s at 200–220 s, with the frame's time in the game's own thread, not in the host's GPU
path. Is it the file lookups, and where in the stack?

**Setup.** BC-250 dev box, 2026-10-06, the host of experiments 0026–0028 (patch 0001 with the
haptics routing of F69), runs started unattended as in `experiments/0026-water-handshake/raw/
run128-summary.txt` (an empty `KYTY_BC5_SAVEDATA_DIR`, `KYTY_BC5_AUTOPRESS=50:cross,58:cross`),
the frame profile per second from `gc/direct.log`, the guest log for the HLE calls. `bc5-mount`
from `tools/` at the commit before this one, then with this commit's `fuse.rs`; the stat timing
with the container mounted by hand (`bc5-mount mount … ~/bc5-work/mnt-stat-test`, no emulator).

**Result.**

*The stall is the game's thread, and it is in `KernelStat`.* Run 129, seconds 201–218: 160–170 ms
a frame, of which 160 ms outside the host (the game's own work), the host 2 ms, GPU busy 11 ms.
The guest log for those seconds shows three threads (`DrawThread`, `Physics_ATQT` and one more)
waking every ~165 ms in lockstep, and in every such frame eight `KernelStat` calls on files under
`/app0/data/prein/{bg,characters,common,effects,proto,text,ui,odx}/odx/<id>`, every one answered
"file not found" (12 of them per frame counting both passes; 1,296 in the 18 s window, 20,939 in
the 384 s run).

*A missing file costs 8 ms through the mount.* With the container mounted by hand, 100 `stat`
calls from a shell on `data/prein/bg/odx` (12,133 entries):

| stat | before | after |
|---|---|---|
| 100 distinct missing names | 0.83 s (8.3 ms each) | 0.14 s (1.4 ms each) |
| the same missing name 100 times | 0.83 s | 0.19 s |
| an existing file 100 times | 0.19 s | 0.13 s |

The ~1.3 ms that remain are the `stat` process itself. The cause was `Bc5Fs::lookup` in
`tools/bc5-mount/src/fuse.rs`: a linear scan of the directory's children folding every name to
upper case (an allocation per entry), run twice for a miss — the length-filtered pass and then the
full one. KytyPlus's resolver asks the exact path first, and only on ENOENT consults its own
per-directory name cache (F51), so every one of the game's missing files went through this scan.
Twelve of them in a frame are 100 ms, which with the rest of the frame is the 165 ms observed, and
20,939 of them in a run are about 170 s — the length of the level load.

*The fix.* `fuse.rs` builds a `HashMap` of folded child names per directory on its first lookup,
and answers a miss with a negative entry carrying the one-hour TTL (FUSE nodeid 0; the container
never changes), so the kernel answers the next stat of the same missing name itself. Tests and
clippy pass on the box (Ubuntu 26.04 distrobox) and on Windows; the existing-file read, the
entry count and case-insensitive names were checked on the mounted container.

*Run 131* (the fixed mount; the same build otherwise plus the pad-audio change of F72; 600 s,
unattended; `raw/run131-summary.txt`): no slow window at all — 51–60 flips a second from the
slot selection at 58 s through the whole opening cutscene; the cutscene was already on screen at
105 s (in runs 128–130 it began at about 225 s), the crash landing at 211 s, the ship's flight at
339 s at 60 fps, the start of gameplay with the controller tutorial at 361 s (32 fps, nobody
steering), the character in the first level's hub at 578 s at 49 fps. 0 failed submissions, 3
waits given up, the save written 69 times, 34,089 missing-file stats (more than run 129's 20,939:
the game got further). Load from the slot selection to the cutscene: about 25 s, from 167.

**Verdict (2026-10-06).** Passed: the level load's 135 s and the cutscene's stall were the same
thing, the mount's negative lookups, and both are gone. What paces the remaining ~25 s is not
probed. Not touched: how many files the game asks for (its own eight-directory search), the
resolver in KytyPlus. The maintainer's report of the audio breaking up in the cutscene (runs
129–130, with a controller whose USB link drops every 10–60 s) is addressed separately (F72) and
not yet heard with the fix.

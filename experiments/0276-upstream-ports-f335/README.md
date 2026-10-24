# Experiment 0276 — two KytyPlus upstream library fixes into patch 0001 (F335)

*Branch `ports/upstream-f335`; number assigned by the top session 2026-10-24; GO for the CPU-only steps received the same evening.*

## Question

Do KytyPlus `41beda43` (APR WriteAddress record sizes 8/12/16 by value, measure NIDs `C+IEj+BsAFM` and `4fgtGfXDrFc`) and `c885da0a` (the pad audio device also found as "Wireless Controller" with four channels) build and behave on the box, and does the new device match leave the DualShock 4 alone?

## Setup (planned)

1. `audio.diff` and `libAmpr.diff` apply to the shared tree's `src/libs/audio.cpp` and `src/libs/libAmpr.cpp` (KytyPlus `f266548` + patch 0001 at `c8a38cc`). Check the two files' md5 against the shared build's recorded tree before applying.
2. Private build: the two translation units and a relink (not the shared binaries).
3. `check-pad-sinks.sh`: channel count and rate of every sink. Expected: the DualSense's USB device 4 ch / 48 kHz (matches), the DualShock 4's sink 2 ch / 32 kHz (F326; must not match). The match requires `channels == 4` and only fires when `KYTY_BC5_PAD_AUDIO_DEVICE` is unset.
4. One run per pad with `KYTY_BC5_AUDIO_TRACE=1`: which device each pad-speaker and vibration port opened; with the second title, `KYTY_BC5_AMM_TRACE=1` for the write-address records' sizes (no title seen so far packs them by measure; the change is a correctness fix without a known symptom on our titles).
5. The maintainer decides; only then the patch on main changes.

## Result

*Build step, 2026-10-24 22:09, on the top session's GO after exp 0278's integration, under this experiment's own lock line (`raw/build-inputs.txt`, `raw/build.out`).*

| Check | Value |
|---|---|
| Tree `src/libs/audio.cpp` | md5 `03b3af4e` (expected, F330), mtime 2026-10-24 17:06 |
| Tree `src/libs/libAmpr.cpp` | md5 `5f2ec30b` (expected), mtime 2026-10-23 11:30 |
| Shared normal binary before / after | `7947154c` / `7947154c` (exp 0278's integration of 22:06; untouched) |
| Diffs applied (`git apply -p3`, the box has no `patch(1)`) | both cleanly, no offset (`raw/patch-audio.out`, `raw/patch-libAmpr.out`); patched `audio.cpp` `ee61d1d9`, `libAmpr.cpp` `93bdfe77`; the combined diff `raw/patch_0276.diff` (204 lines) |
| Compile + link (`build0276.py`, nice 19, 19 s) | rc 0; `~/bc5-work/exp0276/kyty_emulator` 166,538,272 bytes, md5 `dd103996`; 14 occurrences of the string "Wireless Controller" |
| Warnings | 2 distinct (`libAmpr.cpp:1919:143`, `:2028:50`, `-Wformat-extra-args` in the `amm trace: read file` lines), both outside this experiment's hunks (`libAmpr.cpp` 1261–1271, 2808–2829, 3138–3240, 3741–3765), so pre-existing in the shared tree's unit |

Sink listing: my own `check-pad-sinks.sh` runs did not happen (the first failed on the script, an ssh shell has no `XDG_RUNTIME_DIR`, fixed; the retry found another session's bench running and stopped). The top session recorded the sinks at the play test's start instead (`raw/sinks-2235.txt`, the dock's serial redacted): the DualShock 4 is `alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.analog-stereo`, **"Wireless Controller", s16le 2 ch 32000 Hz** — Sony's generic USB product string on this pad too, so the four-channel condition of the new rule is what keeps it apart from the DualSense. A `wpctl status` read earlier that evening (`raw/wpctl-status.txt`) showed the DualSense as "DualSense wireless controller (PS5) Direct DualSense Wireless Controller", which the default "DualSense" match already covers.

*Play test, 2026-10-24 22:35–23:04 (`raw/play-2235-summary.txt`; the 21.9 MB log stays on the box at `~/bc5-work/exp0276/play-2235.log`):* the maintainer played the second title for ~29 minutes on the private binary, ray tracing on, with the DualShock 4 connected at start and a switch to the DualSense during play, no hang or fault. His words: "Wszystko ok, przełączałem między pad PS4 i PS5 bez problemu i drgania były. Pod koniec rozgrywki było zdecydowanie mniej FPS."

- **Rumble per pad:** all 25,147 rumble writes in the log are the F214/F328 fallback (`via game controller`, 100 ms writes), from t ≈ 40 s to the end, with both pads; no `rumble:` failure line. No vibration (type 10) port with the pad stream's 6 channels appears in the audio trace, so no pad port was routed to a controller audio device at any time.
- **"Wireless Controller" match:** the DualShock 4's 2-channel sink did not match (the pad-speaker port, type 4, ran as a 1-channel port on the default sink from t ≈ 151 s, F329's pattern). The DualSense side of the rule was **not exercised**: its device was absent when the ports opened, and `audio.cpp` re-routes a port only after a device loss (`pad_retry`), not when a new device appears.
- **APR record sizes:** no visible effect in 29 minutes of the title's streaming (no error, no EBUSY; `KYTY_BC5_AMM_TRACE` was off).
- **Frame rate:** 24–41 flips/s by minute with dips at minutes 13–14, 20, 23–24 and 28; PSI memory "full" avg300 13.6 % at the end, zram 1.3 GB (top session's digest), so memory pressure is the likelier cause than these two changes, which touch neither the GPU path nor the main mix.

## Verdict

**The two ports build on the box against the shared tree with no new warnings, leave the shared binary untouched, and a 29-minute DualShock 4 / DualSense session on them passed with rumble on both pads.** The DualShock 4's own "Wireless Controller" sink (2 ch, 32 kHz) is correctly left alone by the four-channel rule. Not shown by this run: the rule matching a DualSense that enumerates as "Wireless Controller" (the box's DualSense enumerates with "DualSense" in the name, so on this box the port is a no-op for the DualSense; it matters for a controller whose PipeWire description carries only Sony's USB string, as upstream `c885da0a` reports on other Linux systems), and any effect of the APR record sizes (a parity fix without a known symptom here). Integration is the maintainer's call; the diffs are `audio.diff` and `libAmpr.diff` here, the combined one `raw/patch_0276.diff`.

Sources: KytyPlus `41beda43`, `c885da0a` (github.com/Coder787-source/KytyPlus); HANDOFF F69, F326, F335; `docs/ports/upstream-sync-review.md` §2.

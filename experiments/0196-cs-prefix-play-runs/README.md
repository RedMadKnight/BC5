# 0196 — The compute-state prefix in play: the probe, then `BC5_DIRECT_CS_PREFIX=1` for 17 minutes

**Question.** Experiment 0195 prepared `BC5_DIRECT_CS_PREFIX`. It puts the graphics queue's tracked compute registers in
front of a graphics buffer that draws nothing and dispatches before it sets `COMPUTE_PGM_LO`. In play, which buffers
does the probe (`=journal`) find, and which program do they inherit? Does `=1` run without faults and at an unchanged
frame rate?

**Setup.**
- BC-250 dev box, 2026-10-22. Kernel 7.2.9-ogc3.1, Mesa 26.2.4, libdrm 2.4.134.
- Binary: `~/bc5-work/exp0195/kyty_emulator` (built 10:44:37, sha256 570deb873245bdee…). It is the shared build's
  objects of 10:22:48, which include exp 0193's touchpad mapping, plus exp 0195's `bc5LleAgc.cpp`.
- Launch: the normal launcher (`play-any.sh` → `play-pkg.sh`) with its skips kept
  (`BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`) and the TF ring on. The maintainer played both
  sessions.
- Session 1 is the **probe**: desktop shortcut "BC5 emulator (sonda 0195)", `BC5_EMU=… BC5_DIRECT_CS_PREFIX=journal`,
  10:56–11:04 (journal `~/bc5-data/captures/play-20261022-1056`, t 0–473 s).
- Session 2 runs **`=1`**, on the maintainer's yes (D16). It was started from SSH on the maintainer's display with the
  same switches and `=1` (shortcut "BC5 emulator (prefiks CS 0195)"), 11:36:10–11:53:33 (journal
  `play-20261022-1136`, t 0–1040 s). The night-water session (exp 0194) held its scripted runs meanwhile.
- The journal logs the first 64 such buffers, then every 1024th (`cs prefix (exp 0195): …`). The counts below are
  therefore "at least 64" once 64 is reached.
- Raw files:
  - `raw/probe-1056-flagged.txt` and `raw/cs1-1136-prefixed.txt`. Columns: t s, dcb dwords, offset of the first
    dispatch, the queue's program, RSRC1, RSRC2, prefix dwords, running count.
  - `raw/probe-1056-frames.txt` and `raw/cs1-1136-frames.txt`: flips per window, frames over 250 ms, the long ones in
    full, timeouts and kernel lines.
  - `raw/sessions-long-stretches.txt`: frames with GPU busy over 1 s or label waits over 1 s, in sessions 0808, 0933,
    1056 and 1136.
- Screenshots and the play-pkg log stay on the box (`~/bc5-work/exp0192/shots/115318-cs1-0196.png`,
  `~/bc5-work/exp0196/play-pkg-cs1.log`).

**Result.**
- **The probe (1056) found at least 64 such buffers in 301 s, in three kinds.**
  - 40 are compute-only heads of 255–388 dwords inheriting **0x11d039cd00**: session 0808's buffer, which recurs about
    every 5–25 s in play (as in 0933).
  - 15 are **large compute-only graphics buffers** of 3,742–32,643 dwords that draw nothing. They open with a
    dispatch at offset 8–27 and inherit 0x0909974c00, 0x090985f200, 0x0909973d00/3f00/3900/3700/7100, 0x0909974400 or
    0x11d0287900, the BVH builders and their neighbours.
  - 9 small ones inherit 0x11d0375600, 0x11d0415700, 0x11d0404200, 0x11d0376b00, 0x090997a500 or 0x11d0322e00.
  - **Correction to experiment 0195 (and F253).** The five large captured dcbs that `inherit_check.py` flagged
    (sessions 1729/1809) also draw nothing: each has 0 draws and 585–2,794 dispatches. So they get no draw prefix
    either. They inherit their program too and are as exposed as the 328-dword head; the compute prefix covers them.
- **`=1` (1136): no fault in 17 minutes.**
  - At least 64 buffers got the prefix by t ≈ 476 s: 36 heads of 0x11d039cd00, 21 large compute-only buffers and 7
    small ones.
  - Each prefix is the same 58 dwords, and the program it names is the one the probe saw for that kind of buffer.
  - 0 fence timeouts. 0 kernel amdgpu lines after the start (from dmesg line 1695). No SQC fault, no ring reset.
  - The maintainer reached the night lake. A level-up there, answered with the touchpad, shows exp 0193's mapping
    working.
- **Frame rate.**
  - 29–50 flips a second per 30-s window (fps counter).
  - In the cutscenes between t ≈ 210 and 450 s it was 30–40, with frames of 1.2–9.0 s at 279.1, 280.7, 289.7, 362.3,
    378.3, 429.0, 430.3, 444.9 and 959.4 s. Of those, 279.1, 289.7 and 429.0 s were GPU time (3.5, 2.4 and 9.0 s), and
    362.3 s was a 10-s label wait with the GPU idle.
  - The probe session had 23–43 flips a second, one 1.6-s GPU frame and two 4.4 / 6.1-s freezes with the game thread
    outside the host. Session 0808 had a 1.2-s GPU frame and a 7.2-s label wait.
  - The sessions did not play the same scenes, so the frame rate is not compared here.
  - The long GPU stretches do not follow a prefixed buffer closely in time. The nearest prefixed buffers come 1–12 s
    earlier: 267.6 s before 275.6, 285.4 s before 287.3, 419.5 s before 420.0. Whether the prefix contributes is not
    settled.
- **What the maintainer saw.**
  - In the cutscenes, the characters' movement was slowed while hair and effects ran at normal speed, and the picture
    fell behind the sound. The same complaint ("near the end the picture was very slow against the sound") came from
    the probe session, where the prefix was only journaled.
  - So it is not the prefix. It comes with frame rates of about 30–37 a second in those scenes. A per-frame animation
    step in the cutscenes is the candidate (F241's stepping; F247 measured 1.00× only at 44–52 flips/s).
    TODO(verify).
  - The patchwork water is visible in the 11:53 screenshot. That is exp 0194's question.

**Verdict.**
- **The compute prefix runs in play without a fault**: 17 minutes, at least 64 prefixed buffers, no timeout and no
  kernel message. The probe confirms the two kinds of exposed buffers: the 0x11d039cd00 heads, and large compute-only
  BVH buffers, which experiment 0195 wrongly counted as drawing.
- Not shown: that the prefix prevents session 0808's fault. That fault needs another client's compute dispatch in the
  gap and happened once in about 30 minutes of play, so one clean session is not proof.
- Open: whether the prefix lengthens GPU stretches, and why the cutscene characters slow down at about 30–37 flips/s
  (seen without the prefix too). The next step that decides the first is an A/B in the same scenes: the normal
  shortcut against "BC5 emulator (prefiks CS 0195)", from one save. The lake save the maintainer kept
  (`~/bc5-work/saves-lake-1153`, slot 3) is after these cutscenes; for them, an earlier slot.
- `patch_0195.diff` stays out of the shared tree and patch 0001, and the launchers are unchanged, until that A/B. That
  is the maintainer's call.

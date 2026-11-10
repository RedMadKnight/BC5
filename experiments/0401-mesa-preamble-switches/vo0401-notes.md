# Exp 0401 series e4: survey item 10, `sceVideoOutGetOutputStatus` (switch `KYTY_BC5_VIDEOOUT_STATUS`) — notes, 2026-11-03

Written on the laptop with no box access. This is item 10 of exp 0402's Top 10. `prtvo0401-notes.md` (item 10) found it
"not applicable": the host answers 1 before and after registration, and exp 0291 (F354) saw no change on the second title
with 2. Under the maintainer's new rule, ports are judged for any title, so the behaviour is ported behind a switch
anyway. This file supersedes that verdict for item 10 only. Its facts about our code still hold, and item 7 is untouched.

Deliverables, all in this directory:

| File | md5 |
|---|---|
| `mkvo0401.py` | `505de50862f771bd00933147e354fea7` |
| `vo0401.cpp` | `3839486eb578aadd0b6ff39c4972ed49` |

The unit it writes:

| Unit | In md5 | Out md5 | Lines |
|---|---|---|---|
| `src/graphics/presentation/videoOut.cpp` | `f848f5c6b81196e9722f3c7caf3984ec` | `3fa490f762fb6a9612289ef3a4018150` | 2,087 → 2,148 |

No header is edited.

## Sources read

**Our code.** KytyPlus f266548 + patch 0001, the series e4 tree (`…/19eb012d-…/scratchpad/e4/full`).
- `src/graphics/presentation/videoOut.cpp` (f848f5c6):
  - `VideoOutGetOutputStatus` is at 1837-1863.
  - `VideoOutConfig` is at 177-196. Its `width`/`height` are written only by `Impl::Init` (666-671).
  - `RegisterBuffers2` (1418-1514) writes `groups[set_index]` and `buffers[]`, never the size.
  - `IsOutputSupported` is at 1902-1919 and `ConfigureOutput` at 1982-2009. The vblank pacing reads
    `Config::GetVblankFrequency()` whatever the output mode (866).
- `src/libs/libVideoOut.cpp` (572eada2): NID `utPrVdxio-8` at :38.
- `src/graphics/presentation/window/swapchain.cpp:470`: the swapchain format is fixed at `eR8G8B8A8Unorm` /
  `eSrgbNonlinear`. There is no HDR output path.

**sharpemu** (GPL-2.0-or-later), `src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` at `b1ec286` (b1ec2866575b…, #1125).
The only later commit to the file, `8ddf660`, does not touch this function. HEAD is `514d766`.
- `VideoOutGetOutputStatus`, 505-544: a Gen5 port with every buffer group null gets the size 3840×2160 (524-536).
- `WriteOutputStatus`, 549-562:
  - `resolution` is 2 when width ≥ 3840 or height ≥ 2160, else 1.
  - `dynamicRange` is HDR ? 2 : 1.
  - `refreshRate` is 13 when the port's rate is ≥ 119, else 3.
  - `flags` is HDR ? 1 : 0.
  - The rest of the 0x30 bytes is cleared.
- Port defaults (244-246): 1920×1080 and `GuestRefreshRate`. That rate comes from `SHARPEMU_GUEST_REFRESH_RATE`, default
  60 (56-59).
- After registration the size is the registered set's: `RegisterBufferRange` 1808-1814 and
  `SubmitChangeBufferAttribute2` 1417-1419. `UnregisterBuffers` clears the group but keeps the size (1294).
- Mode 0xF can be configured only when the port's rate is ≥ 119 (`IsOutputSupported` 385, `ConfigureOutput` 445-447).
- HDR is "host output supported" (`HostVideoOptions.cs:89-91`).
- Evidence: the commit message reports one title, TMNT: Splintered Fate. It read HD and laid its viewport out for 4K
  over 1080p buffers. This is no console measurement.

**AnyPS5** (GPL-2.0-only) at `4f41f4c37`.
- `core/libs/prx/libSceVideoOut/src/Output.cpp:22-30`, `outputStatus`:
  - `resolution` = `GetDisplayResolution()`.
  - `dynamicRange` = host HDR ? 2 : 1.
  - `refreshRate` = output mode 0xF ? 13 : 3.
  - `flags` = 0. The other fields are value-initialised.
- `Output.cpp:184-198` is `sceVideoOutGetOutputStatus`, and `200-213` is `…WithVrr` (80 bytes; the first 48 are this
  status).
- `VideoOutDriver.cpp` holds the display side:
  - `resolutionIndex` (73-75) gives 2 for ≥ 3840 or ≥ 2160.
  - `configuredResolution` (77-91) reads `APS5_OUTPUT_RESOLUTION=WxH`.
  - `GetDisplayResolution` (558-561) returns the override or the cached display class.
  - `updateDisplayRefreshRate` (563-570) caches SDL's current mode of the window's display.
  - `vblankEnd` (586, 592) runs 59.94 Hz vblanks unless the mode is 0xF.
- Commits:
  - `bfeeed4ef` (2026-10-19): "report the output resolution from the host display as measured on a PS5".
  - `983a81d91` (10-21): the override.
  - `c9ba43bfb` (10-14): HDR output.
  - `e604020013` (10-27): "report output status flags 0 with HDR output".
- Tests:
  - `tests/Flip.cpp:1221-1253`: no buffer → the display's class, and a flipped buffer of the other class does not
    change it.
  - `tests/HdrPresent.cpp:139-140`: dynamicRange follows host HDR.
- Debt note `docs/dev/debt/libSceVideoOut.md:27`. A payload on a PS5 (firmware 12.70), no buffer registered:
  - right after `sceVideoOutOpen(0xff, 0, 0, NULL)`, `resolution` was 2 with the console on Automatic on a 4K
    display, and 1 with it set to 1080p;
  - on an HDR display with HDR on, `dynamicRange` was 2 and `flags` 0.
  - Not measured: the status after registration, a 1440p output, a sub-4K display on Automatic, and `flags` in a title
    that enables HDR.
  - `:18` (WithVrr) adds a console answer for that call: null → 0x80290002, unknown handle → 0x8029000B.

**Our experiments.**
- HANDOFF F67: the box's display is a DELL U2212HM, 1920×1080 at 60 Hz, SDR, no VRR.
- F354 / exp 0291: the second title calls GetOutputStatus once at start, before `RegisterBuffers2`. Told 1 or 2, it
  registered the same 3840×2160 buffers with the same GPU time.
- Exp 0327/0329 stub lists: the title's only VideoOut stubs were the four exp 0329 registered. `gWT7X8H0bYs`
  (`…WithVrr`) is not imported.

## Field by field: ours, sharpemu, AnyPS5

| Field | Ours today | sharpemu b1ec286 | AnyPS5 4f41f4c37 | Decision |
|---|---|---|---|---|
| `resolution`, before registration | class of the port size (`--screen-width/height`, default 1280×720) → **1** | **2** (Gen5) | class of the host display's mode → 1 on the box's DELL; 2 on a 4K display | **Ported:** on → 2. Both sources give 2 for the console on a 4K display with Automatic, the one state measured with a 2 (AnyPS5's payload). |
| `resolution`, after registration | same, 1 (registration does not change the size) | class of the last registered/changed set's size (2 for the second title's 3840×2160) | the display's class, unchanged by buffers | **They disagree; neither is measured. AnyPS5 is picked:** on → 2 whatever the buffers. Reasons below. |
| `dynamicRange` | 1 | host HDR ? 2 : 1 | host HDR ? 2 : 1 (measured: 2 with HDR on) | Not changed. Both rules give 1 on this host (SDR-only swapchain, SDR display). |
| `refreshRate` | 13 if mode 0xF or `--vblank-frequency` ≥ 119, else 3 | 13 if the port's pacing rate ≥ 119, else 3 | 13 if mode 0xF, else 3 | Not changed. Each reports its own vblank rate, and ours equals sharpemu's: 0xF is configurable only at ≥ 119 in both. AnyPS5 differs only at `--vblank-frequency` ≥ 119 in mode 1, a state AnyPS5's host cannot be in (its vblanks follow the mode). The launcher runs at 60 (F354), where all three answer 3. |
| `flags` | 0 | HDR ? 1 : 0 | 0 (measured, `e604020013`) | Not changed. AnyPS5 is the better source (a console measurement), and ours already says 0. sharpemu's rule also gives 0 here (no HDR). |
| `reserved[3]` | 0 | 0 (cleared) | 0 | Same. |
| Null `status` | INVALID_ADDRESS, before the handle | the same | throws (unmeasured here; measured 0x80290002 on `…WithVrr`) | Same as the measured answer. |
| Unknown handle | INVALID_HANDLE | the same | throws (unmeasured here; measured 0x8029000B on `…WithVrr`) | Same. |
| Layout | 48 bytes: u32, u32, u64, u64, u64[3] | 0x30, the same offsets | `SceTypes.hpp:2351-2357`, the same | Same. |

**Why AnyPS5 after registration.**
- What was measured: with no buffer registered, the field follows the console's output setting (4K Automatic → 2,
  1080p → 1). Buffers did not exist yet, so they could not be the source.
- A buffer registration does not renegotiate HDMI. A title that registers 1080p buffers on a 4K TV is scaled by the
  console, and its output stays 4K.
- sharpemu's own b1ec286 comment says the same: "A PS5 reports what the display chain can take, not the buffers a title
  has not picked yet". Its after-registration rule is the old placeholder rule that b1ec286 kept.
- On the second title the choice makes no difference: it registers 3840×2160 (F155), and both rules give 2.
- The two differ only for a title that registers sub-4K buffers and asks after that. `vo0401.cpp` shows the
  difference: a sharpemu-like mutant fails 6 of its 27 checks (below).

## What was ported

`mkvo0401.py` makes two edits to `src/graphics/presentation/videoOut.cpp`. Each anchor is asserted exactly once, and a
tree that has the edit already is refused.

1. **A block before `VideoOutGetOutputStatus`** (the output's lines 1837-1895).
   - The comment block names exp 0401 series e4, the sources with their commits, lines and licences, the decision above,
     and what was left alone.
   - `bool Bc5VideoOutStatusOn()` reads the switch once (a function-local static). It is on when the variable is set,
     non-empty and not "0" (F767).
   - `uint32_t Bc5VideoOutStatusResolution(today, port_width, port_height, registered_sets)` returns `today` when off
     and 2 when on.
     - On its first call it prints one stderr line, on or off: `[bc5] exp 0401: videoout status on|off: resolution N at
       the first sceVideoOutGetOutputStatus (port size WxH, n buffer sets registered; today's answer M)`.
   - The static `Bc5VideoOutRegisteredSets(cfg)` counts the port's occupied sets, under the port's mutex. The count is
     used only for that line.
   - Both functions have external linkage and a prototype just above them (no header), so `vo0401.cpp` can declare and
     call them.
2. **In `VideoOutGetOutputStatus`** (1910-1911), today's line `status->resolution = (ctx->width >= 3840 || … ? 2u :
   1u);` stays as it is. One statement after it passes that value through `Bc5VideoOutStatusResolution`.

**Off is today's path.** Remove the block and the added statement from the output, and the result is byte-identical to
the input (checked on the laptop). Off, the field keeps today's value. The only additions are a four-entry count and the
one stderr line at the first call. That line is printed in the lean build too, as series e's memory line is.

**On, in a play journal of the second title.** By F354 the title asks once at start, before registering. The line would
read `… on: resolution 2 … (port size 1280x720, 0 buffer sets registered; today's answer 1)`. That is exactly exp
0291's arm B answer, which ran with RT off. Expected effect on this title: none (F354). ASTRO BOT never asks (F67).

The script also asserts what the test's stand-in registration relies on:
- `Impl::Init`'s two lines are the only writes of a port's width or height;
- `RegisterBuffers2` writes `ctx->groups[set_index]`;
- `VideoOutConfig` precedes the block;
- `<atomic>`, `<cstdio>`, `<cstdlib>` and `<cstring>` are included.

## The test, `vo0401.cpp`

**Why the real call cannot run.** `VideoOutGetOutputStatus` needs the driver (`DriverState()` exits without it). The
driver needs a `Graphics::Presenter`, which is built from a `WindowContext` (a window and Vulkan), and its `Impl` starts
the present thread. So there is no safe call without a display. The test calls the two functions the edit adds instead.
They hold the whole switch and the whole answer.

**The 27 checks.**
1. The switch's first read matches the argument.
2. 24 checks over a port's life, for six port sizes: 1280×720 (the launcher's), 1920×1080, 2560×1440, 3840×2160,
   3840×1 and 1×2160.
   - The steps are open (0 sets), set 0 registered (1), set 1 registered (2), and both unregistered (0).
   - This stand-in registration is exact for the answer's inputs: registration changes only the set count, never the
     size (asserted by the script).
   - Expected on: 2 at every step. Expected off: today's class of the size, passed through unchanged.
3. The switch is read once: with the variable set to the other setting, the switch and an answer stay as they were (2
   checks).

**End line.** `vo0401: on|off 27 of 27; end`. It matches box0401.sh's `^$4: on|off \([0-9]*\) of \1\b.*; end$`.

**Build.**
- Compile with the command of `src/graphics/presentation/videoOut.cpp` (compdb output
  `src/CMakeFiles/kyty_emulator.dir/graphics/presentation/videoOut.cpp.o`), i.e. `build0401.py … --gate vo0401.cpp
  <out> --like src/graphics/presentation/videoOut.cpp`. The test includes standard headers only, so any unit's command
  would do.
- Link with every emulator object but `main.cpp.o`, the private `videoOut.cpp.o` in.
- With the shared object the link fails on `Libs::VideoOut::Bc5VideoOutStatusOn()` and `…Resolution(…)`.

**Runtime init.** None. The two functions read only the environment and their own statics. No subsystem, Config, driver
or log is needed.

**Usage.** `KYTY_BC5_VIDEOOUT_STATUS=1 ./vo0401 on`, `=0 ./vo0401 off`, and unset `./vo0401 off`.

## Verified on the laptop

**The script.**
- `python mkvo0401.py <e4/full> <scratch>/vo0401-out` printed `3fa490f762fb6a9612289ef3a4018150
  src/graphics/presentation/videoOut.cpp`.
- Run on its own output, it stopped with "videoOut.cpp has the edit already" and wrote nothing.

**The diff.** Two hunks: 59 lines before `VideoOutGetOutputStatus`, and the 2-line statement.
- Brackets balance: `{}` 375 → 382, `()` 984 → 1022, `[]` 85 → 89.
- The off-path reconstruction is byte-identical to the input.

**Syntax check.**
- Tool: clang++ 22.1.3 from VS 18 (target x86_64-pc-windows-msvc), with `-std=c++20 -Wall -Wextra -Wmissing-prototypes
  -fno-rtti -fno-exceptions`.
- Stand-ins (scratch only, not build inputs):
  - the series' `cmake_config.h`;
  - an empty-ish `pthread.h` and a no-op `tracy/Tracy.hpp`, in
    `C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\vochk\stub-pthread`;
  - fmt 8.1.1 from `refs/Inori_GPCS4` with `FMT_EXCEPTIONS=0`;
  - Vulkan SDK 1.4.341.1 headers and VMA.
- Input and output units: 0 errors. Each has the same two warnings, both from the tree: `Bc5OsdTitleFps` has no
  prototype (516), and `Bc5VideoOutEventName` is unused (398).
- `vo0401.cpp`: 0 errors, 0 warnings.

**Stand-in run.** This is not the box's compiler or objects.
- *Build.* The whole edited unit was compiled to an object and linked with `vo0401.o` by lld-link with
  `/FORCE:UNRESOLVED`. The unit's other 64 references are unresolved and never reached.
- *Results.*
  - `=1 on` and `=yes on`: `vo0401: on 27 of 27; end`.
  - `=0 off`, empty `off` and unset `off`: `vo0401: off 27 of 27; end`.
  - Each run printed the one stderr line, e.g. `[bc5] exp 0401: videoout status on: resolution 2 at the first
    sceVideoOutGetOutputStatus (port size 1280x720, 0 buffer sets registered; today's answer 1)`.
  - A mismatched argument (`=1 off`, `=0 on`, unset `on`) gave rc 2.
- *Unedited unit.* Linked the same way, lld reported exactly the test's two functions among the undefined symbols.
- *Mutants.*
  - sharpemu-like (2 only with 0 sets, today's answer once a set is registered; the stand-in keeps the port size, so
    this is sharpemu's rule for a title whose buffers are the port size): on failed 6 of 27 (1280×720, 1920×1080 and 2560×1440, each at 1 and 2 sets);
    off passed.
  - The switch not cached: on and off each failed 2 of 27 (the read-once checks).
- *The link* resolved the test's declarations against the unit's definitions. So the namespace and the parameter types
  match. The MSVC mangling was checked here; the box's Itanium mangling follows the same declarations.

## To wire it into box0401.sh (not done: no edits to existing files)

```
E4_EDITS+=("vo mkvo0401.py src/graphics/presentation/videoOut.cpp:f848f5c6b81196e9722f3c7caf3984ec:3fa490f762fb6a9612289ef3a4018150")
E4_GATES+=("vo0401.cpp src/graphics/presentation/videoOut.cpp KYTY_BC5_VIDEOOUT_STATUS vo0401")
E4_STRS+=(KYTY_BC5_VIDEOOUT_STATUS 'exp 0401: videoout status')
```

Also outside these files:
- The series comment in box0401.sh ("items 7 and 10 were not applicable").
- `test0401.py`'s file list (line 26) and its stand-in expectations.
- Whether `launcher0401.py` passes the switch. It defaults off.

## Doubts

- **After registration is unmeasured in both sources.** The pick (AnyPS5's display-class rule) is reasoned, not
  measured. A title that registers sub-4K buffers and asks afterwards would tell the two apart; neither of our titles
  does.
- **"On" models a 4K TV, not the box's display.** A real PS5 on the DELL U2212HM (1080p, F67) would most likely answer
  1, which is off. That state, a sub-4K display on Automatic, is the one AnyPS5 lists as unmeasured. On is the console
  on a 4K TV, sharpemu's assumption for every Gen5 port. Our presenter scales any buffer size to the window, so the
  title's choice still displays.
- **No effect expected on the second title or on ASTRO BOT** (F354, F67). The switch is for other titles, per the
  maintainer's rule. Exp 0291's arm B ran with RT off and one run per arm. A check run now would be RT on (the
  2026-10-28 rule).
- **The meaning of 1 and 2** is still only "below 4K" and "4K" by everyone's comparison (TODO(verify) in exp 0291).
  AnyPS5 names them `VIDEO_OUT_RESOLUTION_1080P` and `_2160P`, which is no Sony source.
- **The 1440p (WQHD) case.** The title imports `sceVideoOutAllowOutputResolutionWqhdDetection` (exp 0327's stub list,
  registered in exp 0329). What
  `resolution` a console reports on a 1440p output is unmeasured (AnyPS5's note). With the switch on it is 2.
- **`sceVideoOutGetOutputStatusWithVrr`** (`gWT7X8H0bYs`) is not registered by our host, and the title does not import
  it. Not ported. If a title needs it, AnyPS5's 80-byte form (the first 48 bytes are this status) is the model.
- **Not compiled on the box.** The box's compiler and flags (`-Werror`?) may differ from clang 22 on Windows.
  `std::atomic_bool` and the `%u` casts are portable. The stderr line is printed under the port's mutex, once.
- **The set count runs on every call, even off.** It is 4 entries, and the title calls once (F354).

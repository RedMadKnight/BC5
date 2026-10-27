# 0337 — a system language setting for the emulated console, as the PS5's Settings > System > Language

*Number claimed by the cloud supervisor, 2026-10-26 22:34. The maintainer: "Dodaj równolegle zadanie - dodanie w konsoli
wyboru języka jakim domyślnie emulator się posługuje tak jak w ps5".*

**Question.** Can the maintainer choose the console's system language, as on the PS5, so that the second title starts
in that language? Does the title take it?

**Known before this experiment.**
- **The title reads the language once, at start.**
  - It calls `sceSystemServiceParamGetInt` with `PARAM_ID_LANG` (1); the reply was 1, English (United States).
  - Exp 0046's stderr trace ("bc5 system param 1 -> 1") shows this in every recent session, for example exp 0336 R1.
- **What the tree already has** (`src/libs/libSystemService.cpp:113` at f266548):
  - the reply is `Config::GetConsoleLanguage()`, set by `--console-language <0..29>` (`src/main.cpp:151`; default 1,
    `Config::MAX_CONSOLE_LANGUAGE` 29, `src/common/emulatorConfig.h:58–59`);
  - the numbering's names are in KytyPlus's Qt launcher (`launcher/src/configurationEditDialog.cpp:34–65`), which this
    project does not build (`kyty_emulator` only);
  - so no setting reached the user. The launchers do not pass `--console-language`.
- **The settings live in the input configuration** (`KYTY_BC5_INPUT_CONFIG`, `input.cfg`). The settings overlay (F2,
  `settingsOverlay.cpp`) edits and saves it; its Video tab saves `RenderScale.<TITLE_ID>`. The parser stops on the first
  line it does not know (`hostInput.cpp` `InputMap::Load`).

**Setup.**
- **`patch0337.py`** (four md5-checked files; `raw/patch_0337.diff`):
  - `hostInput.cpp`:
    - `SystemLanguage=<name|number>` in the input configuration, global like the console's setting (not per title).
      A name is compared on its letters and digits in any case (`Polish`, `polish`, `english-united-states`); a number
      is 0–29. Anything else fails the line, as the file's other keys do.
    - It is written back by name.
    - `HostInputSystemLanguage()` returns it, or −1. Before the input map exists, it reads the file alone, without the
      map's side effects, because the title may ask before the window does.
    - The language list (`HostInputLanguageName`, `…Count`, `…FromName`) is the launcher's, in the same order.
  - `hostInput.h`: those declarations (added only).
  - `libSystemService.cpp`: `PARAM_ID_LANG` answers `SystemLanguage` when it is set, else `--console-language` as
    before.
  - `settingsOverlay.cpp`: a **System** tab in the settings overlay.
    - It holds a list of the 30 languages, Save and Close.
    - The text says that games read the language when they start: Save, then Restart game (Video tab). The console
      also restarts applications for a language change.
- **Checked offline:** the name parser in a harness (clang and g++, `-Wall -Wextra -Werror`):
  - "Polish", "polish", "POLISH" and "16" → 16;
  - "english-united-states" → 1; "english (united kingdom)" → 18; "Chinese (Simplified)" → 11;
  - "30", "-1", "xx" and "" → −1.
- **Built** (`run0337.sh build`, `build0337.py`, 22:37–22:38): three units, with the private sources first on the
  include path for the patched header, plus a link from the shared normal objects (4a146894). The result is
  `~/bc5-work/exp0337/kyty_emulator` **ea557b2c**. Its 2 warnings are the tree's `stringUtils.h` deprecation.
- **Run L1** (`s6n0337.sh`, exp 0336's chain): the S6N route with RT off, 240 s, private working directory, saves and
  learned file. The private input configuration is the maintainer's `input.cfg` with RT off and
  `SystemLanguage=Polish` (`raw/L1-input-config.diff`, the title ID redacted). The live saves (5383c9deb3c38e9e) were
  compared only.

**Result (L1, 22:39:15–22:43:28).**
- **The title received Polish:** `bc5 system param 1 -> 16` (`raw/L1-system-params.txt`); every earlier session read
  `-> 1`. Its other parameters were as before (2 → 1, 3 → 1, 100, 208 and 210 → 0).
- **The run passed:** 240 s at 34.2 flips/s (median 34.7 per 10 s, start-up included), with no crash line, kernel GPU
  line, TIMEOUT or devcoredump. The live saves were unchanged; the launcher and bc5-mount were gone afterwards.
- **Not checked here:**
  - the overlay's System tab, which was compiled but not clicked;
  - the language the title's menus show. Screenshots stay on the box (exp 0299's rule), so the maintainer's eyes are
    the check.

**Verdict.**
- The setting works end to end: a `SystemLanguage` line reaches the title's language query, and the title starts with
  the chosen language's code.
- **Before integration, `SystemLanguage` must not go into the shared `input.cfg`.** Every binary built before this
  patch, including the shared builds and the test shortcut's private binary (exp 0332's, the shared objects otherwise),
  rejects the unknown line and stops at start. The 0302 binary did the same with `MangoHud.…`.
- After integration into both shared builds (D19, the maintainer's yes), the line is safe for every launcher that uses
  them. The test shortcut would then need a rebuilt private binary.

**Addendum (2026-10-27, after the integration, F411).** On the maintainer's "Integracja języka. Wprowadzenie poprawek
do wszystkich buildow" (BOX-QUEUE 209), `int0337.sh` ran at 07:36 (`raw/int.out`, `raw/integration/`). It used exp
0338's steps.
- **Guards:** the four tree files still had the md5s `patch0337.py` checks, since exp 0338 did not touch them. Both
  shared binaries were at their post-0338 md5s, and the private build ea557b2c with its L1 pass was there.
- **The diff** (251 lines) was made from the tree's files and the private build's copies. `git apply --check` and
  `git apply` succeeded, and each file then equalled the copy ea557b2c was built from.
- **Both shared builds were rebuilt.** The normal build compiled 5 units. There were no errors; the 3 warnings are in
  older code.

  | build | before | after |
  |---|---|---|
  | normal | 21e8bd22 (exp 0338) | **9382b1e9** |
  | lean | 379a92b8 (exp 0338) | **1860613a** |
- **Patch 0001 on main** is the tree's diff after the integration: md5 3b7e88b8, 96 files. Against main's previous copy,
  only the four integrated files differ.
- **The undo:** copy back the two binaries and four files from `~/bc5-work/exp0337/integration/`, then rebuild both.
- **`SystemLanguage` is now safe in the shared `input.cfg`** for every launcher on the shared builds.
  - It is not in the file yet: the language is the maintainer's choice, in the overlay's System tab, or as a line.
  - The test shortcut runs exp 0332's private binary, without exps 0337 and 0338. It reads its own
    `exp0334/input-rton.cfg` (`run0334.sh`), so a line in `input.cfg` does not reach it.
- Not run yet: a session on the integrated builds.

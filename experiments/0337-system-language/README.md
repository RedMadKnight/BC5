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

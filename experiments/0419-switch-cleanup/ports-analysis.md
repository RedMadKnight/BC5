# Experiment 0419: the 23 library words, what they do at load today (for "built in, run only when the title calls")

The maintainer, 2026-11-13: "Porty bibliotek systemowych => wbudowane, ale uruchamiane tylko jeżeli gra będzie wołać".
Read in candidate F's tree by a subagent (file:line are that tree's); the mechanism lines were not all re-read by
hand, so this is a reading to check at the edit, not a test. Nothing is built.

## The mechanism

- `libs/libs.cpp:248-276`, table `Bc5Tables::TABLES[]` (25 rows `{env, item, init}`); `On()` (282-303) reads each word
  with `getenv` (on = set, non-empty, not "0") and `LoadSwitched` (306-313) calls the row's `init`, once, at process
  start, before the title's ELF is loaded (`emulator.cpp:252`). Each unit also has its own `Bc5...On()` with a second
  `getenv` of the same word, which decides held stubs and the ported branch inside the functions.
  `KYTY_BC5_LOAD_NPAUTH` is not in that table: `libs/libNet.cpp:2122` adds five NIDs to the always-loaded table.
- "On" only adds records to the host's symbol database. **The host's table wins over a guest module's exports**
  (`loader/runtimeLinker.cpp:2126`: the host is asked first; the guest's exports only when it has none). A title that
  never imports a library is unaffected except for more records and one stderr line per table: guest `.sprx` loading
  does not consult the database. A title that DOES import one gets the ported answers instead of a no-op stub or the
  guest module's code: that is the behaviour change of "always on", and it is what the proof on both titles must cover.
- No NID collides with another table's, except the nine voice-port NIDs (libVoice against libAudio), which the
  words keep exclusive.

## Per word

| Word | At registration, besides function pointers | Verdict |
|---|---|---|
| CAMERA, COMPANIONHTTPD, COMPANIONUTIL, DISCMAP, GAMELIVESTREAMING, HMD, INVITATIONDIALOG, MOVE, NPAUTH, NPPARTNER, NPPARTY, NPSNSFACEBOOK, NPTUS, SCREENSHOT, SHAREPLAY, ULOBJMGR, VOICE, VRTRACKER, WEBBROWSERDIALOG (19) | one stderr line each; no namespace-scope object with a constructor, no thread, socket, file or device; state is function-local, made on the first call (SCREENSHOT opens the title's own path read-only inside a call) | pure table: nothing runs until called |
| USBD | the line, and `(void)Bc5UsbAllowList();` (`libs/libUsbd.cpp:2977-2978`): the allow list is parsed (two small heap objects, one line). No `dlopen` here: libusb is loaded only inside `sceUsbdInit` and only when the list is not empty | the one start-up side effect: remove that call (the list is already read lazily at its three users) |
| `KYTY_BC5_VOICE_PORTS` | not a table load: nine more NIDs in the always-loaded Voice table, and port ids become the console's (0-127 instead of 1-254; a 129th port refused) | acts only inside calls |
| `KYTY_BC5_NPTUS_FRIENDS_RUN` | changes the argument-check results of six NpTus call pairs (the firmware run's values) | acts only inside calls |
| `KYTY_BC5_USBD_ALLOW` | a LIST of host USB devices (`vvvv:pppp,...`), not a flag; empty = no host USB access and libusb never loaded | **stays a value** (configuration, default empty): "always on" has no meaning for it |

Nothing in these units touches rendering, VideoOut or GPU submission (grep; no hook). The hang of run r7all was not
attributed to them (`undecided-plan.md`).

## The change for candidate G

- `libs/libs.cpp`: rows 6-24 called unconditionally; each unit's `Bc5...On()` returns true with no `getenv` and no
  line; `libs/libNet.cpp:2197` loses its `if`; `Bc5VoicePortsOn()`, `Bc5VoicePortsSwitch()`, `Bc5NtuRunOn()` return true.
- `libs/libUsbd.cpp:2977-2979`: the eager `Bc5UsbAllowList()` call goes. `KYTY_BC5_USBD_ALLOW` stays, read on first use.
- 22 words leave; one (`USBD_ALLOW`) is reclassified as configuration.
- Proof owed: both titles with all of it built in, start and walk (ASTRO BOT x3). The six tables that are already on
  for the second title only (`ZLIB`, `JPEG`, `IME`, `NPCOMMON`, `NPMANAGER`, `NPTROPHY`) are NOT part of this: they
  are among the twenty words of which four or more together end ASTRO BOT at 5-6 s (exp 0413), cause not found.

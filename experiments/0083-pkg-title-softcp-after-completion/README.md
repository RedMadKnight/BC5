# 0083 — the soft CP of IB-packet submissions after completion: dialog fixed, menu not

**Question.** With asynchronous submission, the host's soft CP runs an IB-packet submission
(`submit_ib_packet`) right after `Direct::submit`. Its `EVFILT_GRAPHICS` (EOP) events, and the
writes of packets the filter dropped, therefore reach the game before the GPU has done the work.
`submit_raw` posts the soft CP to the completion thread instead. Does the same for IB packets
stop the second title's text race under deferred flips (experiments 0080–0082)?

**Setup.**
- KytyPlus patch: `BC5_DIRECT_SOFTCP_POST_IB=1` (off by default) makes `submit_ib_packet` post
  the soft CP behind its job, with the GPU-executed marks, as `submit_raw` does.
- Run 335 (`run335.sh`, 2026-10-14 11:27): run 327's settings, flips deferred, heavy probe off,
  plus the knob.

**Result.**
- The screen-reader dialog's text is complete. This is the first time with deferred flips and no
  heavy probe; it was broken in 3 of 3 such runs.
- The Initial setup menu is as in runs 327 and 334: the title reads "IN T AL SETUP", the
  description and the icon are missing, and "Start" is shown pixelated.
- 24.9 fps, no timeout.

**Verdict.** Partly passed:
- Early EOP events are part of the race. The dialog depends on them.
- The menu still needs undeferred flips (run 333), so something else also runs ahead. The knob
  stays, off by default.
- The practical fix for now is undeferred flips for the second title only, at about 19 fps in
  the menu instead of about 25 (run 333).

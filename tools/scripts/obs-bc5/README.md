# OBS Studio profile "BC5" for recordings on the BC-250

The box has no working VA-API video encoder (`vainfo` fails on the BC-250, 2026-10-21), so OBS
encodes in software: x264, preset `veryfast`, CRF 22, 1920×1080 at 30 frames a second (half the
encoding work of 60; the second title runs ~27–30 in its night scenes), MKV (survives a crash;
File > Remux Recordings makes an MP4), AAC 192 kb/s, to `~/Wideo/BC5`. If the game's frame rate
drops while recording, use preset `superfast` or `ultrafast` (Settings > Output > Recording).

On the dev box OBS is the Flathub app `com.obsproject.Studio` (user installation) and this profile
lives in `~/.var/app/com.obsproject.Studio/config/obs-studio/basic/profiles/BC5/`. Use it with the
"BC5 emulator (MangoHud)" shortcut (`BC5_MANGOHUD=1`, see `../mangohud-bc5.conf`): MangoHud's
hardware figures top left and the title's frame rate top right are drawn into the game's frames, so
a window capture records them.

First use: Profile > BC5; in Sources, + > Screen Capture (PipeWire) and pick the emulator window in
the dialog (OBS remembers it); Desktop Audio records what goes to the headset. Start Recording.

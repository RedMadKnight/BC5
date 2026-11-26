#!/usr/bin/env bash
# Lists the audio sinks PipeWire exposes with their channel counts and rates, so the
# "Wireless Controller" four-channel match (F335) can be checked against each pad:
# the DualSense's USB device is 4 ch @ 48 kHz, the DualShock 4's sink is 2 ch @ 32 kHz (F326).
# Read-only; needs no root. Run on the box only after the top session's GO.
set -u
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}   # an ssh shell has no session environment; PipeWire's socket is there
pw-dump 2>/dev/null | python3 - <<'PY'
import json, sys
for o in json.load(sys.stdin):
    info = o.get("info") or {}
    p = info.get("props") or {}
    if p.get("media.class") != "Audio/Sink":
        continue
    fmt = (info.get("params") or {}).get("Format") or [{}]
    f = fmt[0] if fmt else {}
    print("%-62r ch=%s rate=%s name=%s" % (p.get("node.description", "?"), f.get("channels"), f.get("rate"), p.get("node.name")))
PY

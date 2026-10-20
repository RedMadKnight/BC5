#!/usr/bin/env python3
# BC5 (experiment 0180): from a pw-dump file, the emulator's audio streams and the output devices:
# the latency each node asks for (node.latency, pulse buffer attributes) and the quantum in force.
# usage: pw-nodes.py <pw-dump json>
import json, sys
d = json.load(open(sys.argv[1]))
keys = ("node.name", "application.name", "media.name", "node.latency", "node.rate", "node.force-quantum",
        "pulse.attr.tlength", "pulse.attr.minreq", "pulse.attr.prebuf", "pulse.attr.maxlength", "pulse.attr.fragsize",
        "api.alsa.period-size", "api.alsa.period-num", "api.alsa.headroom", "node.driver", "clock.quantum-limit",
        "audio.channels", "audio.format")
for o in d:
    if o.get("type") != "PipeWire:Interface:Node":
        continue
    info = o.get("info") or {}
    p = info.get("props") or {}
    name = str(p.get("node.name", "")) + " " + str(p.get("application.name", ""))
    if "kyty" in name or "Plantronics" in name or "DualSense" in name:
        print(o["id"], info.get("state"), {k: p[k] for k in keys if k in p})
for o in d:
    if o.get("type") == "PipeWire:Interface:Metadata" and (o.get("props") or {}).get("metadata.name") == "settings":
        print("settings:", [(m.get("key"), m.get("value")) for m in o.get("metadata", []) if "quantum" in str(m.get("key"))])

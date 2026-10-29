#!/usr/bin/env python3
# BC5 exp 0372: reads `pw-dump` (stdin) on the box host.
#   streams0372.py device   -> "<id> <profile index> <profile name>" of the DualSense's ALSA card (nothing if absent)
#   streams0372.py streams  -> one line per output audio stream of the emulator (application.process.binary
#                              kyty_emulator): id, object.serial, target.object, node.dont-reconnect/dont-fallback, the
#                              sinks it is linked to; then one line per sink with its id and description.
import json
import sys

objs = json.load(sys.stdin)
by_id = {o["id"]: o for o in objs}


def props(o):
    return (o.get("info") or {}).get("props") or {}


mode = sys.argv[1] if len(sys.argv) > 1 else "streams"
if mode == "device":
    for o in objs:
        if o.get("type") != "PipeWire:Interface:Device":
            continue
        p = props(o)
        name = " ".join(str(p.get(k, "")) for k in ("device.name", "device.description", "device.product.name"))
        if p.get("device.api") == "alsa" and "DualSense" in name:
            prof = ((o.get("info") or {}).get("params") or {}).get("Profile") or [{}]
            print(o["id"], prof[0].get("index", "?"), prof[0].get("name", "?"))
            break
    sys.exit(0)

links = {}
for o in objs:
    if o.get("type") == "PipeWire:Interface:Link":
        i = o.get("info") or {}
        links.setdefault(i.get("output-node-id"), set()).add(i.get("input-node-id"))


def node_name(nid):
    p = props(by_id.get(nid, {}))
    return p.get("node.description") or p.get("node.name") or str(nid)


def binary(p):
    # The stream nodes of a libpipewire client carry client.id; application.process.binary is on the client
    # (run P1's first reads found none on the nodes themselves).
    c = props(by_id.get(int(p.get("client.id", -1)), {})) if str(p.get("client.id", "")).isdigit() else {}
    return p.get("application.process.binary") or c.get("application.process.binary")


n = 0
for o in objs:
    if o.get("type") != "PipeWire:Interface:Node":
        continue
    p = props(o)
    if binary(p) != "kyty_emulator" or not str(p.get("media.class", "")).startswith("Stream/Output/Audio"):
        continue
    n += 1
    state = (o.get("info") or {}).get("state", "?")
    to = "; ".join(f"{t}:{node_name(t)}" for t in sorted(links.get(o["id"], ()))) or "(no link)"
    print(f"stream {o['id']} serial {p.get('object.serial')} state {state} ch {p.get('audio.channels', '?')}"
          f" target.object={p.get('target.object', '-')} dont-reconnect={p.get('node.dont-reconnect', '-')}"
          f" dont-fallback={p.get('node.dont-fallback', '-')} -> {to}")
print(f"{n} emulator output streams")
for o in objs:
    if o.get("type") == "PipeWire:Interface:Node" and props(o).get("media.class") == "Audio/Sink":
        print(f"sink {o['id']} {props(o).get('node.description', props(o).get('node.name'))}")

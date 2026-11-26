#!/usr/bin/env python3
"""Exp 0391: classify one software replug run from the runner's files; fails closed (LESSONS R07, R18).
usage: check0391.py run <tag> <pulls|late> <runner rc> <raw dir>
Prints its reasons and ends with one line:  CLASS <class> mode <pulls|late> pulls <n>
Classes: PASS, FAIL, NO_TEST (the run passed but no pull happened: no DualSense card, or the replug script never got to
its sequence), INVALID (a file of this run is missing). Exit 0 for PASS or NO_TEST, 1 for FAIL or INVALID, 2 for bad arguments.
What PASS needs, each from this run's own files:
  - the S6N run's verdict is "pass" (s6n0391.sh: no crash, kernel line, TIMEOUT, devcoredump, RT-off line; the route read);
  - the replug sequence ran to "sequence done" with the expected number of pulls (3 for pulls, 1 for late);
  - in every pw-dump read, every emulator stream whose target.object is the DualSense sink is linked to a DualSense sink or
    to nothing: never to another sink (exp 0372's question);
  - after every pull the host log shows the port's "closed (…)" and then "opened on DualSense … after an output device was
    added" (read from the replug file's tails, so no clock mapping is needed);
  - no "(pad) … device playing" trace line while the profile was off (the trace's t is mapped to the box clock from the first
    "closed" line, which follows the profile change within ~50 ms; the window is shrunk by 1.5 s at each end);
  - no "rumble: pad instance … " failure line (F330's one-shot log).
Reported, not gated: the main port's smallest "held" and SDL queue in the 3 s after each reopen (exp 0372 saw a dip to 0 ms
of queue, "probably one short gap per replug"), the rumble write count, the frame rate of the summary."""
import os, re, sys

sys.dont_write_bytecode = True


def main():
    if len(sys.argv) != 6 or sys.argv[1] != "run":
        print(__doc__)
        return 2
    tag, mode, rc, raw = sys.argv[2:6]
    if mode not in ("pulls", "late"):
        print("the mode is pulls or late")
        return 2
    want_pulls = 3 if mode == "pulls" else 1
    reasons = []
    files = {}
    for suffix in ("verdict", "end", "replug", "audio-lines", "summary"):
        p = os.path.join(raw, "%s-%s.txt" % (tag, suffix))
        try:
            files[suffix] = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            files[suffix] = None
            reasons.append("missing %s" % os.path.basename(p))
    if reasons:
        for r in reasons:
            print(r)
        print("CLASS INVALID mode %s pulls 0" % mode)
        return 1
    print("runner rc %s; %s; %s" % (rc, files["end"].strip(), files["summary"].strip()[:400]))
    verdict = files["verdict"].strip()
    fail = []
    if verdict != "pass":
        fail.append("the S6N run's verdict is '%s'" % verdict)

    # --- the replug file: timestamps "HH:MM:SS.mmm ...", profile changes, reads with the pw-dump streams and the log tails
    rep = files["replug"].splitlines()
    ts = re.compile(r"^(\d\d):(\d\d):(\d\d)\.(\d\d\d) (.*)$")

    def clock(m):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0

    no_card = any("no DualSense ALSA card" in l for l in rep)
    profile = []  # (clock, index)
    for l in rep:
        m = ts.match(l)
        if m:
            pm = re.match(r"profile -> (\d+)", m.group(5))
            if pm:
                profile.append((clock(m), int(pm.group(1))))
    pulls = []  # (off_clock, on_clock)
    i = 0
    while i < len(profile):
        if profile[i][1] == 0:
            j = i + 1
            while j < len(profile) and profile[j][1] == 0:
                j += 1
            if j < len(profile):
                pulls.append((profile[i][0], profile[j][0]))
                i = j + 1
                continue
            else:
                fail.append("the profile was turned off at %.3f and never back on" % profile[i][0])
        i += 1
    if mode == "late" and pulls:
        pulls = pulls[1:]  # the first off/on is the late plug itself, not a pull
    done = any("sequence done" in l for l in rep)
    restored = any("restored: DualSense profile" in l for l in rep)
    print("replug: pulls %d (want %d), sequence done %s, profile restored %s, no DualSense card %s" % (len(pulls), want_pulls, done, restored, no_card))
    if no_card or not pulls or not done:
        cls = "NO_TEST" if not fail else "FAIL"
        for r in fail:
            print("FAIL: " + r)
        print("CLASS %s mode %s pulls %d" % (cls, mode, len(pulls)))
        return 0 if cls == "NO_TEST" else 1
    if len(pulls) != want_pulls:
        fail.append("%d pulls, want %d" % (len(pulls), want_pulls))
    if not restored:
        fail.append("the profile restore line is missing")

    # --- streams in every read: a pad stream is linked to a DualSense sink or to nothing
    sinks = {}
    for l in rep:
        m = re.match(r"sink (\d+) (.*)$", l)
        if m:
            sinks[m.group(1)] = m.group(2)
    reads = 0
    pad_streams = 0
    wrong = []
    for l in rep:
        m = re.match(r"stream (\d+) serial (\S+) state (\S+) ch (\S+) target\.object=(\S+) .* -> (.*)$", l)
        if not m:
            continue
        reads += 1
        if "DualSense" not in m.group(5):
            continue
        pad_streams += 1
        links = m.group(6).strip()
        if links == "(no link)":
            continue
        for part in links.split("; "):
            sid, _, name = part.partition(":")
            if "DualSense" not in name and "DualSense" not in sinks.get(sid, ""):
                wrong.append("stream %s serial %s -> %s" % (m.group(1), m.group(2), part))
    print("stream lines %d, pad streams %d, pad streams on another sink %d" % (reads, pad_streams, len(wrong)))
    for w in wrong[:10]:
        print("  " + w)
    if wrong:
        fail.append("%d pad stream reads linked to a sink other than the DualSense" % len(wrong))

    # --- per pull: closed, then opened after an output device was added, in the tails between the off and the read after the on
    # The tails are printed by the replug script after each read, interleaved with the timestamped lines; attribute a tail
    # line to the last timestamped line before it.
    events = []  # (clock, kind, text)
    last = None
    for l in rep:
        m = ts.match(l)
        if m:
            last = clock(m)
            continue
        if last is None:
            continue
        if "closed (" in l:
            events.append((last, "closed", l))
        elif "opened on" in l and "after" in l:
            events.append((last, "opened", l))
    for k, (off, on) in enumerate(pulls, 1):
        closed = [e for e in events if e[1] == "closed" and off <= e[0] <= on + 40]
        opened = [e for e in events if e[1] == "opened" and on <= e[0] <= on + 40]
        print("pull %d: off %.3f on %.3f (%.1f s): closed lines %d, reopened lines %d" % (k, off, on, on - off, len(closed), len(opened)))
        for e in (closed + opened)[:4]:
            print("  " + e[2].strip()[:200])
        if not closed:
            fail.append("pull %d: no 'closed (…)' line in the reads after it" % k)
        if not opened:
            fail.append("pull %d: no 'opened on … after' line in the reads after it" % k)

    # --- the trace while the controller was off: map t to the box clock from the first "closed" line's t and the first off
    au = files["audio-lines"].splitlines()
    tre = re.compile(r"\bt (\d+\.\d+) s\b")
    offset = None
    for l in au:
        if "closed (" in l:
            m = tre.search(l)
            if m and pulls:
                offset = pulls[0][0] - float(m.group(1))
                break
    if offset is None:
        fail.append("no 'closed (…)' line in the audio lines, so the trace cannot be placed on the box clock")
    else:
        bad = []
        for l in au:
            if "(pad)" not in l or "device playing" not in l:
                continue
            m = tre.search(l)
            if not m:
                continue
            c = float(m.group(1)) + offset
            for off, on in pulls:
                if off + 1.5 < c < on - 0.5:
                    bad.append(l.strip()[:160])
        print("trace offset %.3f s; '(pad) … device playing' lines inside a pull: %d" % (offset, len(bad)))
        for b in bad[:5]:
            print("  " + b)
        if bad:
            fail.append("%d pad trace lines say 'device playing' while the profile was off" % len(bad))
        # the main port after each reopen: smallest held and queue in the 3 s after the on
        for k, (off, on) in enumerate(pulls, 1):
            held = []
            queued = []
            for l in au:
                if "(pad)" in l or "audio trace:" not in l:
                    continue
                m = tre.search(l)
                if not m:
                    continue
                c = float(m.group(1)) + offset
                if on <= c <= on + 3.5:
                    h = re.search(r"held ([\d.]+) ms", l)
                    q = re.search(r"\((\d+)-(\d+) ms\)", l)
                    if h:
                        held.append(float(h.group(1)))
                    if q:
                        queued.append(int(q.group(1)))
            print("pull %d: main port in the 3 s after the reopen: held min %s ms, queue min %s ms (%d lines)" %
                  (k, min(held) if held else "?", min(queued) if queued else "?", len(held)))
    rumble_fail = [l for l in au if "rumble: pad instance" in l]
    rumble_writes = sum(1 for l in au if "input trace: rumble" in l)
    dropped = sum(1 for l in au if "pad route:" in l and "dropped" in l)
    print("rumble writes %d, rumble failure lines %d, 'pad route … dropped' lines %d" % (rumble_writes, len(rumble_fail), dropped))
    for l in rumble_fail[:3]:
        print("  " + l.strip()[:160])
    if rumble_fail:
        fail.append("%d rumble failure lines" % len(rumble_fail))

    for r in fail:
        print("FAIL: " + r)
    cls = "PASS" if not fail else "FAIL"
    print("CLASS %s mode %s pulls %d" % (cls, mode, len(pulls)))
    return 0 if cls == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

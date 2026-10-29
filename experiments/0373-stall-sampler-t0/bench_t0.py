# SPDX-License-Identifier: GPL-2.0-only
"""BC5 exp 0373 (T0): the sampler's own Python cost, on whatever machine runs it, with no device.

    python experiments/0373-stall-sampler-t0/bench_t0.py

1. one healthy poll (parse a 20-ring amdgpu_fence_info text, update the clocks, no stall): the steady cost at 40 Hz;
2. the user-space side of one 1,600-slot scan (unpack and filter 68-byte records from a fake device that answers at
   once): a lower bound, the kernel's 17 SQ_IND reads per slot come on top (T1 measures the whole);
3. the event summary of five samples of 800 valid waves (decoded once per sample, then cached), as the writer thread
   formats it.
The numbers are for this machine; the box's Zen 2 cores differ. T2 measures the real cost against the soak's flips/s.
"""
import collections
import importlib.machinery
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "..", "tools", "scripts", "gpu-stall-sampler", "bc5-gpu-stall-sampler")
_loader = importlib.machinery.SourceFileLoader("bc5_gpu_stall_sampler", TOOL)
S = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(S)


def best(fn, n, reps=5):
    out = []
    for _ in range(reps):
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        out.append((time.perf_counter() - t0) / n)
    return min(out)


class NullWriter:
    def submit(self, task):
        pass


def main():
    print("python %s on %s" % (sys.version.split()[0], sys.platform))
    # 1. a healthy poll: 20 rings as on the box (gfx, 8 compute, kiq, 2 sdma, vcn/jpeg...), all moving
    clock = S.FakeClock()
    dev = S.FakeDevice(clock)
    names = ["gfx_0.0.0"] + ["comp_1.%d.%d" % (p, q) for p in range(4) for q in range(2)] + \
        ["kiq_0.2.1.0", "sdma0", "sdma1", "vcn_dec", "vcn_enc0", "vcn_enc1", "jpeg_dec", "mes_kiq", "x1", "x2", "x3"]
    for i, n in enumerate(names):
        dev.fences[n] = (0x1000 + i, 0x1000 + i)
    eng = S.Engine(dev, NullWriter(), S.Config(), clock=clock, wall=lambda: 1.8e9, log=lambda s: None)
    state = {"k": 0}

    def poll():
        state["k"] += 1
        k = state["k"]
        dev.fences["gfx_0.0.0"] = (k, k + (k & 1))
        dev.fences["comp_1.0.0"] = (k, k)
        clock.t += 0.025
        eng.tick(clock.t)
    t = best(poll, 2000)
    print("1. healthy poll: %.1f us per poll, %.2f%% of one core at 40 Hz" % (t * 1e6, t * 40 * 100))

    # 2. the user-space side of a scan
    dev2 = S.FakeDevice(S.FakeClock(), scan_cost=0.0)
    dev2.busy = S.busy_slots(800, 0x11D049AA00)
    cfg = S.Config()
    t = best(lambda: S.take_sample(dev2, cfg, "stall", 0, 0, "", True), 20)
    print("2. scan, user-space side: %.1f ms per 1,600 slots (800 valid), %.1f us per slot" % (t * 1e3, t / 1600 * 1e6))

    # 3. the summary of five samples
    smps = []
    for i in range(5):
        s = S.take_sample(dev2, cfg, "stall", i, i, "", True)
        s.idx = i + 1
        smps.append(s)
    ep = S.Episode(1, 0.0)
    ep.samples = smps
    ep.event, ep.event_reason = "event-bench", "bench"
    st = S.Stall("gfx_0.0.0", 0.0, 1, 2, ep)
    st.samples = [(i + 1, 0.5 + 0.3 * i) for i in range(5)]
    ep.stalls = [st]
    t0 = time.perf_counter()
    eng._summary(ep)
    first = time.perf_counter() - t0
    t = best(lambda: eng._summary(ep), 5)
    print("3. event summary, 5 samples x 800 waves: %.1f ms the first time (decodes), %.1f ms after (cached)"
          % (first * 1e3, t * 1e3))
    files = sum(len(S.fmt_regs(s)) + len(S.fmt_waves_txt(s)) + len(S.pack_waves_bin(s)) for s in smps)
    print("   event size: %d KB for the five samples' files" % (files // 1024))


if __name__ == "__main__":
    main()

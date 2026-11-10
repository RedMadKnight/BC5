#!/usr/bin/env python3
# BC5 exp 0381: a model of the proposed tracker contract (PLAN-chain-walkers.md), not code that runs in the host. It checks
# the contract against the ground truth: every way through a synthetic stream, by brute force.
#
# The contract: a register the tracker calls CERTAIN holds that value at EVERY end of the stream. Anything else is
# UNCERTAIN, and a safe prefix leaves it out.
#   - one value per register, plus one flag, as a small change to the tracker would have; no copy of the state per way;
#   - an unconditional CHAIN follows the target and drops the tail;
#   - under a COND_EXEC a write makes the register uncertain, unless it writes the certain value already there;
#   - a conditional CHAIN: the target is walked as conditional, and so is the rest of this buffer;
#   - what cannot be followed (unreadable, cycle, limit) could write anything: every register becomes uncertain, and a
#     later plain write makes that one register certain again.
#
# Packets are tuples, and a COND_EXEC's skip counts packets here: this is a model of control flow, not a decoder.
#   ("set", reg, value)  ("call", addr)  ("chain", addr)  ("cond", skip)
# usage: python trackermodel0381.py   (runs the named cases and the random check)
import random
import sys

DEPTH = 8
ANY = "?"  # what a register holds after something that could not be followed


class Tracker:
    def __init__(self, mem):
        self.mem = mem
        self.val = {}
        self.unc = set()
        self.active = []

    def clobber(self):
        self.unc = set(self.val)

    def write(self, reg, v, conditional):
        if conditional:
            if reg in self.val and reg not in self.unc and self.val[reg] == v:
                return
            self.val[reg] = v
            self.unc.add(reg)
        else:
            self.val[reg] = v
            self.unc.discard(reg)

    def followable(self, addr):
        return addr in self.mem and addr not in self.active and len(self.active) < DEPTH

    def walk(self, ib, conditional=False):
        until = -1  # the packets below this index are under a COND_EXEC
        for i, p in enumerate(ib):
            c = conditional or i < until
            if p[0] == "set":
                self.write(p[1], p[2], c)
            elif p[0] == "cond":
                until = max(until, i + 1 + p[1])
            elif p[0] in ("call", "chain"):
                if self.followable(p[1]):
                    self.active.append(p[1])
                    self.walk(self.mem[p[1]], c)
                    self.active.pop()
                else:
                    self.clobber()
                if p[0] == "chain":
                    if not c:
                        return  # the tail is dead
                    conditional = True  # taken: the tail does not run; not taken: it does

    def safe_prefix(self):
        return {r: v for r, v in self.val.items() if r not in self.unc}


class Rejected(Tracker):
    """The first plan: a conditional CHAIN follows the target and keeps the tail, and what cannot be followed is only counted."""

    def clobber(self):
        pass

    def walk(self, ib, conditional=False):
        until = -1
        for i, p in enumerate(ib):
            c = i < until
            if p[0] == "set":
                self.write(p[1], p[2], False)
            elif p[0] == "cond":
                until = max(until, i + 1 + p[1])
            elif p[0] in ("call", "chain"):
                if self.followable(p[1]):
                    self.active.append(p[1])
                    self.walk(self.mem[p[1]])
                    self.active.pop()
                if p[0] == "chain" and not c:
                    return


class Today(Tracker):
    """The tracker as it is: every IB is a call, every COND_EXEC is taken, nothing is ever uncertain."""

    def clobber(self):
        pass

    def walk(self, ib, conditional=False):
        for p in ib:
            if p[0] == "set":
                self.write(p[1], p[2], False)
            elif p[0] in ("call", "chain") and self.followable(p[1]):
                self.active.append(p[1])
                self.walk(self.mem[p[1]])
                self.active.pop()


def ends(ib, regs, mem, active=()):
    """Every state a way through ib can end in, with the flag that says it left through a CHAIN or not: the truth."""
    out = []

    def run(i, st):
        if i >= len(ib):
            out.append(st)
            return
        p = ib[i]
        if p[0] == "set":
            run(i + 1, {**st, p[1]: p[2]})
        elif p[0] == "cond":
            run(i + 1, st)
            run(i + 1 + p[1], st)
        else:
            followable = p[1] in mem and p[1] not in active and len(active) < DEPTH
            # Something that cannot be followed may leave any value: one way untouched, one way all overwritten.
            afters = ends(mem[p[1]], st, mem, active + (p[1],)) if followable else [st, {r: ANY for r in st}]
            for a in afters:
                if p[0] == "chain":
                    out.append(a)
                else:
                    run(i + 1, a)

    run(0, dict(regs))
    return out


def sound(ib, mem, cls=Tracker):
    t = cls(mem)
    t.walk(ib)
    all_ends = ends(ib, {}, mem)
    for reg, v in t.safe_prefix().items():
        for e in all_ends:
            if e.get(reg) != v:
                return False, (reg, v, e)
    return True, None


def gen_ib(rng, addrs, n):
    out = []
    for _ in range(n):
        k = rng.random()
        if k < 0.45:
            out.append(("set", rng.randrange(3), rng.randrange(3)))
        elif k < 0.65:
            out.append(("cond", rng.randrange(1, 4)))
        elif k < 0.85:
            out.append(("call", rng.choice(addrs)))
        else:
            out.append(("chain", rng.choice(addrs)))
    return out


def certain(ib, mem):
    t = Tracker(mem)
    t.walk(ib)
    return t.safe_prefix()


def named():
    r0 = ("set", 0, 0x11)
    m = {0x1000: [("set", 0, 0x22)], 0x2000: []}
    cases = [
        ("a call: the tail runs", [("call", 0x1000), ("set", 0, 0x33)], {0: 0x33}),
        ("a CHAIN: the tail is dead", [("chain", 0x1000), ("set", 0, 0x33)], {0: 0x22}),
        ("an unreadable CHAIN: the seed is not vouched for, the tail is dead", [r0, ("chain", 0x9), ("set", 0, 0x33)], {}),
        ("an unreadable CHAIN keeps no other register either", [("set", 1, 5), ("chain", 0x9)], {}),
        ("an unreadable call: a later plain write vouches for that register only", [r0, ("set", 1, 5), ("call", 0x9), ("set", 0, 0x33)], {0: 0x33}),
        ("a conditional CHAIN, ends 0x22 and 0x33: Codex's case", [("cond", 1), ("chain", 0x1000), ("set", 0, 0x33)], {}),
        ("the same with a seed", [r0, ("cond", 1), ("chain", 0x1000), ("set", 0, 0x33)], {}),
        ("a conditional CHAIN with a silent child keeps the seed, the tail does not", [r0, ("cond", 1), ("chain", 0x2000), ("set", 1, 7)], {0: 0x11}),
        ("a conditional call: skipped keeps the seed", [r0, ("cond", 1), ("call", 0x1000)], {}),
        ("a conditional write of the certain value stays certain", [r0, ("cond", 1), ("set", 0, 0x11)], {0: 0x11}),
        ("a plain write after a condition settles it", [r0, ("cond", 1), ("call", 0x1000), ("set", 0, 0x33)], {0: 0x33}),
    ]
    bad = 0
    for name, ib, want in cases:
        got = certain(ib, m)
        ok, why = sound(ib, m)
        good = got == want and ok
        print("%s: %s" % ("ok" if good else "FAIL", name), "" if good else (got, want, why))
        bad += not good
    m2 = dict(m)
    m2[0x5000] = [("chain", 0x5000)]
    m2[0x6000] = [("call", 0x6000), ("set", 1, 5)]
    for name, ib, want in (("a CHAIN cycle", [r0, ("chain", 0x5000)], {}), ("a call cycle, then a plain write", [r0, ("call", 0x6000), ("set", 0, 0x33)], {0: 0x33, 1: 5})):
        got = certain(ib, m2)
        print("%s: %s" % ("ok" if got == want else "FAIL", name), "" if got == want else got)
        bad += got != want
    return bad


def main():
    bad = named()
    rng = random.Random(381)
    n = certain_regs = 0
    for _ in range(40000):
        addrs = [0x1000, 0x2000, 0x3000, 0x9000]
        mem = {a: gen_ib(rng, addrs, rng.randrange(0, 5)) for a in addrs[:3]}
        ib = gen_ib(rng, addrs, rng.randrange(1, 8))
        ok, why = sound(ib, mem)
        n += 1
        certain_regs += len(certain(ib, mem))
        if not ok:
            print("FAIL: unsound", ib, mem, why)
            bad += 1
            if bad > 3:
                break
    print("random streams %d, certain registers claimed %d, unsound %d" % (n, certain_regs, bad))
    # The check must be able to fail: the designs it rejects have to be caught.
    for cls in (Rejected, Today):
        rng = random.Random(381)
        wrong = 0
        for _ in range(4000):
            addrs = [0x1000, 0x2000, 0x3000, 0x9000]
            mem = {a: gen_ib(rng, addrs, rng.randrange(0, 5)) for a in addrs[:3]}
            ib = gen_ib(rng, addrs, rng.randrange(1, 8))
            wrong += not sound(ib, mem, cls)[0]
        print("mutant %s: unsound in %d of 4000 (must not be 0)" % (cls.__name__, wrong))
        bad += wrong == 0
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

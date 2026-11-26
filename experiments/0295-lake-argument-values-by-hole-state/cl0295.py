#!/usr/bin/env python3
# BC5 experiment 0295, added after run W295a: the lake went from patched (shots ts00-ts11) to clean (ts15 on) during the
# run, so its plateaus include clean frames, which pl0295.py leaves unlabelled (clear reads with no family: depth-0
# share <= 0.03). Here the plateaus of pl0295.py's <priv json> are labelled "patched" (in a hole family) or "clean"
# (clear, no family, depth-0 share < 0.03), and the argument values are set against that label:
#  - over pairs of labelled plateaus from different bursts, the share of varying records with equal values, same-label
#    pairs against different-label pairs, permutation null (labels shuffled), split by same and different render size;
#  - per record and dword: the AUC of the value, patched against clean (0.5 = no difference), the largest |AUC - 0.5|
#    against the null of the largest; how many records take values in clean frames that no patched frame has, and back;
#  - the render sizes of each label, since the arguments differ more between sizes than between hole families (pl0295).
# Patched and clean frames come from different parts of the run (bursts b01-b10 and b11-b16), so a slow drift would look
# the same; the bursts' order is printed with each label. Summaries only. Stdlib only.
# usage: python3 -I cl0295.py <priv json> [permutations]
import collections, json, random, sys

d = json.load(open(sys.argv[1]))
nperm = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
rng = random.Random(295)
pls = []
for p in d["plateaus"]:
    lab = "patched" if p["family"] else ("clean" if p["clear"] and p["share"] is not None and p["share"] < 0.03 else None)
    if lab:
        pls.append(dict(p, label=lab, args={int(k, 16): tuple(v) for k, v in p["args"].items()}))
cnt = collections.Counter(p["label"] for p in pls)
print("# %s: %d labelled plateaus (%s)" % (sys.argv[1], len(pls), ", ".join("%s %d" % kv for kv in sorted(cnt.items()))))
for lab in ("patched", "clean"):
    ps = [p for p in pls if p["label"] == lab]
    print("  %s: bursts %s; render sizes %s" % (lab, " ".join(sorted({p["burst"] for p in ps})),
          ", ".join("%s %d" % kv for kv in sorted(collections.Counter(p["size"] for p in ps).items()))))
common = set.intersection(*(set(p["args"]) for p in pls)) if pls else set()
vary = sorted(r for r in common if len({p["args"][r] for p in pls}) > 1)
print("  records read in every labelled plateau %d, varying %d" % (len(common), len(vary)))
pairs = [(p, q) for a, p in enumerate(pls) for q in pls[a + 1:] if p["burst"] != q["burst"]]
eq = [sum(p["args"][r] == q["args"][r] for r in vary) / len(vary) for p, q in pairs] if vary else []


def split(labels):
    s = [e for e, (p, q) in zip(eq, pairs) if labels[p["id"]] == labels[q["id"]]]
    o = [e for e, (p, q) in zip(eq, pairs) if labels[p["id"]] != labels[q["id"]]]
    return (sum(s) / len(s) - sum(o) / len(o)) if s and o else None, s, o


if vary and len(pairs) >= 10:
    labels = {p["id"]: p["label"] for p in pls}
    obs, s, o = split(labels)
    ids, sh, ge = [p["id"] for p in pls], [p["label"] for p in pls], 0
    for _ in range(nperm):
        rng.shuffle(sh)
        v = split(dict(zip(ids, sh)))[0]
        if v is not None and v >= obs:
            ge += 1
    print("  equal varying records per pair: same label %.3f (%d pairs), different labels %.3f (%d pairs); difference %+.3f, permutation p %.4f" % (
        sum(s) / len(s), len(s), sum(o) / len(o), len(o), obs, (1 + ge) / (nperm + 1)))
    for nm, same in (("same label", True), ("different labels", False)):
        a = [e for e, (p, q) in zip(eq, pairs) if (p["label"] == q["label"]) == same and p["size"] == q["size"]]
        b = [e for e, (p, q) in zip(eq, pairs) if (p["label"] == q["label"]) == same and p["size"] != q["size"]]
        print("    %s: same render size %s (%d pairs), different size %s (%d pairs)" % (
            nm, "%.3f" % (sum(a) / len(a)) if a else "-", len(a), "%.3f" % (sum(b) / len(b)) if b else "-", len(b)))


def auc(xs, ys):
    if not xs or not ys:
        return 0.5
    gt = sum((x > y) + 0.5 * (x == y) for x in xs for y in ys)
    return gt / (len(xs) * len(ys))


cells = [(r, k) for r in vary for k in range(4) if len({p["args"][r][k] for p in pls}) > 1]
lab0 = [p["label"] for p in pls]


def aucs(lab):
    out = {}
    for r, k in cells:
        xs = [p["args"][r][k] for p, l in zip(pls, lab) if l == "patched"]
        ys = [p["args"][r][k] for p, l in zip(pls, lab) if l == "clean"]
        out[(r, k)] = auc(xs, ys)
    return out


if cells and cnt["patched"] and cnt["clean"]:
    a0 = aucs(lab0)
    top = sorted(a0.items(), key=lambda kv: -abs(kv[1] - 0.5))
    nmax, sh = [], list(lab0)
    for _ in range(min(nperm, 1000)):
        rng.shuffle(sh)
        nmax.append(max(abs(v - 0.5) for v in aucs(sh).values()))
    nmax.sort()
    print("  per record dword, AUC patched against clean, %d varying dwords; the largest |AUC - 0.5| 8 (null of the largest: median %.3f, 95th percentile %.3f; p of the top %.4f):" % (
        len(cells), nmax[len(nmax) // 2], nmax[int(0.95 * len(nmax))], (1 + sum(1 for v in nmax if v >= abs(top[0][1] - 0.5))) / (len(nmax) + 1)))
    for (r, k), v in top[:8]:
        xs = sorted({p["args"][r][k] for p in pls if p["label"] == "patched"})
        ys = sorted({p["args"][r][k] for p in pls if p["label"] == "clean"})
        print("    %x dword %d: AUC %.3f; distinct values patched %d, clean %d, shared %d" % (r, k, v, len(xs), len(ys), len(set(xs) & set(ys))))
    only_c = [r for r in vary if {p["args"][r] for p in pls if p["label"] == "clean"} - {p["args"][r] for p in pls if p["label"] == "patched"}]
    only_p = [r for r in vary if {p["args"][r] for p in pls if p["label"] == "patched"} - {p["args"][r] for p in pls if p["label"] == "clean"}]
    print("  records with a value in clean frames that no patched frame has: %d of %d; with a patched-only value: %d" % (len(only_c), len(vary), len(only_p)))

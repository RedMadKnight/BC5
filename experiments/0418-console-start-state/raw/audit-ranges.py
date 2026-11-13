import json, re, sys
S = sys.argv[1]
d = json.load(open(S + "/title-regs.json.clean"))
db = json.load(open(S + "/mesa0866/src/amd/registers/gfx10.json"))
names = {}
for m in db["register_mappings"]:
    if "map" in m and "at" in m["map"]:
        names.setdefault(m["map"]["at"], m["name"])
BASE = {"context": 0x28000, "sh": 0xb000, "uconfig": 0x30000}
title = {BASE[r["sp"]] + r["off"] * 4: r for r in d["regs"] if r["sp"] in BASE}
src = open(S + "/mesa0866/src/amd/common/ac_shadowed_regs.c").read()
def table(name):
    m = re.search(r"static const struct ac_reg_range " + name + r"\[\] = \{(.*?)\n\};", src, re.S)
    out = []
    for e in re.findall(r"\{\s*(R_[0-9A-F]{6}_\w+|0x[0-9a-fA-F]+)\s*,\s*(.*?)\s*,?\s*\}", m.group(1), re.S):
        a = int(e[0][2:8], 16) if e[0].startswith("R_") else int(e[0], 16)
        expr = re.sub(r"R_([0-9A-F]{6})_\w+", lambda x: "0x" + x.group(1), e[1])
        out.append((a, eval(expr)))
    return out
for cls, t in (("uconfig", "Nv10UserConfigShadowRange"), ("sh", "Gfx10ShShadowRange"), ("cs-sh", "Gfx10CsShShadowRange"), ("context", "Nv10ContextShadowRange")):
    regs = []
    for a, n in table(t):
        regs += range(a, a + n, 4)
    named = [a for a in regs if a in names]
    miss = [a for a in named if a not in title]
    print(f"\n## {cls} {t}: {len(regs)} addresses, {len(named)} named in gfx10.json, {len(named)-len(miss)} seen, {len(miss)} not seen")
    # collapse user data families
    fam = {}
    for a in miss:
        n = re.sub(r"_\d+$", "_N", names[a])
        fam.setdefault(n, []).append(a)
    print("; ".join(f"{k}×{len(v)}" if len(v) > 1 else f"{k}({v[0]:#x})" for k, v in fam.items())[:2600])
print("\n## title/host writes outside gfx10.json names")
for a, r in sorted(title.items()):
    if a not in names:
        print(hex(a), r["sp"], hex(r["off"]), "n", r["n"], "nv", r["nvals"], [hex(v[0]) for v in r["vals"][:3]], r["kind"])
print("\n## all uconfig seen")
print(", ".join(f"{names.get(a, hex(a))}" for a in sorted(title) if 0x30000 <= a < 0x38000))
print("\n## WRITE_DATA reg", hex(49987), hex(0x30000 + (49987 - 0xc000) * 4), names.get(0x30000 + (49987 - 0xc000) * 4))
print("VGT_SHADER_STAGES_EN", title.get(0x28b54, {}).get("vals"), title.get(0x28b54, {}).get("nvals"))
for a in (0x28000+0x2d5*4,):
    print(hex(a), names.get(a), title.get(a, {}).get("vals"))

import json, re, sys
S = sys.argv[1]
d = json.load(open(S + "/title-regs.json.clean"))
db = json.load(open(S + "/mesa0866/src/amd/registers/gfx10.json"))
names = {}
for m in db["register_mappings"]:
    if "map" in m and "at" in m["map"]:
        names.setdefault(m["map"]["at"], m["name"])
BASE = {"context": 0x28000, "sh": 0xb000, "uconfig": 0x30000}
title = {}
for r in d["regs"]:
    a = BASE[r["sp"]] + r["off"] * 4 if r["sp"] in BASE else None
    if a is not None:
        title[a] = r
M = [
 # addr, class, value text, why
 (0x301ec,"uconfig","0x20","cp coher delay ac_cmdbuf.c:60"),
 (0x30e00,"uconfig","border VA>>8","compute border colour :61"),
 (0x30e04,"uconfig","border VA>>40",":62"),
 (0xb834,"sh","addr32_hi>>8",":64"),
 (0xb858,"sh","cu en",":67"),(0xb85c,"sh","cu en",":67"),(0xb864,"sh","0",":71"),(0xb868,"sh","0",":71"),
 (0xb890,"sh","0",":74"),(0xb894,"sh","0",":75"),(0xb898,"sh","0",":76"),(0xb89c,"sh","0",":77"),
 (0xb9f4,"sh","0",":92"),
 (0xb810,"sh","0","radv_queue:649"),(0xb814,"sh","0",":650"),(0xb818,"sh","0",":651"),
 (0xb860,"sh","tmpring","radv_queue:516"),
 (0xb01c,"sh","CU_EN ffff WL 3f",":439"),(0xb0c0,"sh","soft group, 4 req",":444"),
 (0xb0c8,"sh","0",":447"),(0xb0cc,"sh","0",":448"),(0xb0d0,"sh","0",":449"),(0xb0d4,"sh","0",":450"),
 (0xb104,"sh","CU_EN hi",":454"),(0xb1c0,"sh","0",":457"),
 (0xb1c8,"sh","0",":458"),(0xb1cc,"sh","0",":459"),(0xb1d0,"sh","0",":460"),(0xb1d4,"sh","0",":461"),
 (0xb004,"sh","CU_EN hi",":465"),(0xb404,"sh","CU_EN hi",":470"),
 (0xb2c8,"sh","0",":476"),(0xb2cc,"sh","0",":477"),(0xb2d0,"sh","0",":478"),(0xb2d4,"sh","0",":479"),
 (0xb324,"sh","addr32_hi>>8",":480"),(0xb41c,"sh","CU_EN ffff WL 3f",":483"),
 (0xb4c8,"sh","0",":486"),(0xb4cc,"sh","0",":487"),(0xb4d0,"sh","0",":488"),(0xb4d4,"sh","0",":489"),
 (0xb524,"sh","addr32_hi>>8",":490"),(0xb124,"sh","addr32_hi>>8","radv_queue:732"),
 (0x28038,"context","PUNCHOUT FORCE_OFF",":518"),(0x2807c,"context","cache policy",":521"),
 (0x28080,"context","border VA>>8",":529"),(0x28084,"context","border VA>>40",":530"),
 (0x28410,"context","cache policy",":532"),(0x28830,"context","filter 1",":551"),
 (0x28a18,"context","fui(64)",":554"),(0x28aac,"context","1",":557"),(0x28b50,"context","12,30,24,24,6",":558"),
 (0x28c48,"context","binner",":574"),(0x28c50,"context","512",":593"),(0x28c58,"context","14",":596"),
 (0x28838,"context","0","radv_queue:740"),(0x28a00,"context","8,8","radv :745"),(0x28a04,"context","minmax","radv :746"),
 (0x286d4,"context","point sprite","radv :772"),(0x28be4,"context","vtx cntl","radv :781"),(0x28818,"context","vte","radv :791"),
 (0x28828,"context","1.0","radv :814"),(0x2882c,"context","excl 1,1","si_state:4861"),
 (0x30924,"uconfig","0",":599"),(0x30928,"uconfig","0",":600"),(0x30964,"uconfig","~0",":608"),(0x30968,"uconfig","0",":609"),
 (0x3097c,"uconfig","0",":610"),(0x30988,"uconfig","0",":611"),(0x30a00,"uconfig","0",":613"),(0x30a04,"uconfig","0",":614"),
 (0x30938,"uconfig","tf size","ac_cmdbuf_cp tess_rings"),(0x3093c,"uconfig","hs_offchip","ac_cmdbuf_cp"),(0x30940,"uconfig","tf base","ac_cmdbuf_cp"),(0x30984,"uconfig","tf base hi","ac_cmdbuf_cp"),
 (0x30900,"uconfig","esgs size","radv_queue:372"),(0x30904,"uconfig","gsvs size","radv_queue:372"),
]
out = []
for a, c, v, w in M:
    n = names.get(a, "?")
    t = title.get(a)
    if t:
        vals = " ".join(f"{x[0]:#x}×{x[1]}" for x in t["vals"][:3])
        out.append((c, "TITLE", n, hex(a), v, f"n={t['n']} nv={t['nvals']} {vals} kinds={','.join(t['kind'])}", w))
    else:
        out.append((c, "NOT-SEEN", n, hex(a), v, "", w))
for r in sorted(out, key=lambda x: (x[1], x[0], x[3])):
    print(*r, sep=" | ")

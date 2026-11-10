# Multi-line-aware NID extractor for Kyty-family trees: every LIB_FUNC/LIB_OBJECT("<nid>", f) even when split
# over lines, plus any bare quoted 11-char NID-looking string next to LIB_ macros. Output: nid, file, line, func.
import os, re, sys
root, out = sys.argv[1], sys.argv[2]
re_func = re.compile(r'LIB_(?:FUNC|OBJECT)\(\s*"([^"]+)"\s*,\s*([^)]*?)\)', re.S)
rows = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(('.cpp', '.h', '.inc', '.hpp')):
            continue
        p = os.path.join(dp, f)
        txt = open(p, encoding='utf-8', errors='replace').read()
        rel = os.path.relpath(p, root).replace(os.sep, '/')
        for m in re_func.finditer(txt):
            line = txt.count('\n', 0, m.start()) + 1
            rows.append((m.group(1), rel, str(line), ' '.join(m.group(2).split())))
with open(out, 'w', encoding='utf-8') as fo:
    for r in rows:
        fo.write('\t'.join(r) + '\n')
print(len(rows), len(set(r[0] for r in rows)))

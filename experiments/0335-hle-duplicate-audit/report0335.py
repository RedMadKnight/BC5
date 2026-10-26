#!/usr/bin/env python3
# BC5 experiment 0335: the tables of the audit from regs0335.py's output: the dead LIB_DEFINE blocks, the live NIDs with
# two different implementations, and the patch's registrations that have a same-named host implementation under
# another NID. usage: report0335.py <regs.jsonl> <git-status.txt> <patch-funcs.tsv>
import json, re, sys
from collections import defaultdict

R = [json.loads(l) for l in open(sys.argv[1])]
st = {l[3:].strip(): l[:2].strip() for l in open(sys.argv[2])}
added = set()
for l in open(sys.argv[3]):
    f, rest = l.split('\t', 1)
    m = re.search(r'LIB_(?:FUNC|OBJECT)\("([^"]+)"', rest)
    if m:
        added.add((f, m.group(1)))
live = [r for r in R if r['live']]
dead = [r for r in R if not r['live']]
print(f"# {len(R)} registrations: {len(live)} reached from Libs::InitAll (libs.cpp), {len(dead)} in LIB_DEFINE blocks nothing calls; {len(added)} added by patch 0001")
livenids = defaultdict(list)
for r in live:
    livenids[r['nid']].append(r)
print("\n## dead blocks (never added to the symbol database)")
blocks = defaultdict(list)
for r in dead:
    blocks[(r['root'], r['file'])].append(r)
for (root, f), v in sorted(blocks.items(), key=lambda kv: kv[0][1]):
    libs = sorted(set(r['ctx']['library'] for r in v if r['ctx']))
    over = sum(1 for r in v if r['nid'] in livenids)
    print(f"{root:52} {f:36} [{st.get(f, '-')}] {len(v):4} NIDs ({len(v) - over} only here); {','.join(libs)}")
print("\n## live NIDs registered more than once with different functions (order = SymbolDatabase::Add order)")
for nid, v in sorted(livenids.items(), key=lambda kv: kv[1][0]['order']):
    if len(v) < 2:
        continue
    funcs = set(x['func'].split('::')[-1] for x in v)
    if len(funcs) == 1:
        continue
    v = sorted(v, key=lambda y: y['order'])
    print(f"{nid}: " + ' | '.join(f"#{x['order']} {x['func']} ({x['file']}:{x['line']}, {'patch' if (x['file'], x['nid']) in added else 'upstream'})" for x in v))
print("\n## live NIDs registered more than once with the same function (aliases)")
n = 0
for nid, v in livenids.items():
    if len(v) > 1 and len(set(x['func'].split('::')[-1] for x in v)) == 1:
        n += 1
print(f"{n} NIDs")


def norm(fn):
    x = fn.split('::')[-1]
    x = re.sub(r'^(_?sce|Sce|Kernel|kernel|Lib|lib|Bc5|bc5)+', '', x)
    x = re.sub(r'(_\d+|\d+)$', '', x)
    return x.lower().replace('_', '')


byname = defaultdict(list)
for r in R:
    byname[norm(r['func'])].append(r)
print("\n## patch registrations with a same-named host implementation under another NID")
for r in R:
    if (r['file'], r['nid']) not in added:
        continue
    others = [o for o in byname[norm(r['func'])] if o['nid'] != r['nid'] and (o['file'], o['nid']) not in added]
    if others:
        print(f"{r['nid']} {r['func']} ({r['file']}:{r['line']}) <-> " + '; '.join(f"{o['nid']} {o['func']} ({o['file']}:{o['line']}, {'live' if o['live'] else 'dead'})" for o in others[:3]))

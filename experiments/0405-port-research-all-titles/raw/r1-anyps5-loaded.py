# r1-anyps5-loaded.py -- which of our LIB_FUNC/LIB_OBJECT registrations are reachable from Libs::InitAll.
# A registration counts as live only when the LIB_DEFINE (or other SymbolDatabase* init function) that holds it is
# called, directly or through LIB_LOAD, from InitAll (libs/libs.cpp). Names are matched on their last component, an
# over-approximation when two namespaces define the same init name.
# Usage: python -I r1-anyps5-loaded.py <our src dir> <out.json>
import os, re, sys, json
src, out = sys.argv[1:3]
rx_def = re.compile(r'(?:LIB_DEFINE\(\s*(\w+)\s*\)|void\s+(\w+)\s*\(\s*Loader::SymbolDatabase\s*\*\s*\w*\s*\))\s*\{')
rx_func = re.compile(r'LIB_(?:FUNC|OBJECT)\(\s*"([^"]+)"')
rx_call = re.compile(r'LIB_LOAD\(\s*([\w:]+)\s*\)|([\w:]+)\s*\(\s*s\s*\)')

def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), t, flags=re.S)
    return re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), t)

def body_end(t, i):
    d = 0
    for j in range(i, len(t)):
        if t[j] == '{': d += 1
        elif t[j] == '}':
            d -= 1
            if d == 0: return j
    return len(t)

defs = {}   # name -> {'calls': set, 'nids': set}
where = {}  # nid -> list of file:line
for dp, dn, fn in os.walk(src):
    for f in fn:
        if not f.endswith(('.cpp', '.inc', '.h', '.hpp')): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, src).replace('\\', '/')
        t = strip_comments(open(p, encoding='utf-8', errors='replace').read())
        for m in rx_def.finditer(t):
            name = m.group(1) or m.group(2)
            b = m.end() - 1; e = body_end(t, b); body = t[b:e]
            d = defs.setdefault(name, {'calls': set(), 'nids': set()})
            for c in rx_call.finditer(body):
                d['calls'].add((c.group(1) or c.group(2)).split('::')[-1])
            for x in rx_func.finditer(body):
                d['nids'].add(x.group(1))
                where.setdefault(x.group(1), []).append('%s:%d' % (rel, t.count('\n', 0, b + x.start()) + 1))
seen = set(); stack = ['InitAll']
while stack:
    n = stack.pop()
    if n in seen or n not in defs: continue
    seen.add(n); stack.extend(defs[n]['calls'])
live = set().union(*(defs[n]['nids'] for n in seen))
allreg = set().union(*(d['nids'] for d in defs.values()))
dead_defs = sorted(n for n in defs if n not in seen and defs[n]['nids'])
json.dump({'live': sorted(live), 'dead_only': sorted(allreg - live), 'dead_defs': dead_defs,
           'dead_where': {k: where[k] for k in sorted(allreg - live)}}, open(out, 'w'), indent=0)
print('init functions', len(defs), 'reached', len(seen), 'registered NIDs', len(allreg), 'live', len(live),
      'only in unreached tables', len(allreg - live))
print('unreached tables with registrations:', ' '.join(dead_defs))

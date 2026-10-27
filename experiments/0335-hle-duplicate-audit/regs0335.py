#!/usr/bin/env python3
# BC5 experiment 0335. Parse KytyPlus's HLE registrations: every LIB_FUNC/LIB_OBJECT with its library context (the LIB_VERSION/LIB_NAME in
# force, or a LIB_USING's namespace), its LIB_DEFINE, file and line; then walk the LIB_LOAD calls from libs.cpp's top
# definition to get the order of SymbolDatabase::Add. Output: JSON lines to stdout.
#   usage: regs.py <tree> > regs.jsonl
import json, os, re, sys

tree = sys.argv[1]
RE_VER = re.compile(r'LIB_VERSION\(\s*"([^"]*)"\s*,\s*(\d+)\s*,\s*"([^"]*)"\s*,\s*(\d+)\s*,\s*(\d+)\s*\)')
RE_NAME = re.compile(r'LIB_NAME\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)')
RE_USING = re.compile(r'LIB_USING\(\s*([\w:]+)\s*\)')
RE_NS = re.compile(r'\bnamespace\s+([\w:]+)\s*\{')
RE_DEF = re.compile(r'(?:LIB_DEFINE\(\s*([\w:]+)\s*\)|void\s+(InitAll)\s*\(\s*Loader::SymbolDatabase\s*\*\s*s\s*\)\s*\{)')
RE_FUNC = re.compile(r'LIB_(FUNC|OBJECT)\(\s*"([^"]+)"\s*,\s*([^)]*?)\s*\)\s*;')
RE_LOAD = re.compile(r'(?:LIB_LOAD\(\s*([\w:]+)\s*\)|\b([\w:]*Init\w*)\s*\(\s*s\s*\))\s*;')

files = []
for root, _, names in os.walk(os.path.join(tree, 'src')):
    for n in names:
        if n.endswith(('.cpp', '.h', '.hpp', '.inc')):
            files.append(os.path.join(root, n))

ns_ctx = {}     # namespace leaf name -> library context declared in it
defs = {}       # LIB_DEFINE leaf name -> {"file", "line", "items": [("func", rec) | ("load", name)]}
for f in sorted(files):
    try:
        text = open(f, encoding='utf-8', errors='replace').read()
    except OSError:
        continue
    if 'LIB_' not in text:
        continue
    rel = os.path.relpath(f, tree)
    ctx = None
    ns_stack = []
    cur_def = None
    depth = 0
    def_depth = None
    lines = text.splitlines()
    for i in range(len(lines)):  # a LIB_FUNC spanning lines is joined onto its first line
        if re.search(r'LIB_(FUNC|OBJECT)\(', lines[i]) and '#define' not in lines[i] and not re.search(r'\)\s*;', lines[i].split('//')[0]):
            j = i + 1
            while j < len(lines) and j < i + 6:
                lines[i] = lines[i].split('//')[0].rstrip() + ' ' + lines[j].strip()
                lines[j] = ''
                if re.search(r'\)\s*;', lines[i]):
                    break
                j += 1
    in_block = False
    for ln, line in enumerate(lines, 1):
        # strip block comments, string and character literals, and // comments before brace counting
        out, i = [], 0
        while i < len(line):
            if in_block:
                j = line.find('*/', i)
                if j < 0:
                    i = len(line)
                    break
                in_block = False
                i = j + 2
                continue
            c = line[i]
            if line.startswith('/*', i):
                in_block = True
                i += 2
                continue
            if line.startswith('//', i):
                break
            if c in '"\'':
                q = c
                i += 1
                lit = []
                while i < len(line) and line[i] != q:
                    if line[i] == '\\':
                        lit.append(line[i:i + 2])
                        i += 2
                        continue
                    lit.append(line[i])
                    i += 1
                i += 1
                out.append(q + ''.join(lit).replace('{', '').replace('}', '') + q)
                continue
            out.append(c)
            i += 1
        code = ''.join(out)
        m = RE_NS.search(code)
        if m:
            ns_stack.append((m.group(1).split('::')[-1], depth, ctx))  # the context in force outside, restored at the close
        if (m := RE_VER.search(code)):
            ctx = {'library': m.group(1), 'lib_ver': int(m.group(2)), 'module': m.group(3), 'mod_ver': [int(m.group(4)), int(m.group(5))]}
            if ns_stack:
                ns_ctx[ns_stack[-1][0]] = ctx
        elif (m := RE_NAME.search(code)) and '#define' not in code:
            ctx = {'library': m.group(1), 'lib_ver': None, 'module': m.group(2), 'mod_ver': None}
            if ns_stack:
                ns_ctx[ns_stack[-1][0]] = ctx
        if (m := RE_USING.search(code)) and '#define' not in code:
            ctx = {'using': m.group(1).split('::')[-1]}
        if (m := RE_DEF.search(code)) and '#define' not in code and not re.search(r'LIB_DEFINE\([^)]*\)\s*;', code):
            cur_def = '::'.join([x[0] for x in ns_stack] + [(m.group(1) or m.group(2)).split('::')[-1]])
            if cur_def in defs:
                cur_def += f'@{rel}:{ln}'
            defs[cur_def] = {'file': rel, 'line': ln, 'items': [], 'ns': [x[0] for x in ns_stack]}
            def_depth = depth
        for m in RE_FUNC.finditer(code):
            if cur_def is None:
                continue
            defs[cur_def]['items'].append(('func', {'kind': m.group(1), 'nid': m.group(2), 'func': m.group(3).strip(),
                                                    'file': rel, 'line': ln, 'ctx': dict(ctx) if ctx else None}))
        for m in RE_LOAD.finditer(code):
            if cur_def is not None and '#define' not in code:
                defs[cur_def]['items'].append(('load', m.group(1) or m.group(2)))
        depth += code.count('{') - code.count('}')
        while ns_stack and depth <= ns_stack[-1][1]:
            ctx = ns_stack[-1][2]
            ns_stack.pop()
        if cur_def is not None and def_depth is not None and depth <= def_depth and '}' in code and ln > defs[cur_def]['line']:
            cur_def = None
            def_depth = None


def resolve_ctx(c):
    seen = 0
    while c is not None and 'using' in c and seen < 10:
        c = ns_ctx.get(c['using'])
        seen += 1
    return c


def resolve_load(name, ns):
    # LIB_LOAD(A::B) from namespace ns: the definition whose qualified name ends with A::B, nearest to ns first
    cands = [k for k in defs if k.split('@')[0] == name or k.split('@')[0].endswith('::' + name)]
    if not cands:
        return None
    def score(k):
        kn = defs[k]['ns']
        common = 0
        for a, b in zip(kn, ns):
            if a != b:
                break
            common += 1
        return (-common, len(kn))
    return sorted(cands, key=score)[0]


for k, d in defs.items():
    d['items'] = [(kind, resolve_load(x, d['ns']) if kind == 'load' else x) for kind, x in d['items']]
    for kind, x in d['items']:
        if kind == 'load' and x is None:
            print(json.dumps({'unresolved_load_in': k}), file=sys.stderr)
# the load order: every LIB_DEFINE that no other LIB_DEFINE loads is a root; libs.cpp's roots first
loaded = {x for d in defs.values() for kind, x in d['items'] if kind == 'load' and x}
roots = [n for n, d in defs.items() if n not in loaded]
roots.sort(key=lambda n: (0 if n.endswith('::InitAll') else 1, defs[n]['file'], defs[n]['line']))
order = 0
emitted = set()


def walk(name, path, root):
    global order
    d = defs.get(name)
    if d is None or name in path:
        return
    for kind, x in d['items']:
        if kind == 'load':
            if x:
                walk(x, path | {name}, root)
        else:
            rec = dict(x)
            rec['ctx'] = resolve_ctx(rec['ctx'])
            rec['define'] = name
            rec['root'] = root
            rec['live'] = root.endswith('::InitAll')
            rec['order'] = order
            order += 1
            key = (rec['file'], rec['line'], rec['nid'])
            if key in emitted:
                continue
            emitted.add(key)
            print(json.dumps(rec))


for r in roots:
    walk(r, frozenset(), r)
print(json.dumps({'roots': roots}), file=sys.stderr)

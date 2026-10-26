#!/usr/bin/env python3
# BC5 experiment 0338: the imports whose path or implementation differs between two import logs (BC5_IMPORT_LOG, exp
# 0336's format: "<t> import\t<program>\t<nid#lib#mod>\t<library>\t<module>\t<path>\t<record>\t<dbg_name>\t<bound|stub>"),
# keyed by program and name, and the path counts of each.
# usage: compare0338.py <before log[.gz]> <after log[.gz]>
import collections, gzip, sys


def load(p):
    f = gzip.open(p, 'rt') if p.endswith('.gz') else open(p)
    out = {}
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) == 9 and parts[0].endswith(' import'):
            _, prog, name, lib, mod, path, rec, dbg, bound = parts
            out[(prog, name)] = (lib, path, dbg, bound)
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
for tag, d in (('before', a), ('after', b)):
    c = collections.Counter(v[1] for v in d.values())
    print(f'{tag}: {len(d)} imports; ' + ', '.join(f'{k} {c[k]}' for k in sorted(c)))
only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
print(f'only before: {len(only_a)}; only after: {len(only_b)}')
for k in only_a + only_b:
    print('  ', 'before' if k in a else 'after', k[0], k[1])
print('\n## changed (program, NID, requested library: path implementation -> path implementation)')
n = 0
for k in sorted(set(a) & set(b), key=lambda k: (a[k][0], k[0], k[1])):
    if a[k][1:3] != b[k][1:3]:
        n += 1
        print(f'{k[0]:24} {k[1].split("#")[0]:12} {a[k][0]:12} {a[k][1]:13} {a[k][2]:40} -> {b[k][1]:5} {b[k][2]}')
print(f'{n} changed')

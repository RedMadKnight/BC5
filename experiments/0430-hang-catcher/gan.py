import collections
import re
import sys

ev = []
for l in open(sys.argv[1], errors='replace'):
    m = re.match(r'([\d.]+) (\S+) (0x[0-9a-f]+) (\S+) (-?\d+) #(\d+) (\d+) \| (.*)', l)
    if not m:
        continue
    t, typ, lab, kind, ring, n, off, rest = m.groups()
    ev.append((float(t), typ, int(lab, 16), kind, int(ring), int(n), int(off), rest))
print('events', len(ev), 'span %.3f s' % (ev[-1][0] - ev[0][0]))
waited = collections.Counter(e[2] for e in ev if e[1] == 'wait')
print('labels waited on:', len(waited))
types = collections.Counter(e[1] for e in ev)
print('types', dict(types))
# per label with waits: the sequence
for lab, nw in waited.most_common(8):
    seq = [e for e in ev if e[2] == lab]
    print('\n== label 0x%x: %d events, %d waits' % (lab, len(seq), nw))
    writes = collections.Counter((e[1], e[3], e[4], re.search(r'value (0x[0-9a-f]+)', e[7]).group(1)) for e in seq if e[1] in ('write', 'DROPPED-WRITE'))
    for k, v in writes.most_common(8):
        print('   ', v, k)
    wv = collections.Counter((e[3], e[4], re.search(r'value (0x[0-9a-f]+) ref (0x[0-9a-f]+)', e[7]).groups(), 'SAT' if 'SATISFIED' in e[7] else 'uns') for e in seq if e[1] == 'wait')
    for k, v in wv.most_common(6):
        print('    wait', v, k)
    for e in seq[:40]:
        print('     %.6f %-14s %s r%d #%d @%d | %s' % (e[0], e[1], e[3], e[4], e[5], e[6], e[7][:90]))

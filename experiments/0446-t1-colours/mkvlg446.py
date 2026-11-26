# exp 0446 (tag vlg446, 2026-11-26): remove exp 0439's flip-label arm a (BC5_0439_FLIP_LABEL_GPU, not adopted; arm b,
# FLIP_LABEL_PIECES, is the fix) from a unit made by mkvl439.py: the block in GetBufferLabelAddress, whole, so the word
# and its code are not compiled. The block's anchor and its end must each match exactly once.
#   python3 -I mkvlg446.py <bc5LleAgc.cpp>   (in place)
import sys

p = sys.argv[1]
s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
head = '\t{ // exp 0439 (tag vl439 a, BC5_0439_FLIP_LABEL_GPU=1)'
tail = '\t\t\t});\n\t}\n\t*out = Bc5Gc::g_labels;\n'
assert s.count(head) == 1, ('head', s.count(head))
i = s.index(head)
j = s.find(tail, i)
assert j > i and s.count(tail) == 1, ('tail', s.count(tail))
cut = s[i:j + len(tail)]
assert cut.count('BC5_0439_FLIP_LABEL_GPU') == 2 and 'GetBufferLabelAddress' not in cut, 'the block is not the arm alone'
s = s[:i] + '\t*out = Bc5Gc::g_labels;\n' + s[j + len(tail):]
assert 'BC5_0439_FLIP_LABEL_GPU' not in s and 'vl439 a' not in s
open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvlg446: removed', cut.count('\n'), 'lines of arm a from', p)

#!/usr/bin/env python3
# BC5 exp 0439 (tag vlon439, 11-24 night): vl439 (b) as the default. The flip-label wait inside a chained or called piece
# is served on the CPU before the submit, exactly as the top-level one (exp 0069's rule), for every title, unless
# BC5_0439_FLIP_LABEL_PIECES is "0". vz439e-g measured that dropping it lets the next frame render into a display buffer
# whose flip is still running: the third title's film noise in its native-4K mode.
# Usage: python3 mkvlon439.py <d2/new>   (patches bc5LleAgc.cpp in place; the anchor exactly once)
import os
import sys

p = os.path.join(sys.argv[1], 'bc5LleAgc.cpp')
s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'vlon439' not in s
a = '''					const char* e = std::getenv("BC5_0439_FLIP_LABEL_PIECES");
					return e != nullptr && e[0] == '1' && e[1] == 0;'''
b = '''					const char* e = std::getenv("BC5_0439_FLIP_LABEL_PIECES"); // exp 0439 (tag vlon439): on unless "0"
					return !(e != nullptr && e[0] == '0' && e[1] == 0);'''
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b)
open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvlon439: patched', p)

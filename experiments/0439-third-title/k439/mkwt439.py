#!/usr/bin/env python3
# BC5 exp 0439 (tag wt439, the maintainer's word of 11-22 ~20:45: the FPS figure does not belong in
# the menu window, only in MangoHud): the emulator window's title without the frame rate, for every title and both builds; MangoHud shows it.
# src/graphics/presentation/window/window.cpp, WindowContext::UpdateTitle (patch 0001 since 2026-10-16: the rate only,
# set once a second). Now: no rate, and the title is set only when its text changes (once, in practice).
# Usage: python mkwt439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'wt439' not in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''	    "[{} | {}] {}{}{}{}{}{}[{}] [{}], fps: {:.1f}", KYTY_BUILD_LABEL, build_type,''',
    '''	    "[{} | {}] {}{}{}{}{}{}[{}] [{}]", KYTY_BUILD_LABEL, build_type, // exp 0439 (tag wt439): no frame rate (MangoHud has it)''')
rep('''	    device_name, processor_name, current_fps);
''', '''	    device_name, processor_name);
	{ // exp 0439 (tag wt439): set only when the text changes
		static std::string wt439_last;
		if (fps == wt439_last) {
			return;
		}
		wt439_last = fps;
	}
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkwt439: wrote', dst)

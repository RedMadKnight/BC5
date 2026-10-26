#!/usr/bin/env python3
# BC5 experiment 0332: the crash handler also dumps the faulting function's stack frame and what its slots point to,
# two levels deep. A one-file change of the shared tree's src/loader/runtimeLinker.cpp (md5 f294dfc2, the file in main's
# patch 0001). The death crash at eboot.bin+0x3ba1bdf (F401) walks a list of 16-byte handle entries that it takes
# through [rbp-0x38] and then [[rbp-0x38]]. Its first entry held garbage, and the existing dump (the registers and
# 8 qwords behind each) does not reach the list. Read only: every read is checked with the file's IsReadableRange, as
# the existing dumps are. Crash time only, so no switch.
# Each anchor must occur exactly once.
# usage: patch0332.py <shared runtimeLinker.cpp, md5 f294dfc2> <out .cpp> <out .diff>   (the input is only read)
import difflib, hashlib, sys

IN_MD5 = 'f294dfc28ec7558552d6b3898dbde71d'

FRAME = r'''		dump_guest_qwords("guest r15", info->r15);
		// Experiment 0332: the crash's stack frame and what its slots point to, two levels deep, so that a crash in the
		// title's own code shows the data it walked. The death crash at eboot.bin+0x3ba1bdf takes its handle list
		// through [rbp-0x38] and [[rbp-0x38]] (F401). Read only: every read is checked with IsReadableRange.
		if (info->rbp >= 0x100000000ull && IsReadableRange(info->rbp - 0x80u, 20u * sizeof(uint64_t))) {
			const auto* frame = reinterpret_cast<const uint64_t*>(info->rbp - 0x80u);
			for (int k = 0; k < 20; k++) {
				Bc5CrashLog("frame rbp%+d = %016" PRIx64 "\n", -0x80 + 8 * k, frame[k]);
			}
			for (int k = 0; k < 20; k++) {
				const int      off = -0x80 + 8 * k;
				const uint64_t p   = frame[k];
				if (p < 0x100000000ull || !IsReadableRange(p, 8u * sizeof(uint64_t))) {
					continue;
				}
				char name[40] {};
				std::snprintf(name, sizeof(name), "frame [rbp%+d]", off);
				dump_guest_qwords(name, p);
				const uint64_t q = *reinterpret_cast<const uint64_t*>(p);
				if (q < 0x100000000ull || !IsReadableRange(q, 32u * sizeof(uint64_t))) {
					continue;
				}
				const auto* w = reinterpret_cast<const uint64_t*>(q);
				for (int r = 0; r < 4; r++) {
					Bc5CrashLog("frame [[rbp%+d]] = %016" PRIx64 " +0x%02x: %016" PRIx64 " %016" PRIx64 " %016" PRIx64
					            " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
					            off, q, r * 64, w[r * 8 + 0], w[r * 8 + 1], w[r * 8 + 2], w[r * 8 + 3], w[r * 8 + 4],
					            w[r * 8 + 5], w[r * 8 + 6], w[r * 8 + 7]);
				}
			}
		}
'''

EDITS = [
    ('		dump_guest_qwords("guest r15", info->r15);\n', FRAME),
]


def main():
    src_path, out_path, diff_path = sys.argv[1:4]
    raw = open(src_path, 'rb').read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != IN_MD5:
        sys.exit(f"{src_path}: md5 {md5}, expected {IN_MD5} (the shared tree's runtimeLinker.cpp, main's patch 0001)")
    text = raw.decode('utf-8')
    for k, (old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        if n != 1:
            sys.exit(f'edit {k}: anchor found {n} times')
        text = text.replace(old, new)
    out = text.encode('utf-8')
    open(out_path, 'wb').write(out)
    diff = difflib.unified_diff(raw.decode('utf-8').splitlines(keepends=True), text.splitlines(keepends=True),
                                'a/src/loader/runtimeLinker.cpp', 'b/src/loader/runtimeLinker.cpp', n=3)
    open(diff_path, 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'{out_path}: md5 {hashlib.md5(out).hexdigest()}, {len(EDITS)} edits')


if __name__ == '__main__':
    main()

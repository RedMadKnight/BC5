#!/usr/bin/env python3
"""BC5 exp 0412 (README section 39): how much of the guest's direct memory file holds only zeros?
Reads the emulator's direct-memory memfd from outside (/proc/<pid>/fd/<n>, read-only; no ptrace, no signal) and counts,
over the file's allocated extents (SEEK_DATA / SEEK_HOLE), the 4 KiB pages that are all zero. A pinned page that is
all zero is a page the zero-page scheme of section 31 would not have to keep; a hole is not allocated at all.
Prints the totals and a table per 256 MiB of file offset. Reading does not allocate (the pages exist or are holes).
usage: zero0412.py <pid> [label]"""
import os
import sys
import time

PAGE = 4096
BLOCK = 4 << 20
BUCKET = 256 << 20


def main():
    pid = int(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else "zero"
    best = None
    for n in os.listdir(f"/proc/{pid}/fd"):
        try:
            link = os.readlink(f"/proc/{pid}/fd/{n}")
            if not link.startswith("/memfd:"):
                continue
            st = os.stat(f"/proc/{pid}/fd/{n}")
        except OSError:
            continue
        # The direct-memory file is the memfd with the most allocated blocks (the private one is 1 TiB and sparse).
        if best is None or st.st_blocks > best[3]:
            best = (n, st.st_size, link, st.st_blocks)
    assert best is not None, "no memfd"
    fd = os.open(f"/proc/{pid}/fd/{best[0]}", os.O_RDONLY)
    size = best[1]
    zero_block = bytes(BLOCK)
    zero_page = bytes(PAGE)
    data = zeros = 0
    buckets = {}
    t0 = time.time()
    pos = 0
    while pos < size:
        try:
            start = os.lseek(fd, pos, os.SEEK_DATA)
        except OSError:
            break
        end = os.lseek(fd, start, os.SEEK_HOLE)
        pos = start
        while pos < end:
            want = min(BLOCK - pos % BLOCK, end - pos)
            b = os.pread(fd, want, pos)
            if not b:
                break
            k = pos // BUCKET
            d, z = buckets.get(k, (0, 0))
            n_pages = len(b) // PAGE
            if len(b) == BLOCK and b == zero_block:
                zp = n_pages
            else:
                zp = sum(1 for i in range(0, n_pages * PAGE, PAGE) if b[i:i + PAGE] == zero_page)
            buckets[k] = (d + n_pages, z + zp)
            data += n_pages
            zeros += zp
            pos += len(b)
        pos = end
    mib = lambda p: p * PAGE / 1048576.0
    print(f"{label}: file {best[2]} {size / 1048576.0:.0f} MiB; allocated {mib(data):.0f} MiB, of it all-zero pages {mib(zeros):.0f} MiB "
          f"({100.0 * zeros / max(data, 1):.1f} %); read in {time.time() - t0:.1f} s")
    for k in sorted(buckets):
        d, z = buckets[k]
        print(f"{label}:   offset {k * 256:6d} MiB: allocated {mib(d):6.0f}, all-zero {mib(z):6.0f}")


if __name__ == "__main__":
    main()

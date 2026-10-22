#!/usr/bin/env python3
# BC5 experiment 0191: replace the src/libs/bc5LleAgc.cpp section (a new-file diff) of
# backend/kytyplus-patches/0001-bc5-lle-agc.patch with a new version of the file, leaving every other section
# byte for byte (the live KytyPlus tree on the box also carries other sessions' uncommitted changes, so the
# whole patch is not regenerated from it). The blob id is git's: sha1("blob <len>\0" + content).
# usage: swap_patch_section.py <patch in> <bc5LleAgc.cpp> <patch out>
import hashlib
import sys

src, new_file, dst = sys.argv[1:4]
p = open(src, "rb").read()
body = open(new_file, "rb").read()
assert body.endswith(b"\n") and b"\r\n" not in body
head = b"diff --git a/src/libs/bc5LleAgc.cpp b/src/libs/bc5LleAgc.cpp\n"
start = p.index(head)
end = p.find(b"\ndiff --git ", start + 1)
end = len(p) if end < 0 else end + 1
lines = body[:-1].split(b"\n")
blob = hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()[:7]
sec = (head + b"new file mode 100644\nindex 0000000.." + blob.encode() + b"\n--- /dev/null\n+++ b/src/libs/bc5LleAgc.cpp\n"
       + b"@@ -0,0 +1,%d @@\n" % len(lines) + b"".join(b"+" + l + b"\n" for l in lines))
old = p[start:end]
assert old.startswith(head) and b"--- /dev/null" in old[:300], "the section is not a new-file diff"
open(dst, "wb").write(p[:start] + sec + p[end:])
print("section replaced: %d -> %d bytes, %d lines, blob %s" % (len(old), len(sec), len(lines), blob))

#!/usr/bin/env python3
"""BC5 experiment 0417: one switch on top of exp 0412's nl412 (the learned windows removed), keep-guards variant.

The top session ordered the zero guards out with the rest of the learned pass; exp 0412's author advises keeping the
2 MiB zero guard behind each eager heap (a rule from the title's behaviour, exp 0037: it reads up to 64 KiB past its
GPU heaps' ends; the full removal has never run). By the maintainer's fixes-first rule both go into one private build:
the keep-guards unit (mknl0412.py --keep-guards on the folded unit 353893b8 -> 457c1943; mknl0412.py at exp 0412 commit 45a686c4, with its K1 catcher) gets
  BC5_DIRECT_HEAP_GUARDS=0   no guard is made: the behaviour of the full variant, with the code still present
  unset or anything else     the guards as before
and says which, once, on stderr. With =0 nothing ever enters g_scratch, so the pass returns before its first loop.
usage: mkguards0417.py <bc5LleAgc.cpp in (457c1943)> <out> [--default-off]
       --default-off: unset means NO guards and BC5_DIRECT_HEAP_GUARDS=1 turns them on (the top session's choice B)"""
import hashlib
import sys

src, dst = sys.argv[1:3]
default_off = "--default-off" in sys.argv[3:]
s = open(src, "rb").read()
assert b"\r" not in s
md5 = hashlib.md5(s).hexdigest()
assert md5 == "457c194376048e5ae6127a82d431a898", md5
old = b"""	if (!g_dev) return; // exp 0412 (tag nl412): no learned file
	static uint64_t applied_gen = 0;
"""
cond = (b"e != nullptr && e[0] == '1' && e[1] == '\\0'" if default_off else b"!(e != nullptr && e[0] == '0' && e[1] == '\\0')")
new = b"""	if (!g_dev) return; // exp 0412 (tag nl412): no learned file
	// Experiment 0417: BC5_DIRECT_HEAP_GUARDS. %s
	static const bool heap_guards = [] {
		const char* e  = std::getenv("BC5_DIRECT_HEAP_GUARDS");
		const bool  on = %s;
		std::fprintf(stderr, "[bc5] exp 0417: the zero guards behind the eager heaps are %%s (BC5_DIRECT_HEAP_GUARDS)\\n", on ? "on" : "off");
		return on;
	}();
	if (!heap_guards) return; // nothing was ever put into g_scratch, so there is nothing to give back either
	static uint64_t applied_gen = 0;
""" % (b"Unset: no guard; =1 makes the 2 MiB zero guard behind each eager heap (exp 0037)." if default_off
       else b"=0 makes no guard (the full nl412 variant's behaviour); unset: the guards of exp 0037.", cond)
assert s.count(old) == 1
s = s.replace(old, new)
# exp 0412's once-only journal line said the guard "stays"; with the switch that is true only by default (its author's note)
old = b"the 2 MiB zero guard behind each eager heap stays; a GPU fault"
new = b"the 2 MiB zero guard behind each eager heap stays unless BC5_DIRECT_HEAP_GUARDS=0 (exp 0417; stderr says which); a GPU fault"
assert s.count(old) == 1
s = s.replace(old, new)
open(dst, "wb").write(s)
print("guards %s -> %s (%s)" % (md5[:8], hashlib.md5(s).hexdigest()[:8], "default off" if default_off else "default on"))

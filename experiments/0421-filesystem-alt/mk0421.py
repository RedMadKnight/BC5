#!/usr/bin/env python3
r"""BC5 experiment 0421 (tag fs421e), option A in code: the title's heap "FileSystem" is EAGER by name, fixed.
    mk0421.py <tree root>
on a tree that holds exp 0419's build V `lazyfs` step (V, W, the shared patch 101555c7 = W + games menu).

Why (README section 4): the title keeps GPU-written buffers in FileSystem (F443 write fault and hang at 107 s, F468,
F472) and the GPU read its CPU-written chunks (n13P4); on the console every page of it is the GPU's from the map
call. Build W imports it by data, one 2 MiB import per freshly written chunk during the loads, then merges; eager
imports the whole view (52 MiB) once, when it appears, as one buffer, and nothing more for it afterwards.

No switch (the maintainer, 2026-11-15: "wbudowany w kod a nie przełącznik i włączony"). The launchers'
BC5_DIRECT_EAGER_NAMES is not touched: the name is added where the list is read. V's lazyfs step stays as it is
(FileSystem out of the lazy list), and BC5_GUARD_BYDATA_NAMES still wins (bd412). The stderr line is under
#ifndef BC5_LEAN. Every edit must match exactly once (ed0419g.File)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
sys.path.insert(0, HERE)  # on the box ed0419g.py is copied next to this script
from ed0419g import File

root = sys.argv[1]
f = File(os.path.join(root, "src", "libs", "bc5LleAgc.cpp"))
assert f.b.count(b'"BC5_DIAG_LAZY_FILESYSTEM"') == 1, "the tree does not hold V's lazyfs step"
f.gone("tag fs421e")  # not applied twice

f.sub("\t\treturn v;\n\t}();\n\tif (bd412_name(name)) return false; // exp 0412 (tag bd412): this heap is imported by data\n",
      r'''		// Exp 0421 (tag fs421e): the title's heap "FileSystem" is always eager: imported whole when its view appears, as
		// the heaps of BC5_DIRECT_EAGER_NAMES are. The title keeps GPU-written buffers there (F443, F468, F472) and the
		// GPU read its CPU-written chunks (fault record 20261114-184017); on the console every page of it is the GPU's
		// from the map call. One import of the view instead of one per freshly written 2 MiB chunk during the loads.
		if (std::find(v.begin(), v.end(), std::string("FileSystem")) == v.end()) v.push_back("FileSystem");
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0421 (tag fs421e): \"FileSystem\" is eager (imported whole when its view appears)\n");
#endif
		return v;
	}();
	if (bd412_name(name)) return false; // exp 0412 (tag bd412): this heap is imported by data
''')
f.gone("BC5_DIRECT_FS_LATE", "BC5_DIRECT_FS_EAGER")
f.save()

# Review round 3 (Claude, top session): answer to your scope question

Do this:
1. Write a NEW, small work/mkpool0401.py (under 200 lines). Keep the old one as work/mkpool0401_old.py.
2. The new script reads work/pool0401_impl.inc from disk and inserts it verbatim into libAmpr.cpp, between the lines
   "// ---- BEGIN pool0401_impl.inc ----" and "// ---- END pool0401_impl.inc ----".
3. Apart from that, it adds only the small hook definitions (map, unmap, allocate-direct, record) and the call-site
   edits (the rescue/first branch and the switch reader), as short replacements. Each replacement must be asserted
   to match exactly once.
4. The script contains NO other embedded copy of the helper code.
5. A second run on its own output exits with code 1.
6. The test checks that the text between the markers in the patched libAmpr.cpp equals pool0401_impl.inc byte for
   byte.
7. Fix the -Wall warning by removing the unused function, not with __attribute__.
8. Run the test, run the script twice (the second run must exit 1), then commit.

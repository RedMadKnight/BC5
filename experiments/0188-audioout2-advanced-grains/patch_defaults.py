import sys
root = sys.argv[1]
def patch(path, old, new):
    b = open(path, "rb").read()
    if b.count(new) >= 1 and b.count(old) == 0:
        print("already", path); return
    assert b.count(old) == 1, (path, b.count(old))
    open(path, "wb").write(b.replace(old, new)); print("ok", path)
# AudioOut2 grain model: on by default (experiment 0188), KYTY_BC5_AUDIO2_ADVANCED=0 turns it off.
patch(root + "/src/libs/libAudio2.cpp",
      b"""		const char* e = std::getenv("KYTY_BC5_AUDIO2_ADVANCED");
		return e != nullptr && std::atoi(e) != 0;""",
      b"""		const char* e = std::getenv("KYTY_BC5_AUDIO2_ADVANCED"); // on unless =0 (experiment 0188, runs M5, O6, A1)
		return e == nullptr || std::atoi(e) != 0;""")
patch(root + "/src/libs/libAudio2.cpp",
      b"timeline ran that much fast (experiment 0188, run M2). KYTY_BC5_AUDIO2_ADVANCED=1.",
      b"timeline ran that much fast (experiment 0188, run M2). On by default; KYTY_BC5_AUDIO2_ADVANCED=0 restores the old model.")
# VideoOut event coalescing: on by default (experiment 0188), KYTY_BC5_VIDEOOUT_COALESCE=0 turns it off.
patch(root + "/src/graphics/presentation/videoOut.cpp",
      b"""		const char* e = std::getenv("KYTY_BC5_VIDEOOUT_COALESCE");
		return e != nullptr && std::atoi(e) != 0;""",
      b"""		const char* e = std::getenv("KYTY_BC5_VIDEOOUT_COALESCE"); // on unless =0 (experiment 0188)
		return e == nullptr || std::atoi(e) != 0;""")

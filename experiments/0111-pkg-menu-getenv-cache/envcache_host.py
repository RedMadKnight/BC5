p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
L = open(p, encoding="utf-8", newline="").read().split("\n")
lines = [1455, 1456, 1904, 3256, 3523, 5027, 5097, 5147, 5155, 5158, 5176, 5186, 5268, 5358, 5423]
n = 0
for ln in lines:
    i = ln - 1
    assert "std::getenv(\"BC5_" in L[i], (ln, L[i])
    c = L[i].count("std::getenv(\"BC5_")
    L[i] = L[i].replace("std::getenv(\"BC5_", "BC5_ENV(\"BC5_")
    n += c
s = "\n".join(L)
anchor = "namespace Libs {"
assert s.count(anchor) >= 1
macro = ("// Experiment 0111: the host's BC5_* settings, read once per call site. std::getenv walks the whole\n"
         "// environment (about a hundred variables here), and the submission path called it about eight\n"
         "// times for every buffer, partly under g_dev_mutex. Nothing sets BC5_* variables while the title runs.\n"
         "#define BC5_ENV(name) ([]() -> const char* { static const char* const v = std::getenv(name); return v; }())\n\n")
s = s.replace(anchor, macro + anchor, 1)
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok", n)

"""Exp 0413 (PRIVATE diagnostic, never for a shared build): switch_defaults.hpp of the a2ab53c7 tree (md5 6ba7a7eb) with a
row filter read from a FILE, so a bisect over the rows keeps the environment identical in every run. Apply() skips each
row whose name stands on a line of /home/kjaniszewski/bc5-work/exp0413/n/skip.txt (a missing file skips nothing) and, with
a line "+NAME=VALUE", adds a row that is not in the table. usage: mkskip0413.py <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read().decode()
assert hashlib.md5(s.encode()).hexdigest().startswith("6ba7a7eb"), hashlib.md5(s.encode()).hexdigest()
OLD = ("\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n"
       "\t\tsetenv(d->name, d->value, 0);\n"
       "\t}\n")
assert s.count(OLD) == 1
NEW = ("\t// exp 0413 private diagnostic: rows to skip (NAME) and rows to add (+NAME=VALUE), one per line, from a file.\n"
       "\tchar  skip[8192] = {0};\n"
       "\tFILE* sf         = std::fopen(\"/home/kjaniszewski/bc5-work/exp0413/n/skip.txt\", \"rb\");\n"
       "\tif (sf != nullptr) {\n"
       "\t\tconst size_t got = std::fread(skip + 1, 1, sizeof(skip) - 3, sf);\n"
       "\t\tstd::fclose(sf);\n"
       "\t\tskip[0]       = '\\n';\n"
       "\t\tskip[got + 1] = '\\n';\n"
       "\t\tskip[got + 2] = 0;\n"
       "\t}\n"
       "\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n"
       "\t\tchar key[160];\n"
       "\t\tstd::snprintf(key, sizeof(key), \"\\n%s\\n\", d->name);\n"
       "\t\tif (std::strstr(skip, key) != nullptr) continue;\n"
       "\t\tsetenv(d->name, d->value, 0);\n"
       "\t}\n"
       "\tfor (char* p = skip; (p = std::strstr(p, \"\\n+\")) != nullptr;) {\n"
       "\t\tp += 2;\n"
       "\t\tchar* e  = std::strchr(p, '\\n');\n"
       "\t\tchar* eq = std::strchr(p, '=');\n"
       "\t\tif (e == nullptr || eq == nullptr || eq > e) break;\n"
       "\t\t*eq = 0;\n"
       "\t\t*e  = 0;\n"
       "\t\tsetenv(p, eq + 1, 0);\n"
       "\t\t*eq = '=';\n"
       "\t\t*e  = '\\n';\n"
       "\t}\n")
s = s.replace(OLD, NEW).replace("#include <cstdlib>\n", "#include <cstdio>\n#include <cstdlib>\n")
open(sys.argv[2], "wb").write(s.encode())
print(hashlib.md5(s.encode()).hexdigest())

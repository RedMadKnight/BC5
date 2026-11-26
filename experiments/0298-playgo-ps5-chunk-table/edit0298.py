# BC5 experiment 0298: the two private source copies (the tree's files are not touched).
#   systemContent.cpp: PlayGo::Open also takes a PS5 table ("plgx"), whose chunk count sits at offset 10 as in a PS4
#                      "plgo" one (the second title's table: 100 there, and 100 "Chunk #N" labels), and says on stderr
#                      what it read.
#   libPlayGo.cpp:     the title's PlayGo calls on stderr (the play log), the first 32 of each function, and every
#                      GetLocus answer among them.
# usage: python3 -I edit0298.py <systemContent.cpp copy> <libPlayGo.cpp copy>
import sys

sc, pg = sys.argv[1:3]

s = open(sc, encoding="utf-8").read()
old = "\tif (magic1 != 0x6f676c70) {\n"
assert s.count(old) == 1
s = s.replace(old,
              "\t// BC5 experiment 0298: a PS5 package's table starts with \"plgx\" and keeps the chunk count at offset 10 as\n"
              "\t// the PS4 \"plgo\" one does (the second title's: 100, matching its 100 \"Chunk #N\" labels).\n"
              "\tif (magic1 != 0x6f676c70 && magic1 != 0x78676c70) {\n"
              "\t\tstd::fprintf(stderr, \"bc5 playgo: %s: magic %08\" PRIx32 \", not a chunk table\\n\", Common::PathToString(file_name).c_str(), magic1);\n")
old = "\tm_f.Read(&m_chunks_num, 2);\n\n\tm_opened = true;\n"
assert s.count(old) == 1
s = s.replace(old, "\tm_f.Read(&m_chunks_num, 2);\n\n\tm_opened = true;\n"
                   "\tstd::fprintf(stderr, \"bc5 playgo: %s: magic %08\" PRIx32 \", %\" PRIu16 \" chunks\\n\", Common::PathToString(file_name).c_str(), magic1, m_chunks_num);\n")
old = "#include <cstdint>\n"
assert s.count(old) == 1
s = s.replace(old, "#include <cinttypes>\n#include <cstdint>\n#include <cstdio>\n")
open(sc, "w", encoding="utf-8").write(s)

p = open(pg, encoding="utf-8").read()
old = "#include <algorithm>\n"
assert p.count(old) == 1
p = p.replace(old, "#include <algorithm>\n#include <atomic>\n#include <cstdarg>\n#include <cstdio>\n")
old = "static uint32_t g_chunks_num = 0;\n"
assert p.count(old) == 1
p = p.replace(old, old + "\n"
              "// BC5 experiment 0298: the title's PlayGo calls on stderr (the play log), the first 32 of each kind.\n"
              "static void bc5_pg(std::atomic<int>& n, const char* fmt, ...) {\n"
              "\tif (n.fetch_add(1) >= 32) {\n\t\treturn;\n\t}\n"
              "\tva_list ap;\n\tva_start(ap, fmt);\n\tstd::fputs(\"bc5 playgo: \", stderr);\n\tstd::vfprintf(stderr, fmt, ap);\n\tva_end(ap);\n"
              "}\n"
              "#define BC5_PG(...)                                   \\\n"
              "\tdo {                                              \\\n"
              "\t\tstatic std::atomic<int> bc5_pg_n {0};           \\\n"
              "\t\tbc5_pg(bc5_pg_n, __VA_ARGS__);                  \\\n"
              "\t} while (0)\n")
n = p.count("\tPRINT_NAME();\n")
assert n >= 18, n
p = p.replace("\tPRINT_NAME();\n", "\tPRINT_NAME();\n\tBC5_PG(\"%s\\n\", __func__);\n")
old = ("\t\tif (is_valid_chunk(chunk_ids[i])) {\n"
       "\t\t\tout_loci[i] = PLAYGO_LOCUS_LOCAL_FAST;\n"
       "\t\t} else {\n"
       "\t\t\treturn PLAYGO_ERROR_BAD_CHUNK_ID;\n"
       "\t\t}\n")
assert p.count(old) == 1
p = p.replace(old,
              "\t\tif (is_valid_chunk(chunk_ids[i])) {\n"
              "\t\t\tout_loci[i] = PLAYGO_LOCUS_LOCAL_FAST;\n"
              "\t\t\tBC5_PG(\"GetLocus chunk %u: local fast\\n\", static_cast<unsigned>(chunk_ids[i]));\n"
              "\t\t} else {\n"
              "\t\t\tBC5_PG(\"GetLocus chunk %u: BAD_CHUNK_ID (chunks %u)\\n\", static_cast<unsigned>(chunk_ids[i]), g_chunks_num);\n"
              "\t\t\treturn PLAYGO_ERROR_BAD_CHUNK_ID;\n"
              "\t\t}\n")
old = "\t\tLOGF(\"Warning: assume that chunks count is 1\\n\");\n"
assert p.count(old) == 1
p = p.replace(old, old + "\t\tstd::fputs(\"bc5 playgo: no chunk table read, assuming 1 chunk\\n\", stderr);\n")
open(pg, "w", encoding="utf-8").write(p)
print("edited", n, "functions traced")

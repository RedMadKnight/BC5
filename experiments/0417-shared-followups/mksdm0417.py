#!/usr/bin/env python3
"""BC5 experiment 0417, tag sdm417: ASTRO BOT's save data memory (README section 12). Puts sdm0417.inc in place of the
save-data-memory functions of src/libs/libSaveData.cpp (candidate B's unit, md5 0bd91bb4): the store per slot
(KYTY_BC5_SAVEDATA_MEMORY_SLOTS), the parameters and icon kept (KYTY_BC5_SAVEDATA_MEMORY_PARAM) and a call log
(KYTY_BC5_SAVEDATA_MEMORY_LOG). All three are off by default; with all off the calls do what they did.
usage: mksdm0417.py <libSaveData.cpp in> <sdm0417.inc> <libSaveData.cpp out>"""
import hashlib
import sys

src, inc, dst = sys.argv[1:4]
s = open(src, "rb").read()
b = open(inc, "rb").read()
assert b"\r" not in s and b"\r" not in b and b"sdm417" not in s
assert hashlib.md5(s).hexdigest()[:8] == "0bd91bb4", hashlib.md5(s).hexdigest()
A = b"static std::string save_data_memory_dir() {\n"
Z = b"int KYTY_SYSV_ABI SaveDataTransferringMount(const SaveDataTransferringMount* mount,\n"
assert s.count(A) == 1 and s.count(Z) == 1
i, j = s.index(A), s.index(Z)
old = s[i:j]
assert hashlib.md5(old).hexdigest()[:8] == "bf62dbdd", hashlib.md5(old).hexdigest()
s = s[:i] + b + b"\n" + s[j:]
a = b"\t\twritten = save_data_memory_store();\n"
assert s.count(a) == 1
s = s.replace(a, b"\t\twritten = save_data_memory_store(std::max(0, bc5_sdm_slot(sync_param->slot_id))); // exp 0417: the slot's own store with the switch on\n"
              b"\t\tif (bc5_sdm_log_on()) {\n"
              b"\t\t\tstd::fprintf(stderr, \"[bc5] sdm417 sync: slot %\" PRIu32 \" option %\" PRIu32 \": file %s\\n\", sync_param->slot_id, sync_param->option,\n"
              b"\t\t\t             written ? \"written\" : \"NOT WRITTEN\");\n"
              b"\t\t}\n")
open(dst, "wb").write(s)
print("libSaveData.cpp -> %s" % hashlib.md5(s).hexdigest()[:8])

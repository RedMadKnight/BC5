#!/usr/bin/env python3
"""BC5 experiment 0417, tag sdt417 (README section 16): sceSaveDataTransferringMount.
Found with the call log: ASTRO BOT, once it has a real save, calls SaveDataTransferringMount for ANOTHER title's save
(title_id PPSA01325, dir_name sce_sdmemory). The host ignored title_id, took the directory of that name under the
RUNNING title (its own save data memory directory), created it when absent, mounted it and answered OK with
"created"; the title then read our memory.dat as the other title's save and faulted at eboot+0x29c385.
KYTY_BC5_SAVEDATA_TRANSFER_FIX=1 (off by default: unset, empty or "0" is the old code):
  - the directory is _SaveData/<title_id of the call>/<dir_name> (the running title's when title_id is null or empty);
  - a title_id with '/' or '.' in it is PARAMETER;
  - a directory that does not exist is NOT created: the call answers SAVE_DATA_ERROR_NOT_FOUND (0x809F0008);
  - one that exists is mounted with status 0 (not "created").
TODO(verify): the console's own answer for a transfer source that does not exist; NOT_FOUND is the library's code
for a missing save and is what a title must handle on a console without the other title's save.
Applies to candidate C's unit (md5 a01e4b64, after mksdm0417.py).
usage: mksdt0417.py <libSaveData.cpp in> <libSaveData.cpp out>"""
import hashlib
import sys

src, dst = sys.argv[1:3]
s = open(src, "rb").read()
assert b"\r" not in s and b"sdt417" not in s
assert hashlib.md5(s).hexdigest()[:8] == "a01e4b64", hashlib.md5(s).hexdigest()


def once(old, new):
    global s
    assert s.count(old) == 1, (old[:70], s.count(old))
    s = s.replace(old, new)


once(b"int KYTY_SYSV_ABI SaveDataTransferringMount(const SaveDataTransferringMount* mount,\n",
     b"""// Experiment 0417 (tag sdt417): KYTY_BC5_SAVEDATA_TRANSFER_FIX, see the function below.
static bool bc5_sdt_on() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_SAVEDATA_TRANSFER_FIX");
		const bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
		std::fprintf(stderr, "[bc5] exp 0417: savedata transferring mount fix %s\\n", v ? "on" : "off");
		return v;
	}();
	return on;
}

int KYTY_SYSV_ABI SaveDataTransferringMount(const SaveDataTransferringMount* mount,
""")
once(b"""	const std::string mount_dir =
	    std::string(SAVE_DATA_DIR) + "/" + get_title_id() + "/" + dir_name;
	const int slot = g_mount_slots.FindAvailable(dir_name);
	if (slot == SaveDataMountSlots::BUSY) {
		return SAVE_DATA_ERROR_BUSY;
	}
	if (slot == SaveDataMountSlots::FULL) {
		return SAVE_DATA_ERROR_MOUNT_FULL;
	}

	if (!Common::File::IsDirectoryExisting(mount_dir)) {
		Common::File::CreateDirectories(mount_dir);
	}

	return mount_save_data(slot, dir_name, mount_dir, 1, mount_result);
""",
     b"""	// exp 0417 (tag sdt417): the save of the title the call names, never created here. Off: the old code, which took
	// the running title's directory of that name, created it and answered "created".
	const bool  bc5_fix   = bc5_sdt_on();
	std::string bc5_title = get_title_id();
	if (bc5_fix && mount->title_id != nullptr && mount->title_id->data[0] != '\\0') {
		bc5_title.assign(mount->title_id->data, strnlen(mount->title_id->data, sizeof(mount->title_id->data)));
		if (bc5_title.find('/') != std::string::npos || bc5_title.find('.') != std::string::npos) {
			return SAVE_DATA_ERROR_PARAMETER;
		}
	}
	const std::string mount_dir =
	    std::string(SAVE_DATA_DIR) + "/" + bc5_title + "/" + dir_name;
	if (bc5_fix && !Common::File::IsDirectoryExisting(mount_dir)) {
		std::fprintf(stderr, "[bc5] sdt417: transferring mount of %s/%s: no such save, NOT_FOUND (nothing created)\\n", bc5_title.c_str(),
		             dir_name.c_str());
		return SAVE_DATA_ERROR_NOT_FOUND;
	}
	const int slot = g_mount_slots.FindAvailable(dir_name);
	if (slot == SaveDataMountSlots::BUSY) {
		return SAVE_DATA_ERROR_BUSY;
	}
	if (slot == SaveDataMountSlots::FULL) {
		return SAVE_DATA_ERROR_MOUNT_FULL;
	}

	if (!Common::File::IsDirectoryExisting(mount_dir)) {
		Common::File::CreateDirectories(mount_dir);
	}
	if (bc5_fix) {
		std::fprintf(stderr, "[bc5] sdt417: transferring mount of %s/%s: mounted, not created\\n", bc5_title.c_str(), dir_name.c_str());
	}

	return mount_save_data(slot, dir_name, mount_dir, bc5_fix ? 0u : 1u, mount_result);
""")
open(dst, "wb").write(s)
print("libSaveData.cpp -> %s" % hashlib.md5(s).hexdigest()[:8])

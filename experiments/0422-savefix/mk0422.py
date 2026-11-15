#!/usr/bin/env python3
r"""BC5 experiment 0422 (tag sdt422): exp 0417's transferring-mount save fix (tag sdt417, F835) fixed on, no switch.
    mk0422.py <tree root>
on a tree whose src/libs/libSaveData.cpp holds exp 0417's switched fix as in the shared patch e3fd8b55.

Why: the maintainer (2026-11-15, to the top session): "Włącz poprawkę zapisu na stałe w kodzie." Behind
KYTY_BC5_SAVEDATA_TRANSFER_FIX (read with BC5_DIAG_ENV) the fix was off by default and compiled out of the lean build,
so a fresh install (an empty save directory) still met F833: ASTRO BOT's sceSaveDataTransferringMount for another
title's save (PPSA01325/sce_sdmemory) got the running title's own save memory, created and answered "created", and
every later start ended at 5 s.

Now always: the directory is the one of the title the call names; an absent save is not created and the call answers
NOT_FOUND; a present one is mounted with "not created" (mount_save_data(..., 0u, ...)). bc5_sdt_on() and the switch word
go. The two [bc5] sdt417 stderr lines stay, under #ifndef BC5_LEAN (lean has no diagnostics). The old block (from the
comment that names the switch through the end of SaveDataTransferringMount) must match byte for byte (md5 below)."""
import hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
sys.path.insert(0, HERE)  # on the box ed0419g.py is copied next to this script
from ed0419g import File

OLD_MD5 = "3721b9e56bd7fbcef489af11b0e3e9de"  # the old block with LF, as in the shared patch e3fd8b55
FIRST = "// Experiment 0417 (tag sdt417): KYTY_BC5_SAVEDATA_TRANSFER_FIX, see the function below.\n"
LAST = "\treturn mount_save_data(slot, dir_name, mount_dir, bc5_fix ? 0u : 1u, mount_result);\n}\n"

NEW = r'''int KYTY_SYSV_ABI SaveDataTransferringMount(const SaveDataTransferringMount* mount,
                                            SaveDataMountResult*             mount_result) {
	PRINT_NAME();
	sg412::Op sg_op(sg412::kLib, true); // exp 0412 (tag sg412)

	if (mount == nullptr || mount_result == nullptr || mount->dir_name == nullptr) {
		return SAVE_DATA_ERROR_PARAMETER;
	}

	LOGF("\t user_id  = %" PRId32 "\n"
	     "\t title_id = %s\n"
	     "\t dir_name = %s\n",
	     mount->user_id, mount->title_id != nullptr ? mount->title_id->data : "<null>",
	     mount->dir_name->data);

	*mount_result = {};

	Common::LockGuard lock(g_mount_mutex);
	const std::string dir_name = mount->dir_name->data;
	// exp 0417 (tag sdt417), always on since exp 0422 (tag sdt422): the save of the title the call names, never created
	// here. ASTRO BOT asks for ANOTHER title's save (PPSA01325/sce_sdmemory); the old code took the running title's
	// directory of that name, created it and answered "created", and the title then faulted reading its own file as the
	// other title's save: every start after a first save from an empty directory ended at 5 s (F833, F835).
	std::string bc5_title = get_title_id();
	if (mount->title_id != nullptr && mount->title_id->data[0] != '\0') {
		bc5_title.assign(mount->title_id->data, strnlen(mount->title_id->data, sizeof(mount->title_id->data)));
		if (bc5_title.find('/') != std::string::npos || bc5_title.find('.') != std::string::npos) {
			return SAVE_DATA_ERROR_PARAMETER;
		}
	}
	const std::string mount_dir =
	    std::string(SAVE_DATA_DIR) + "/" + bc5_title + "/" + dir_name;
	if (!Common::File::IsDirectoryExisting(mount_dir)) {
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] sdt417: transferring mount of %s/%s: no such save, NOT_FOUND (nothing created)\n", bc5_title.c_str(),
		             dir_name.c_str());
#endif
		return SAVE_DATA_ERROR_NOT_FOUND;
	}
	const int slot = g_mount_slots.FindAvailable(dir_name);
	if (slot == SaveDataMountSlots::BUSY) {
		return SAVE_DATA_ERROR_BUSY;
	}
	if (slot == SaveDataMountSlots::FULL) {
		return SAVE_DATA_ERROR_MOUNT_FULL;
	}
#ifndef BC5_LEAN
	std::fprintf(stderr, "[bc5] sdt417: transferring mount of %s/%s: mounted, not created\n", bc5_title.c_str(), dir_name.c_str());
#endif

	return mount_save_data(slot, dir_name, mount_dir, 0u, mount_result);
}
'''

root = sys.argv[1]
f = File(os.path.join(root, "src", "libs", "libSaveData.cpp"))
f.gone("tag sdt422")  # not applied twice
first, last = f._c(FIRST), f._c(LAST)
assert f.b.count(first) == 1, "%d matches of the switch comment" % f.b.count(first)
a = f.b.index(first)
e = f.b.index(last, a) + len(last)
old = f.b[a:e].replace(b"\r\n", b"\n")
assert hashlib.md5(old).hexdigest() == OLD_MD5, "the old block is not e3fd8b55's: md5 %s" % hashlib.md5(old).hexdigest()
f.cut(FIRST, LAST, NEW)
f.gone("KYTY_BC5_SAVEDATA_TRANSFER_FIX", "bc5_sdt_on", "bc5_fix")
assert f.b.count(b"tag sdt422") == 1 and f.b.count(b"sdt417:") == 2
f.save()

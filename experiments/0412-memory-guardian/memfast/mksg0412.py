#!/usr/bin/env python3
"""BC5 experiment 0412, tag sg412 (README section 65): the SAVE GUARD of the fault record.
The fault record (tag fr412, mkfr0412.py, BC5_FAULT_RECORD) ends the game at a GPU fault; the maintainer plays on his
live saves, so that exit must not cut a save. The title's saves are written through the host's own calls, so the host
knows when one is being written. This script puts saveguard0412.inc into the tree as src/bc5/save_guard0412.hpp and
marks the host calls that touch save storage with sg412::Op:
  src/kernel/fileSystem.cpp   open (a write, create or truncate open counts as a write), close, write, pwrite,
                              ftruncate, truncate, fsync, unlink, rename, mkdir, rmdir: only for names under a save
                              mount ("/savedata<n>"); every other file is untouched (one string compare)
  src/libs/libSaveData.cpp    mount (the slot becomes "clean", the directory is noted for the sync), unmount (the slot
                              ends), the mounts and the library's own writers (delete, the save-data memory, the
                              parameters, the icon by path; SaveDataSaveIcon writes nothing on the host)
The wait itself (sg412::close) is called from fr412_record_and_exit only. Without BC5_FAULT_RECORD and a GPU fault no
call is ever held or changed: the marks cost two atomic adds on a save call.
usage: mksg0412.py <tree in (src/kernel/fileSystem.cpp, src/libs/libSaveData.cpp)> <out dir> <saveguard0412.inc>"""
import hashlib
import os
import sys

T = b" // exp 0412 (tag sg412)\n"
INC = b'#include "bc5/save_guard0412.hpp" // exp 0412 (tag sg412): the save guard of the fault record\n'


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def after_name(s, head, line, between=b""):
    """the guard's line right after PRINT_NAME() of the function that starts with `head`"""
    a = head + b"\n" + between + b"\tPRINT_NAME();\n"
    return once(s, a, a + b"\t" + line + T)


def file_system(s):
    assert b"\r" not in s and b"tag sg412" not in s
    s = once(s, b'#include "kernel/fileSystem.h"\n', b'#include "kernel/fileSystem.h"\n' + INC)
    a = b"static FileDescriptors* g_files        = nullptr;\n"
    s = once(s, a, a + b"""// Experiment 0412 (tag sg412): the save mount a descriptor's file lies on, or sg412::kNone.
static int Bc5SgFd(int d) {
	if (g_files == nullptr || d < DESCRIPTOR_MIN) return sg412::kNone;
	auto* file = g_files->GetFile(d);
	return (file != nullptr && file->opened) ? sg412::slot_of(file->name.c_str()) : sg412::kNone;
}
""")
    fd_w = b"sg412::Op sg_op(Bc5SgFd(d), true);"
    fd_r = b"sg412::Op sg_op(Bc5SgFd(d), false);"
    path_w = b"sg412::Op sg_op(sg412::slot_of(path), true);"
    s = after_name(s, b"int KYTY_SYSV_ABI KernelOpen(const char* path, int flags, uint16_t mode) {",
                   b"sg412::Op sg_op(sg412::slot_of(path), (static_cast<uint32_t>(flags) & 0x0603u) != 0); // FreeBSD: O_WRONLY 1, O_RDWR 2, O_CREAT 0x200, O_TRUNC 0x400",
                   b"\tbc5::load_stat::Scope ls_scope(bc5::load_stat::kFileOpen); // experiment 0415 (ls415)\n")
    s = after_name(s, b"int KYTY_SYSV_ABI KernelClose(int d) {", fd_r)
    s = after_name(s, b"int64_t KYTY_SYSV_ABI KernelWrite(int d, const void* buf, size_t nbytes) {", fd_w)
    s = after_name(s, b"int64_t KYTY_SYSV_ABI KernelPwrite(int d, const void* buf, size_t nbytes, int64_t offset) {", fd_w)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelFtruncate(int d, int64_t length) {", fd_w)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelTruncate(const char* path, int64_t length) {", path_w)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelFsync(int d) {", fd_r)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelUnlink(const char* path) {", path_w)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelRename(const char* from, const char* to) {",
                   b"sg412::Op sg_op(sg412::slot_of(to) != sg412::kNone ? sg412::slot_of(to) : sg412::slot_of(from), true);")
    s = after_name(s, b"int KYTY_SYSV_ABI KernelMkdir(const char* path, uint16_t mode) {", path_w)
    s = after_name(s, b"int KYTY_SYSV_ABI KernelRmdir(const char* path) {", path_w)
    assert s.index(b"constexpr int DESCRIPTOR_MIN = 3;") < s.index(b"static int Bc5SgFd(int d) {")
    return s


def save_data(s):
    assert b"\r" not in s and b"tag sg412" not in s
    a = b"static constexpr char     SAVE_DATA_DIR[]      = \"_SaveData\";\n"
    s = once(s, a, INC + a)
    a = b"\tg_mount_slots.Mount(static_cast<size_t>(slot), dir_name);\n"
    s = once(s, a, a + b"\tsg412::note_root(directory.c_str());" + T + b"\tsg412::mounted(slot);" + T)
    a = b"\tLibKernel::FileSystem::Umount(point);\n\tg_mount_slots.Release(static_cast<size_t>(slot));\n"
    s = once(s, a, a + b"\tsg412::unmounted(slot);" + T)
    lib_w = b"sg412::Op sg_op(sg412::kLib, true);"
    mp_w = b"sg412::Op sg_op(mount_point != nullptr ? sg412::slot_of(mount_point->data) : sg412::kNone, true); // a part of the save on that mount"
    for head in (b"int KYTY_SYSV_ABI SaveDataMount3(const SaveDataMount3* mount, SaveDataMountResult* mount_result) {",
                 b"int KYTY_SYSV_ABI SaveDataDelete(const SaveDataDelete* del) {",
                 b"int KYTY_SYSV_ABI SaveDataSetSaveDataMemory2(const SaveDataMemorySet2* set_param) {",
                 b"int KYTY_SYSV_ABI SaveDataSyncSaveDataMemory(const void* sync_param) {"):
        s = after_name(s, head, lib_w)
    for head in (b"int KYTY_SYSV_ABI SaveDataTransferringMount(const SaveDataTransferringMount* mount,",
                 b"int KYTY_SYSV_ABI SaveDataSetParam(const SaveDataMountPoint* mount_point, uint32_t param_type,",
                 b"int KYTY_SYSV_ABI SaveDataSaveIconByPath(const SaveDataMountPoint* mount_point, const char* path) {"):
        i = s.index(head)
        assert s.count(head) == 1
        j = s.index(b"\tPRINT_NAME();\n", i)
        assert j - i < 400 and b"\n}\n" not in s[i:j], ("PRINT_NAME is not in this function's head", head[:50])
        j += len(b"\tPRINT_NAME();\n")
        s = s[:j] + b"\t" + (lib_w if b"TransferringMount" in head else mp_w) + T + s[j:]
    return s


def main():
    assert len(sys.argv) == 4 and sys.argv[1] != sys.argv[2], __doc__
    src, out, inc = sys.argv[1:4]
    h = open(inc, "rb").read()
    assert b"\r" not in h and b"namespace sg412 {" in h
    for rel, fn in (("src/kernel/fileSystem.cpp", file_system), ("src/libs/libSaveData.cpp", save_data)):
        s = fn(open(os.path.join(src, rel), "rb").read())
        os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
        open(os.path.join(out, rel), "wb").write(s)
        print(f"{rel} {hashlib.md5(s).hexdigest()}")
    os.makedirs(os.path.join(out, "src/bc5"), exist_ok=True)
    open(os.path.join(out, "src/bc5/save_guard0412.hpp"), "wb").write(h)
    print(f"src/bc5/save_guard0412.hpp {hashlib.md5(h).hexdigest()}")


if __name__ == "__main__":
    main()

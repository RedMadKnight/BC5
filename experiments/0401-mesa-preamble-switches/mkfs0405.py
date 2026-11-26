#!/usr/bin/env python3
"""BC5 experiment 0401 series e5 (exp 0405's ports), tag fs: the file system items of exp 0405's top-32 table and their
POSIX return conventions, in src/kernel/fileSystem.cpp and src/libs/libKernel.cpp (registrations).
  KYTY_BC5_FS_FIXES (fileSystem.cpp), items:
    kk04         R2 KK04 (+SK02): sceKernelRename of an open file (source or target) and of a directory (today: EXIT,
                 ENOENT); open descriptors follow a rename, a replaced or unlinked file's descriptors lose its name.
    sk04         R2 SK04 (+KK09): KernelOpen without EXITs (O_ACCMODE 3 -> EINVAL; a directory opened for writing, with
                 O_TRUNC or O_CREAT -> EISDIR, EEXIST with O_EXCL); the O_TRUNC|O_RDONLY EACCES path frees its descriptor.
    blksize      R1 #12: directories report st_blksize 0x10000 (stat, fstat).
    nametoolong  R1 #13: ENAMETOOLONG for >= 1024 bytes or a component over 255 (open, stat, unlink, rename, mkdir,
                 rmdir, CheckReachability); mkdir and CheckReachability no longer refuse every path over 255 bytes.
    kk10         R2 KK10: write/pwrite on a descriptor not open for writing -> EBADF.
    sk05         R2 SK05 (+KK35): guest paths normalised ("." / ".." / "//"), the longest mount point wins, a mount point
                 named without its '/' is the mount point.
  KYTY_BC5_POSIX_RET_FIXES (libKernel.cpp registrations, read when the library is loaded), items:
    unlink, munmap, mprotect, trywrlock  R1 #9, R2 SK06, R3 M15: the posix NIDs VAzswvTOCzI, UqDGjXA5yUM, YQOfxL4QfeU,
                 XhWHn6P5R7U get wrappers that answer -1 and errno (pthread: the errno number) for an SCE error code;
    schedparam, once  R2 SK06: the sce NIDs P41kTWUS3EI, oIRFTjoILbg, 14bOACANTBo get wrappers that answer SCE codes
                 where today's posix functions answer errno numbers.
  Each switch: unset, empty or "0" is off (today's code path in every edited function, today's registrations); any other
  value turns all its items on, unless it names items (comma-separated): then only those. One stderr line each:
  "[bc5] exp 0405: fs fixes on (items: ...)" / "... off" at the FileSystem subsystem's init, "[bc5] exp 0405: posix return
  fixes on (items: ...)" / "... off" when libkernel's table is built.
Inputs: the e5 input tree (KytyPlus f266548 + patch 0001 + e4's units); both files are the base tree's (LF). Each input's
md5 is asserted, each anchor must occur exactly once and keep the brace/parenthesis balance, a file that has the edit is
refused, and every NID the script registers is checked against its name (lesson R32). Prints "<rel> <md5>" per output.
usage: mkfs0405.py <tree root> <out dir>"""
import hashlib
import os
import sys

FS = "src/kernel/fileSystem.cpp"
LK = "src/libs/libKernel.cpp"
IN_MD5 = {
    FS: "f1b5f5288faddd78deff2dbd1b613e1f",
    LK: "3bf94a6168d176d591730bac33dff5b1",
}
MARK = b"experiment 0405"


def T(s):
    """The texts below are written with '»' for a tab (raw strings: a C++ backslash stays as it is)."""
    return s.replace("»", "\t").encode("utf-8")


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def once(s, old, new, what, keep_balance=True):
    assert s.count(old) == 1, (what, old[:120], s.count(old))
    if keep_balance:
        assert balance(old) == balance(new), ("the edit changes the balance", what, balance(old), balance(new))
    return s.replace(old, new)


# ======================================================================================================================
# src/kernel/fileSystem.cpp
# ======================================================================================================================

FS_BLOCK_ANCHOR = T(r"""static int PosixToKernel(int posix_errno) {
»return KERNEL_ERROR_UNKNOWN + posix_errno;
}
""")

FS_BLOCK = T(r"""
// ---- experiment 0405 (BC5 exp 0401 series e5), KYTY_BC5_FS_FIXES: exp 0405's file system ports -----------------------
// Read once, at the FileSystem subsystem's init: one stderr line, "[bc5] exp 0405: fs fixes on (items: ...)" or "... off".
// Unset, empty or "0" is off, and every edited function takes today's path. Any other value turns every item on, unless
// it names items (comma-separated): then only those.
//   kk04         sceKernelRename of an open file (source or target) and of a directory, where today's code EXITs
//                (either path open) or answers ENOENT (a directory). KytyPS5 dfec14a src/kernel/fileSystem.cpp:1398-1430
//                (GPL-2.0) renames without looking at open files; sharpemu 1811cef "[Kernel] Allow renaming and
//                unlinking open guest files" (SharpEmu.Libs/Kernel/KernelFileExtendedExports.cs:330-380 @ 514d766,
//                GPL-2.0-or-later) moves a directory or a file over its target. Adapted: open descriptors follow a
//                rename; a replaced or unlinked file's descriptors keep their file and lose its host name, so that the
//                path functions that look an open file up by its host name do not take it for a newer file of that name.
//   sk04         KernelOpen without EXITs: O_ACCMODE 3 is EINVAL; a directory opened for writing, with O_TRUNC or with
//                O_CREAT is EISDIR (EEXIST with O_CREAT|O_EXCL); the O_TRUNC|O_RDONLY EACCES path frees its descriptor
//                (KK09). sharpemu 956da76 (KernelMemoryCompatExports.cs:1512-1530, 4827-4839 @ 514d766,
//                GPL-2.0-or-later) refuses these opens; KytyPS5 dfec14a src/kernel/fileSystem.cpp:495-498 (GPL-2.0)
//                frees the descriptor. The error values are FreeBSD's (kern_openat: O_ACCMODE 3 -> EINVAL, the same
//                check in obhq/obliteration 2a53d5c legacy/src/fs/mod.rs:393-400, MIT/Apache-2.0; vn_open_cred /
//                vn_open_vnode: EEXIST, then EISDIR), not measured on a console: TODO(verify).
//   blksize      directories report st_blksize 0x10000 (stat, fstat). AnyPS5 da7581eec
//                core/libs/prx/libkernel/File/src/NativeStat.cpp:224 @ 4f41f4c37 (GPL-2.0-only), after the PS4 Pro 10.71
//                measurement its commit cites (not a PS5: TODO(verify)).
//   nametoolong  ENAMETOOLONG for a path of 1024 bytes or more or a component over 255 bytes (FreeBSD MAXPATHLEN,
//                NAME_MAX) in open, stat, unlink, rename, mkdir, rmdir and CheckReachability; mkdir and
//                CheckReachability no longer refuse every path over 255 bytes. AnyPS5 2de34f87b
//                core/libs/prx/libc/src/General.cpp:386-388 @ 4f41f4c37 (GPL-2.0-only); the length rule of this file's
//                CheckGuestPath (experiment 0327).
//   kk10         write and pwrite on a descriptor that is not open for writing are EBADF. KytyPS5 dfec14a
//                src/kernel/fileSystem.cpp:722, 940 (GPL-2.0).
//   sk05         guest paths normalised before the mount search ("." dropped, ".." up one level but never above "/",
//                "//" folded; relative paths as they are), the longest matching mount point wins, and a mount point
//                named without its '/' (open("/app0", 0)) is the mount point (KK35). sharpemu 9ff60ab, e01092a
//                (KernelMemoryCompatExports.cs:5070-5110, 5176-5203 @ 514d766, GPL-2.0-or-later). Unlike sharpemu, the
//                whole guest path is normalised: "/app0/.." is "/", under no mount. Lexical, as sharpemu: "/app0/x/../f"
//                is "/app0/f" even when x does not exist (FreeBSD's namei would answer ENOENT).
// The upstream projects' copyrights remain with their authors; GPL-2.0, as the rest of this file.
static constexpr uint32_t BC5_FS_KK04        = 1u << 0u;
static constexpr uint32_t BC5_FS_SK04        = 1u << 1u;
static constexpr uint32_t BC5_FS_BLKSIZE     = 1u << 2u;
static constexpr uint32_t BC5_FS_NAMETOOLONG = 1u << 3u;
static constexpr uint32_t BC5_FS_KK10        = 1u << 4u;
static constexpr uint32_t BC5_FS_SK05        = 1u << 5u;

struct Bc5FsItem {
»const char* name;
»uint32_t    bit;
};

static constexpr Bc5FsItem BC5_FS_ITEMS[] = {
    {"kk04", BC5_FS_KK04},        {"sk04", BC5_FS_SK04}, {"blksize", BC5_FS_BLKSIZE},
    {"nametoolong", BC5_FS_NAMETOOLONG}, {"kk10", BC5_FS_KK10}, {"sk05", BC5_FS_SK05},
};

static uint32_t Bc5FsFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (const auto& item: BC5_FS_ITEMS) {
»»»if (std::strlen(item.name) == n && std::strncmp(p, item.name, n) == 0) {
»»»»items |= item.bit;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»if (items == 0) {
»»for (const auto& item: BC5_FS_ITEMS) {
»»»items |= item.bit;
»»}
»}
»return items;
}

// The items of KYTY_BC5_FS_FIXES that are on (0: off), read once.
static uint32_t Bc5FsFixes() {
»static const uint32_t items = [] {
»»const uint32_t v = Bc5FsFixesParse(std::getenv("KYTY_BC5_FS_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: fs fixes off\n");
»»} else {
»»»std::string names;
»»»for (const auto& item: BC5_FS_ITEMS) {
»»»»if ((v & item.bit) != 0) {
»»»»»names += names.empty() ? "" : " ";
»»»»»names += item.name;
»»»»}
»»»}
»»»std::fprintf(stderr, "[bc5] exp 0405: fs fixes on (items: %s)\n", names.c_str());
»»}
»»std::fflush(stderr);
»»return v;
»}();
»return items;
}

static bool Bc5FsFix(uint32_t item) {
»return (Bc5FsFixes() & item) != 0;
}

// nametoolong: a path of 1024 bytes or more, or a component over 255 bytes (CheckGuestPath's length rule).
static bool Bc5PathTooLong(const char* path) {
»size_t component_length = 0;
»for (size_t i = 0; path[i] != '\0'; ++i) {
»»if (i >= 1023) {
»»»return true;
»»}
»»if (path[i] == '/') {
»»»component_length = 0;
»»} else if (++component_length > 255) {
»»»return true;
»»}
»}
»return false;
}

// sk05: an absolute guest path with "." dropped, ".." up one level (never above "/") and repeated '/' folded; a path
// whose last component was empty, "." or ".." keeps one trailing '/' (the directory form). Relative paths as they are.
static std::string Bc5NormalizeGuestPath(const std::string& path) {
»if (path.empty() || path[0] != '/') {
»»return path;
»}
»std::vector<std::string> parts;
»bool                     trailing = false;
»size_t                   pos      = 1;
»for (;;) {
»»const size_t      next = path.find('/', pos);
»»const std::string part = path.substr(pos, next == std::string::npos ? std::string::npos : next - pos);
»»trailing               = part.empty() || part == "." || part == "..";
»»if (part == "..") {
»»»if (!parts.empty()) {
»»»»parts.pop_back();
»»»}
»»} else if (!part.empty() && part != ".") {
»»»parts.push_back(part);
»»}
»»if (next == std::string::npos) {
»»»break;
»»}
»»pos = next + 1;
»}
»std::string out;
»for (const auto& part: parts) {
»»out += '/';
»»out += part;
»}
»if (out.empty()) {
»»return "/";
»}
»if (trailing) {
»»out += '/';
»}
»return out;
}

// sk05: of the mount points mounted_path starts with, the longest (today's code takes the first).
static std::vector<MountPoints::MountPair>::iterator Bc5LongestMount(std::vector<MountPoints::MountPair>& pairs,
                                                                      const std::string&                   mounted_path) {
»auto best = pairs.end();
»for (auto p = pairs.begin(); p != pairs.end(); ++p) {
»»if (Common::StartsWith(mounted_path, p->point) && (best == pairs.end() || p->point.size() > best->point.size())) {
»»»best = p;
»»}
»}
»return best;
}
// ---- end of experiment 0405's helpers -------------------------------------------------------------------------------
""")

FS_EDITS = (
    ("FileDescriptors: the two kk04 methods (declarations)",
     T(r"""»void  CloseAll();
"""),
     T(r"""»void  CloseAll();
»void  Bc5Forget(const std::filesystem::path& real_name);                         // experiment 0405 (kk04)
»void  Bc5Rename(const std::filesystem::path& from, const std::filesystem::path& to); // experiment 0405 (kk04)
""")),
    ("FileDescriptors: the two kk04 methods (definitions)",
     T(r"""void FileDescriptors::CloseAll() {
»Common::LockGuard lock(m_mutex);

»for (auto& f: m_files) {
»»if (f != nullptr && f->opened) {
»»»f->f.Close();
»»»delete f;
»»»f = nullptr;
»»}
»}
}
"""),
     T(r"""void FileDescriptors::CloseAll() {
»Common::LockGuard lock(m_mutex);

»for (auto& f: m_files) {
»»if (f != nullptr && f->opened) {
»»»f->f.Close();
»»»delete f;
»»»f = nullptr;
»»}
»}
}

// Experiment 0405 (KYTY_BC5_FS_FIXES kk04): a host name, compared without its trailing '/' (a directory opened with
// O_DIRECTORY keeps its name with one).
static std::string Bc5HostKey(const std::filesystem::path& p) {
»std::string s = p.generic_string();
»while (s.size() > 1 && s.back() == '/') {
»»s.pop_back();
»}
»return s;
}

// Experiment 0405 (kk04): the descriptors of a file that was replaced or unlinked keep their file (Linux keeps an open
// file's inode) and lose its host name, so that the path functions that look an open file up by its host name
// (KernelTruncate, KernelUnlink) do not take them for a newer file of that name (sharpemu 1811cef's rule).
void FileDescriptors::Bc5Forget(const std::filesystem::path& real_name) {
»const std::string key = Bc5HostKey(real_name);
»if (key.empty()) {
»»return;
»}
»Common::LockGuard lock(m_mutex);
»for (auto* f: m_files) {
»»if (f != nullptr && !f->real_name.empty() && Bc5HostKey(f->real_name) == key) {
»»»Common::LockGuard file_lock(f->mutex);
»»»f->real_name.clear();
»»}
»}
}

// Experiment 0405 (kk04): after a rename on the host the open descriptors follow it, as on FreeBSD (a descriptor names
// a vnode, not a path): those of the source and of anything under a renamed directory take the new host name, those of
// a replaced target lose theirs (Bc5Forget).
void FileDescriptors::Bc5Rename(const std::filesystem::path& from, const std::filesystem::path& to) {
»const std::string from_key = Bc5HostKey(from);
»const std::string to_key   = Bc5HostKey(to);
»if (from_key.empty() || to_key.empty() || from_key == to_key) {
»»return;
»}
»Bc5Forget(to);
»Common::LockGuard lock(m_mutex);
»for (auto* f: m_files) {
»»if (f == nullptr || f->real_name.empty()) {
»»»continue;
»»}
»»const std::string s = Bc5HostKey(f->real_name);
»»if (s == from_key) {
»»»Common::LockGuard file_lock(f->mutex);
»»»f->real_name = to;
»»} else if (s.size() > from_key.size() && s.compare(0, from_key.size(), from_key) == 0 && s[from_key.size()] == '/') {
»»»Common::LockGuard file_lock(f->mutex);
»»»f->real_name = std::filesystem::path(to_key + s.substr(from_key.size()));
»»}
»}
}
""")),
    ("GetRealFilename: sk05",
     T(r"""std::filesystem::path MountPoints::GetRealFilename(const std::string& mounted_file_name) {
»Common::LockGuard lock(m_mutex);

»auto mounted_path =
»    Common::DirectoryWithoutFilename(Common::FixFilenameSlash(mounted_file_name));

»const auto it = std::find_if(
»    m_mount_pairs.begin(), m_mount_pairs.end(),
»    [&mounted_path](const MountPair& p) { return Common::StartsWith(mounted_path, p.point); });
"""),
     T(r"""std::filesystem::path MountPoints::GetRealFilename(const std::string& bc5_guest_name) {
»Common::LockGuard lock(m_mutex);

»// Experiment 0405 (KYTY_BC5_FS_FIXES sk05): off, mounted_file_name is the caller's name, as today; on, the normalised
»// name, in the directory form when it names a mount point without its '/' (KK35).
»const bool  bc5_sk05 = Bc5FsFix(BC5_FS_SK05);
»std::string bc5_normalized;
»if (bc5_sk05) {
»»bc5_normalized = Bc5NormalizeGuestPath(Common::FixFilenameSlash(bc5_guest_name));
»»for (const auto& p: m_mount_pairs) {
»»»if (bc5_normalized + "/" == p.point) {
»»»»bc5_normalized += "/";
»»»»break;
»»»}
»»}
»}
»const std::string& mounted_file_name = bc5_sk05 ? bc5_normalized : bc5_guest_name;

»auto mounted_path =
»    Common::DirectoryWithoutFilename(Common::FixFilenameSlash(mounted_file_name));

»auto it = std::find_if(
»    m_mount_pairs.begin(), m_mount_pairs.end(),
»    [&mounted_path](const MountPair& p) { return Common::StartsWith(mounted_path, p.point); });
»if (bc5_sk05) {
»»it = Bc5LongestMount(m_mount_pairs, mounted_path); // experiment 0405 (sk05): the longest mount point
»}
""")),
    ("GetRealDirectory: sk05",
     T(r"""std::filesystem::path MountPoints::GetRealDirectory(const std::string& mounted_directory) {
»Common::LockGuard lock(m_mutex);

»auto mounted_path = Common::FixDirectorySlash(mounted_directory);

»const auto it = std::find_if(
»    m_mount_pairs.begin(), m_mount_pairs.end(),
»    [&mounted_path](const MountPair& p) { return Common::StartsWith(mounted_path, p.point); });
"""),
     T(r"""std::filesystem::path MountPoints::GetRealDirectory(const std::string& bc5_guest_directory) {
»Common::LockGuard lock(m_mutex);

»// Experiment 0405 (KYTY_BC5_FS_FIXES sk05): off, mounted_directory is the caller's name, as today; on, normalised.
»const bool  bc5_sk05 = Bc5FsFix(BC5_FS_SK05);
»std::string bc5_normalized;
»if (bc5_sk05) {
»»bc5_normalized = Bc5NormalizeGuestPath(Common::FixFilenameSlash(bc5_guest_directory));
»}
»const std::string& mounted_directory = bc5_sk05 ? bc5_normalized : bc5_guest_directory;

»auto mounted_path = Common::FixDirectorySlash(mounted_directory);

»auto it = std::find_if(
»    m_mount_pairs.begin(), m_mount_pairs.end(),
»    [&mounted_path](const MountPair& p) { return Common::StartsWith(mounted_path, p.point); });
»if (bc5_sk05) {
»»it = Bc5LongestMount(m_mount_pairs, mounted_path); // experiment 0405 (sk05): the longest mount point
»}
""")),
    ("the subsystem's init: the switch's line",
     T(r"""KYTY_SUBSYSTEM_INIT(FileSystem) {
»g_mount_points = new MountPoints;
»g_files        = new FileDescriptors;
}
"""),
     T(r"""KYTY_SUBSYSTEM_INIT(FileSystem) {
»g_mount_points = new MountPoints;
»g_files        = new FileDescriptors;
»(void)Bc5FsFixes(); // experiment 0405: reads KYTY_BC5_FS_FIXES once and prints its line, on or off
}
""")),
    ("KernelOpen: nametoolong",
     T(r"""»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»auto flags_u = static_cast<uint32_t>(flags);
"""),
     T(r"""»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»if (Bc5FsFix(BC5_FS_NAMETOOLONG) && Bc5PathTooLong(path)) { // experiment 0405 (nametoolong)
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»auto flags_u = static_cast<uint32_t>(flags);
""")),
    ("KernelOpen: sk04, O_ACCMODE 3 and the O_DIRECTORY EXITs",
     T(r"""»»default: EXIT("invalid flag_u: %u\n", flags_u);
»}

»EXIT_NOT_IMPLEMENTED(directory && rw_mode != Common::File::Mode::Read);
»EXIT_NOT_IMPLEMENTED(directory && (trunc || creat));
"""),
     T(r"""»»default:
»»»if (Bc5FsFix(BC5_FS_SK04)) { // experiment 0405 (sk04): O_ACCMODE 3 is EINVAL (FreeBSD kern_openat)
»»»»return KERNEL_ERROR_EINVAL;
»»»}
»»»EXIT("invalid flag_u: %u\n", flags_u);
»}

»// Experiment 0405 (sk04): with the switch on these opens go on to the directory branch below: EISDIR for a directory
»// (EEXIST with O_CREAT|O_EXCL), ENOTDIR for another file, ENOENT for a missing one. Off, today's EXITs.
»if (!Bc5FsFix(BC5_FS_SK04)) {
»»EXIT_NOT_IMPLEMENTED(directory && rw_mode != Common::File::Mode::Read);
»»EXIT_NOT_IMPLEMENTED(directory && (trunc || creat));
»}
""")),
    ("KernelOpen: sk04 (KK09), the EACCES path frees its descriptor",
     T(r"""»if (trunc && rw_mode == Common::File::Mode::Read) {
»»return KERNEL_ERROR_EACCES;
»}
"""),
     T(r"""»if (trunc && rw_mode == Common::File::Mode::Read) {
»»if (Bc5FsFix(BC5_FS_SK04)) { // experiment 0405 (sk04, KK09): KytyPS5 dfec14a fileSystem.cpp:495-498
»»»g_files->DeleteDescriptor(descriptor);
»»}
»»return KERNEL_ERROR_EACCES;
»}
""")),
    ("KernelOpen: sk04, a directory opened for writing",
     T(r"""»»EXIT_NOT_IMPLEMENTED(!directory && rw_mode != Common::File::Mode::Read);
»»EXIT_NOT_IMPLEMENTED(!directory && (trunc || creat));
"""),
     T(r"""»»if (Bc5FsFix(BC5_FS_SK04)) { // experiment 0405 (sk04): FreeBSD vn_open_cred / vn_open_vnode
»»»if (rw_mode != Common::File::Mode::Read || trunc || creat) {
»»»»g_files->DeleteDescriptor(descriptor);
»»»»return (creat && excl) ? KERNEL_ERROR_EEXIST : KERNEL_ERROR_EISDIR;
»»»}
»»} else {
»»»EXIT_NOT_IMPLEMENTED(!directory && rw_mode != Common::File::Mode::Read);
»»»EXIT_NOT_IMPLEMENTED(!directory && (trunc || creat));
»»}
""")),
    ("KernelWrite: kk10",
     T(r"""»»const auto result = ::Libs::Network::Net::Send(d, buf, nbytes, 0);
»»return (result >= 0 ? result : PosixToKernel(*Posix::GetErrorAddr()));
»}

»auto* file = g_files->GetFile(d);

»if (file == nullptr) {
»»return KERNEL_ERROR_EBADF;
»}
"""),
     T(r"""»»const auto result = ::Libs::Network::Net::Send(d, buf, nbytes, 0);
»»return (result >= 0 ? result : PosixToKernel(*Posix::GetErrorAddr()));
»}

»auto* file = g_files->GetFile(d);

»if (file == nullptr) {
»»return KERNEL_ERROR_EBADF;
»}

»if (Bc5FsFix(BC5_FS_KK10) && (!file->opened || !file->writable)) { // experiment 0405 (kk10): KytyPS5 dfec14a :722
»»return KERNEL_ERROR_EBADF;
»}
""")),
    ("KernelPwrite: kk10",
     T(r"""»auto* file = g_files->GetFile(d);

»if (file == nullptr) {
»»return KERNEL_ERROR_EBADF;
»}

»if (file->directory) {
»»return KERNEL_ERROR_EISDIR;
»}
»if (file->special != SpecialFile::None) {
»»return KERNEL_ERROR_EOPNOTSUPP;
»}

»EXIT_IF(!file->opened);

»if (nbytes > UINT_MAX) {
»»return KERNEL_ERROR_EOPNOTSUPP;
»}

»file->mutex.Lock();

»bool     is_invalid    = file->f.IsInvalid();
»auto     pos           = file->f.Tell();
"""),
     T(r"""»auto* file = g_files->GetFile(d);

»if (file == nullptr) {
»»return KERNEL_ERROR_EBADF;
»}

»if (Bc5FsFix(BC5_FS_KK10) && (!file->opened || !file->writable)) { // experiment 0405 (kk10): KytyPS5 dfec14a :940
»»return KERNEL_ERROR_EBADF;
»}

»if (file->directory) {
»»return KERNEL_ERROR_EISDIR;
»}
»if (file->special != SpecialFile::None) {
»»return KERNEL_ERROR_EOPNOTSUPP;
»}

»EXIT_IF(!file->opened);

»if (nbytes > UINT_MAX) {
»»return KERNEL_ERROR_EOPNOTSUPP;
»}

»file->mutex.Lock();

»bool     is_invalid    = file->f.IsInvalid();
»auto     pos           = file->f.Tell();
""")),
    ("KernelStat: nametoolong",
     T(r"""»if (path == nullptr || sb == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»LOGF("\t KernelStat: %s\n", path);
"""),
     T(r"""»if (path == nullptr || sb == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»if (Bc5FsFix(BC5_FS_NAMETOOLONG) && Bc5PathTooLong(path)) { // experiment 0405 (nametoolong)
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»LOGF("\t KernelStat: %s\n", path);
""")),
    ("KernelStat: blksize",
     T(r"""»if (is_dir) {
»»stat.st_size    = 0;
»»stat.st_blksize = 512;
»»stat.st_blocks  = 0;
»} else {
"""),
     T(r"""»if (is_dir) {
»»stat.st_size    = 0;
»»stat.st_blksize = Bc5FsFix(BC5_FS_BLKSIZE) ? 0x10000u : 512u; // experiment 0405 (blksize): AnyPS5 da7581eec
»»stat.st_blocks  = 0;
»} else {
""")),
    ("KernelFstat: blksize",
     T(r"""»} else {
»»stat.st_size    = 0;
»»stat.st_blksize = 512;
»»stat.st_blocks  = 0;
»}
"""),
     T(r"""»} else {
»»stat.st_size    = 0;
»»stat.st_blksize = Bc5FsFix(BC5_FS_BLKSIZE) ? 0x10000u : 512u; // experiment 0405 (blksize): AnyPS5 da7581eec
»»stat.st_blocks  = 0;
»}
""")),
    ("KernelUnlink: nametoolong",
     T(r"""int KYTY_SYSV_ABI KernelUnlink(const char* path) {
»PRINT_NAME();

»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}
"""),
     T(r"""int KYTY_SYSV_ABI KernelUnlink(const char* path) {
»PRINT_NAME();

»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»if (Bc5FsFix(BC5_FS_NAMETOOLONG) && Bc5PathTooLong(path)) { // experiment 0405 (nametoolong)
»»return KERNEL_ERROR_ENAMETOOLONG;
»}
""")),
    ("KernelUnlink: kk04",
     T(r"""»auto* open_file = g_files->GetFile(real_file_name);
»bool  ok        = (open_file != nullptr && open_file->opened && !open_file->directory
»                       ? open_file->f.Unlink()
»                       : Common::File::DeleteFile(real_file_name));

»if (!ok) {
»»return KERNEL_ERROR_EIO;
»}
"""),
     T(r"""»auto* open_file = g_files->GetFile(real_file_name);
»// Experiment 0405 (kk04): on, the host name is unlinked (what SysFileUnlink does on Linux), not the name the open
»// file had when it was opened (a rename may have changed it), and the file's descriptors lose the name (Bc5Forget).
»const bool bc5_kk04 = Bc5FsFix(BC5_FS_KK04);
»bool       ok       = bc5_kk04 ? Common::File::DeleteFile(real_file_name)
»                    : (open_file != nullptr && open_file->opened && !open_file->directory
»                           ? open_file->f.Unlink()
»                           : Common::File::DeleteFile(real_file_name));

»if (!ok) {
»»return KERNEL_ERROR_EIO;
»}
»if (bc5_kk04) {
»»g_files->Bc5Forget(real_file_name);
»}
""")),
    ("KernelRename: the kk04 function before it",
     T(r"""int KYTY_SYSV_ABI KernelRename(const char* from, const char* to) {
"""),
     T(r"""// Experiment 0405 (KYTY_BC5_FS_FIXES kk04): sceKernelRename where today's code EXITs (either path open) or answers
// ENOENT (a directory). A file takes today's steps (its target's parent made, an existing file target replaced), and a
// directory as its target is EISDIR; a directory is renamed by the host's rename(2): onto a missing name or an empty
// directory, ENOTEMPTY onto another, ENOTDIR onto a file, EXDEV across host file systems (FreeBSD's rename(2) errors).
// A rename onto the same file does nothing (today's code deletes the file, then answers EIO). Open descriptors follow
// (FileDescriptors::Bc5Rename). KytyPS5 dfec14a src/kernel/fileSystem.cpp:1398-1430; sharpemu 1811cef
// (KernelFileExtendedExports.cs:330-380 @ 514d766).
static int Bc5RenameFixed(const char* from, const char* to, const std::filesystem::path& real_from,
                          const std::filesystem::path& real_to) {
»if (real_from.empty() || real_to.empty()) {
»»return KERNEL_ERROR_ENOENT;
»}
»const bool from_dir  = Common::File::IsDirectoryExisting(real_from);
»const bool from_file = !from_dir && Common::File::IsFileExisting(real_from);
»if (!from_dir && !from_file) {
»»return KERNEL_ERROR_ENOENT;
»}
»std::error_code same_error;
»if (std::filesystem::equivalent(real_from, real_to, same_error) && !same_error) {
»»LOGF("\tKernelRename: %s -> %s, the same file (experiment 0405)\n", from, to);
»»return OK;
»}
»if (from_dir) {
»»std::error_code error;
»»std::filesystem::rename(real_from, real_to, error);
»»if (error) {
»»»if (error == std::errc::directory_not_empty || error == std::errc::file_exists) {
»»»»return KERNEL_ERROR_ENOTEMPTY;
»»»}
»»»if (error == std::errc::cross_device_link) {
»»»»return KERNEL_ERROR_EXDEV;
»»»}
»»»return KernelErrorFromHost(error);
»»}
»} else {
»»if (Common::File::IsDirectoryExisting(real_to)) {
»»»return KERNEL_ERROR_EISDIR;
»»}
»»Common::File::CreateDirectories(real_to.parent_path());
»»if (Common::File::IsFileExisting(real_to)) {
»»»Common::File::DeleteFile(real_to);
»»}
»»if (!Common::File::MoveFile(real_from, real_to)) {
»»»return KERNEL_ERROR_EIO;
»»}
»}
»g_files->Bc5Rename(real_from, real_to);
»LOGF("\tKernelRename: %s -> %s (experiment 0405)\n", from, to);
»return OK;
}

int KYTY_SYSV_ABI KernelRename(const char* from, const char* to) {
""")),
    ("KernelRename: nametoolong",
     T(r"""»if (from == nullptr || to == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}
"""),
     T(r"""»if (from == nullptr || to == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»if (Bc5FsFix(BC5_FS_NAMETOOLONG) && (Bc5PathTooLong(from) || Bc5PathTooLong(to))) { // experiment 0405 (nametoolong)
»»return KERNEL_ERROR_ENAMETOOLONG;
»}
""")),
    ("KernelRename: kk04",
     T(r"""»EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_from) != nullptr);
»EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_to) != nullptr);
"""),
     T(r"""»if (Bc5FsFix(BC5_FS_KK04)) {
»»return Bc5RenameFixed(from, to, real_from, real_to); // experiment 0405 (kk04)
»}

»EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_from) != nullptr);
»EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_to) != nullptr);
""")),
    ("KernelMkdir: nametoolong",
     T(r"""»if (std::strlen(path) > 255) {
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»LOGF("\t path = %s\n"
»     "\t mode = %04" PRIx16 "\n",
»     path, mode);
"""),
     T(r"""»if (Bc5FsFix(BC5_FS_NAMETOOLONG)) { // experiment 0405 (nametoolong): FreeBSD's limits, not every path over 255
»»if (Bc5PathTooLong(path)) {
»»»return KERNEL_ERROR_ENAMETOOLONG;
»»}
»} else if (std::strlen(path) > 255) {
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»LOGF("\t path = %s\n"
»     "\t mode = %04" PRIx16 "\n",
»     path, mode);
""")),
    ("KernelRmdir: nametoolong",
     T(r"""int KYTY_SYSV_ABI KernelRmdir(const char* path) {
»PRINT_NAME();

»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}
"""),
     T(r"""int KYTY_SYSV_ABI KernelRmdir(const char* path) {
»PRINT_NAME();

»if (path == nullptr) {
»»return KERNEL_ERROR_EINVAL;
»}

»if (Bc5FsFix(BC5_FS_NAMETOOLONG) && Bc5PathTooLong(path)) { // experiment 0405 (nametoolong)
»»return KERNEL_ERROR_ENAMETOOLONG;
»}
""")),
    ("KernelCheckReachability: nametoolong",
     T(r"""»if (std::strlen(path) > 255) {
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»LOGF("\t KernelCheckReachability: %s\n", path);
"""),
     T(r"""»if (Bc5FsFix(BC5_FS_NAMETOOLONG)) { // experiment 0405 (nametoolong): FreeBSD's limits, not every path over 255
»»if (Bc5PathTooLong(path)) {
»»»return KERNEL_ERROR_ENAMETOOLONG;
»»}
»} else if (std::strlen(path) > 255) {
»»return KERNEL_ERROR_ENAMETOOLONG;
»}

»LOGF("\t KernelCheckReachability: %s\n", path);
""")),
)


def edit_fs(s):
    assert MARK not in s and b"Bc5FsFix" not in s and b"KYTY_BC5_FS_FIXES" not in s, f"{FS} has the edit already"
    assert b"\r\n" not in s, f"{FS}: CRLF line endings; this script expects the base tree's LF copy"
    s = once(s, FS_BLOCK_ANCHOR, FS_BLOCK_ANCHOR + FS_BLOCK, "the helper block after PosixToKernel")
    for what, old, new in FS_EDITS:
        s = once(s, old, new, what)
    # the helpers come before their first use; each item's switch is used where it should be
    first_use = s.index(b"Bc5FsFix(BC5_FS_")
    assert s.index(b"static bool Bc5FsFix(uint32_t item)") < first_use
    assert s.index(b"class MountPoints {") < s.index(b"static std::vector<MountPoints::MountPair>::iterator Bc5LongestMount")
    assert s.index(b"Bc5LongestMount(std::vector") < s.index(b"std::filesystem::path MountPoints::GetRealFilename(")
    assert s.index(b"int KernelErrorFromHost(") < s.index(b"static int Bc5RenameFixed(")
    counts = {b"BC5_FS_KK04)": 2, b"BC5_FS_SK04)": 4, b"BC5_FS_BLKSIZE)": 2, b"BC5_FS_NAMETOOLONG)": 7,
              b"BC5_FS_KK10)": 2, b"BC5_FS_SK05)": 2}
    for k, n in counts.items():
        got = s.count(b"Bc5FsFix(" + k)
        assert got == n, ("uses of", k, got, n)
    assert s.count(b"g_files->Bc5Rename(") == 1 and s.count(b"g_files->Bc5Forget(") == 1
    return s


# ======================================================================================================================
# src/libs/libKernel.cpp
# ======================================================================================================================

LK_BLOCK_ANCHOR = T(r"""LIB_DEFINE(InitLibKernel_1_Posix) {
""")

LK_BLOCK = T(r"""// ---- experiment 0405 (BC5 exp 0401 series e5), KYTY_BC5_POSIX_RET_FIXES: return conventions of seven NIDs ----------
// Read once, when libkernel's tables are built (Libs::InitLibKernel_1: its Pthread table, then this Posix table): one
// stderr line, "[bc5] exp 0405: posix return fixes on (items: ...)" or "... off". The registrations change only then:
// a later change of the variable has no effect until the next start. Unset, empty or "0" is off: today's
// registrations. Any other value turns every item on, unless it names items (comma-separated): then only those.
//   unlink      VAzswvTOCzI (unlink) answered SCE codes (FileSystem::KernelUnlink): -1 and errno. AnyPS5 4f41f4c37
//               core/libs/prx/libkernel/File/src/Stdio.cpp:1227 (GPL-2.0-only), exp 0405 R1 #9 / R2 SK06.
//   munmap      UqDGjXA5yUM (munmap), and
//   mprotect    YQOfxL4QfeU (mprotect) answered SCE codes (Memory::KernelMunmap, KernelMprotect): -1 and errno.
//               shadPS4 60c42b9 src/core/libraries/kernel/memory.cpp:421-428, 851-859 (GPL-2.0-or-later), exp 0405
//               R3 M15.
//   trywrlock   XhWHn6P5R7U (pthread_rwlock_trywrlock) answered SCE codes (LibKernel::PthreadRwlockTrywrlock, EBUSY
//               0x80020010): the errno number, as this file's other posix pthread entry points (exp 0336's tryrdlock).
//               sharpemu 0c467e8 (KernelPthreadCompatExports.cs @ 514d766, GPL-2.0-or-later), exp 0405 R2 SK06.
//   schedparam  P41kTWUS3EI (scePthreadGetschedparam) and oIRFTjoILbg (scePthreadSetschedparam) answered errno numbers
//               (Posix::pthread_get/setschedparam): SCE codes (0x80020000 + the errno number, KernelToPosix's inverse
//               on its range; a NULL argument is 0x80020016). Exp 0405 R2 SK06.
//   once        14bOACANTBo (scePthreadOnce) answered errno numbers (Posix::pthread_once, 22): SCE codes, as above.
// The wrappers call today's functions and only translate the result (POSIX_CALL / POSIX_PTHREAD_CALL, libs/errno.h).
// The upstream projects' copyrights remain with their authors; GPL-2.0, as the rest of this file.
static constexpr uint32_t BC5_POSIX_UNLINK     = 1u << 0u;
static constexpr uint32_t BC5_POSIX_MUNMAP     = 1u << 1u;
static constexpr uint32_t BC5_POSIX_MPROTECT   = 1u << 2u;
static constexpr uint32_t BC5_POSIX_TRYWRLOCK  = 1u << 3u;
static constexpr uint32_t BC5_POSIX_SCHEDPARAM = 1u << 4u;
static constexpr uint32_t BC5_POSIX_ONCE       = 1u << 5u;

struct Bc5PosixItem {
»const char* name;
»uint32_t    bit;
};

static constexpr Bc5PosixItem BC5_POSIX_ITEMS[] = {
    {"unlink", BC5_POSIX_UNLINK},       {"munmap", BC5_POSIX_MUNMAP}, {"mprotect", BC5_POSIX_MPROTECT},
    {"trywrlock", BC5_POSIX_TRYWRLOCK}, {"schedparam", BC5_POSIX_SCHEDPARAM}, {"once", BC5_POSIX_ONCE},
};

static uint32_t Bc5PosixRetFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (const auto& item: BC5_POSIX_ITEMS) {
»»»if (std::strlen(item.name) == n && std::strncmp(p, item.name, n) == 0) {
»»»»items |= item.bit;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»if (items == 0) {
»»for (const auto& item: BC5_POSIX_ITEMS) {
»»»items |= item.bit;
»»}
»}
»return items;
}

// The items of KYTY_BC5_POSIX_RET_FIXES that are on (0: off), read once.
static uint32_t Bc5PosixRetFixes() {
»static const uint32_t items = [] {
»»const uint32_t v = Bc5PosixRetFixesParse(std::getenv("KYTY_BC5_POSIX_RET_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: posix return fixes off\n");
»»} else {
»»»std::string names;
»»»for (const auto& item: BC5_POSIX_ITEMS) {
»»»»if ((v & item.bit) != 0) {
»»»»»names += names.empty() ? "" : " ";
»»»»»names += item.name;
»»»»}
»»»}
»»»std::fprintf(stderr, "[bc5] exp 0405: posix return fixes on (items: %s)\n", names.c_str());
»»}
»»std::fflush(stderr);
»»return v;
»}();
»return items;
}

static bool Bc5PosixRetFix(uint32_t item) {
»return (Bc5PosixRetFixes() & item) != 0;
}

static int KYTY_SYSV_ABI Bc5PosixUnlink(const char* path) {
»PRINT_NAME();

»return POSIX_CALL(LibKernel::FileSystem::KernelUnlink(path));
}

static int KYTY_SYSV_ABI Bc5PosixMunmap(void* addr, size_t len) {
»PRINT_NAME();

»return POSIX_CALL(LibKernel::Memory::KernelMunmap(reinterpret_cast<uint64_t>(addr), len));
}

static int KYTY_SYSV_ABI Bc5PosixMprotect(const void* addr, size_t len, int prot) {
»PRINT_NAME();

»return POSIX_CALL(LibKernel::Memory::KernelMprotect(addr, len, prot));
}

static int KYTY_SYSV_ABI Bc5PosixRwlockTrywrlock(LibKernel::PthreadRwlock* rwlock) {
»PRINT_NAME();

»return POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockTrywrlock(rwlock));
}

// An errno number of the posix functions as an SCE code (0 stays OK).
static int Bc5PosixToKernel(int posix_result) {
»return posix_result == 0 ? OK : LibKernel::KERNEL_ERROR_UNKNOWN + posix_result;
}

static int KYTY_SYSV_ABI Bc5ScePthreadGetschedparam(LibKernel::Pthread thread, int* policy,
                                                    LibKernel::KernelSchedParam* param) {
»PRINT_NAME();

»return Bc5PosixToKernel(Posix::pthread_getschedparam(thread, policy, param));
}

static int KYTY_SYSV_ABI Bc5ScePthreadSetschedparam(LibKernel::Pthread thread, int policy,
                                                    const LibKernel::KernelSchedParam* param) {
»PRINT_NAME();

»return Bc5PosixToKernel(Posix::pthread_setschedparam(thread, policy, param));
}

static int KYTY_SYSV_ABI Bc5ScePthreadOnce(void* once_control, void(KYTY_SYSV_ABI* init_routine)()) {
»PRINT_NAME();

»return Bc5PosixToKernel(Posix::pthread_once(once_control, init_routine));
}
// ---- end of experiment 0405's block ---------------------------------------------------------------------------------

""")

LK_EDITS = (
    ("Posix table: schedparam",
     T(r"""»LIB_FUNC("FIs3-UQT9sg", Posix::pthread_getschedparam);
»LIB_FUNC("P41kTWUS3EI", Posix::pthread_getschedparam);
»LIB_FUNC("Xs9hdiD7sAA", Posix::pthread_setschedparam);
»LIB_FUNC("oIRFTjoILbg", Posix::pthread_setschedparam);
"""),
     T(r"""»LIB_FUNC("FIs3-UQT9sg", Posix::pthread_getschedparam);
»if (Bc5PosixRetFix(BC5_POSIX_SCHEDPARAM)) { // experiment 0405 (schedparam): scePthreadGetschedparam, SCE codes
»»LIB_FUNC("P41kTWUS3EI", Bc5ScePthreadGetschedparam);
»} else {
»»LIB_FUNC("P41kTWUS3EI", Posix::pthread_getschedparam);
»}
»LIB_FUNC("Xs9hdiD7sAA", Posix::pthread_setschedparam);
»if (Bc5PosixRetFix(BC5_POSIX_SCHEDPARAM)) { // experiment 0405 (schedparam): scePthreadSetschedparam, SCE codes
»»LIB_FUNC("oIRFTjoILbg", Bc5ScePthreadSetschedparam);
»} else {
»»LIB_FUNC("oIRFTjoILbg", Posix::pthread_setschedparam);
»}
""")),
    ("Posix table: trywrlock",
     T(r"""»LIB_FUNC("XhWHn6P5R7U", LibKernel::PthreadRwlockTrywrlock);
"""),
     T(r"""»if (Bc5PosixRetFix(BC5_POSIX_TRYWRLOCK)) { // experiment 0405 (trywrlock): pthread_rwlock_trywrlock, errno numbers
»»LIB_FUNC("XhWHn6P5R7U", Bc5PosixRwlockTrywrlock);
»} else {
»»LIB_FUNC("XhWHn6P5R7U", LibKernel::PthreadRwlockTrywrlock);
»}
""")),
    ("Posix table: mprotect, munmap",
     T(r"""»LIB_FUNC("YQOfxL4QfeU", LibKernel::Memory::KernelMprotect);
»LIB_FUNC("UqDGjXA5yUM", LibKernel::Memory::KernelMunmap);
"""),
     T(r"""»if (Bc5PosixRetFix(BC5_POSIX_MPROTECT)) { // experiment 0405 (mprotect): -1 and errno
»»LIB_FUNC("YQOfxL4QfeU", Bc5PosixMprotect);
»} else {
»»LIB_FUNC("YQOfxL4QfeU", LibKernel::Memory::KernelMprotect);
»}
»if (Bc5PosixRetFix(BC5_POSIX_MUNMAP)) { // experiment 0405 (munmap): -1 and errno
»»LIB_FUNC("UqDGjXA5yUM", Bc5PosixMunmap);
»} else {
»»LIB_FUNC("UqDGjXA5yUM", LibKernel::Memory::KernelMunmap);
»}
""")),
    ("libkernel Pthread table: once",
     T(r"""»LIB_FUNC("14bOACANTBo", Posix::pthread_once);
"""),
     T(r"""»if (Posix::Bc5PosixRetFix(Posix::BC5_POSIX_ONCE)) { // experiment 0405 (once): scePthreadOnce, SCE codes
»»LIB_FUNC("14bOACANTBo", Posix::Bc5ScePthreadOnce);
»} else {
»»LIB_FUNC("14bOACANTBo", Posix::pthread_once);
»}
""")),
    ("libkernel Pthread table: unlink",
     T(r"""»LIB_FUNC("VAzswvTOCzI", FileSystem::KernelUnlink);
"""),
     T(r"""»if (Posix::Bc5PosixRetFix(Posix::BC5_POSIX_UNLINK)) { // experiment 0405 (unlink): -1 and errno
»»LIB_FUNC("VAzswvTOCzI", Posix::Bc5PosixUnlink);
»} else {
»»LIB_FUNC("VAzswvTOCzI", FileSystem::KernelUnlink);
»}
""")),
)

# The NIDs this script registers, with the names they hash from (lesson R32; the names as shadPS4 60c42b9's
# src/core/aerolib/aerolib.inl has them).
NIDS = (
    ("VAzswvTOCzI", "unlink"),
    ("UqDGjXA5yUM", "munmap"),
    ("YQOfxL4QfeU", "mprotect"),
    ("XhWHn6P5R7U", "pthread_rwlock_trywrlock"),
    ("P41kTWUS3EI", "scePthreadGetschedparam"),
    ("oIRFTjoILbg", "scePthreadSetschedparam"),
    ("14bOACANTBo", "scePthreadOnce"),
)
NID_SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
NID_CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"


def nid(name):
    """exp 0327's calculator (nid0401.py): SHA-1 of the name and the public salt, 8 bytes little-endian, 64 symbols."""
    digest = int.from_bytes(hashlib.sha1(name.encode() + NID_SALT).digest()[:8], "little")
    return "".join(NID_CODES[(digest >> (58 - i * 6)) & 63] for i in range(10)) + NID_CODES[(digest & 15) * 4]


def check_nids():
    for name, want in (("strcmp", "Ovb2dSJOAuE"), ("strncmp", "aesyjrHVWy4"), ("strcpy_s", "5Xa2ACNECdo")):
        assert nid(name) == want, ("the NID calculator", name, nid(name), want)
    for want, name in NIDS:
        assert nid(name) == want, ("NID and name differ", want, name, nid(name))


def edit_lk(s):
    assert MARK not in s and b"Bc5PosixRetFix" not in s and b"KYTY_BC5_POSIX_RET_FIXES" not in s, \
        f"{LK} has the edit already"
    assert b"\r\n" not in s, f"{LK}: CRLF line endings; this script expects the base tree's LF copy"
    for name in (b"Bc5PosixUnlink", b"Bc5PosixMunmap", b"Bc5PosixMprotect", b"Bc5PosixRwlockTrywrlock",
                 b"Bc5ScePthreadGetschedparam", b"Bc5ScePthreadSetschedparam", b"Bc5ScePthreadOnce"):
        assert name not in s, name
    s = once(s, LK_BLOCK_ANCHOR, LK_BLOCK + LK_BLOCK_ANCHOR, "the block before InitLibKernel_1_Posix")
    for what, old, new in LK_EDITS:
        s = once(s, old, new, what)
    # the block is in namespace Posix, before both tables; each NID is registered once on each branch
    posix_ns = s.index(b"namespace Posix {\n\nLIB_VERSION(\"Posix\", 1, \"libkernel\", 1, 1);")
    block = s.index(b"static uint32_t Bc5PosixRetFixes()")
    assert posix_ns < block < s.index(b"LIB_DEFINE(InitLibKernel_1_Posix) {") < s.index(b"} // namespace Posix\n\nnamespace Coredump")
    assert block < s.index(b"LIB_DEFINE(InitLibKernel_1_Pthread) {")
    for want, _ in NIDS:
        n = s.count(b'LIB_FUNC("' + want.encode() + b'"')
        assert n == 2, ("registrations of", want, n)
    assert s.count(b"Bc5PosixRetFix(") == 7 + 1, s.count(b"Bc5PosixRetFix(")  # 7 uses + the definition
    return s


FILES = ((FS, edit_fs), (LK, edit_lk))


def main():
    assert len(sys.argv) == 3, __doc__
    root, out = sys.argv[1], sys.argv[2]
    check_nids()
    for rel, fn in FILES:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        got = hashlib.md5(s).hexdigest()
        assert got == IN_MD5[rel], (f"{rel}: md5 {got}, not the e5 input's {IN_MD5[rel]}", )
        o = fn(s)
        assert balance(o) == balance(s), (rel, "brace/parenthesis balance changed", balance(s), balance(o))
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(o)
        print(f"{rel} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "jit": exp 0405's R3 M31 (the JIT shared-memory calls, the
maintainer's decision 3 of 2026-11-04) and the one excluded-provenance libkernel row whose function lives in these units
(R1 520a8249a, decision 1), in two units of the e6 input tree (e5's sources), each behind a switch that is off by default
and read once (off is today's path exactly):
  src/kernel/memory.cpp     the JIT areas: Bc5JitAreaCreate, Bc5JitAreaAlias, Bc5JitAreaMap, Bc5JitHandleClose
                            (behaviour after AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Jit.cpp:197-237)
  src/libs/libKernel.cpp    KYTY_BC5_JIT_SHM    registers the three under their NIDs, close wrappers for JIT handles
                            KYTY_BC5_FW_KERNEL  notify: sceKernelSendNotificationRequest (BunnyFl's fw 13.42 run)
Each unit's input md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur exactly
once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are
(both units are LF). After editing, the script undoes its own edits on the output and asserts that this gives the input
back byte for byte. The NIDs used are checked first with exp 0327's calculator (nid0401.py's copy), itself checked on
three known pairs. Only the two units are written. Prints "<relpath> <md5>" per written file.
Notes: jit0405-notes.md; CPU test: jit0405.cpp.
usage: mkjit0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"KYTY_BC5_JIT_SHM", b"KYTY_BC5_FW_KERNEL", b"Bc5Jit", b"Bc5Fw", b"series e6 of experiment 0401",
         b"Bc5KernelSendNotificationRequest")


def T(text, crlf=False):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    if crlf:
        assert b"\r" not in out
        out = out.replace(b"\n", b"\r\n")
    return out


# =====================================================================================================================
# NIDs: exp 0327's calculator (the public host algorithm: SHA-1 of the name and the salt, the first 8 bytes little-endian
# in a 64-character alphabet), as nid0401.py has it, self-checked on known pairs first.
# =====================================================================================================================
SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"


def nid(name):
    digest = int.from_bytes(hashlib.sha1(name.encode() + SALT).digest()[:8], "little")
    return "".join(CODES[(digest >> (58 - i * 6)) & 63] for i in range(10)) + CODES[(digest & 15) * 4]


NIDS = (
    ("avvJ3J0H0EY", "sceKernelJitCreateSharedMemory"),
    ("MR221Mwo0Pc", "sceKernelJitCreateAliasOfSharedMemory"),
    ("YKT49TOLQWs", "sceKernelJitMapSharedMemory"),
    ("zl7hupSO0C0", "sceKernelSendNotificationRequest"),
    ("UK2Tl2DWUns", "sceKernelClose"),
    ("bY-PO6JhzhQ", "close"),
    ("NNtFaKJbPt0", "_close"),
)


def check_nids():
    for name, want in (("strcmp", "Ovb2dSJOAuE"), ("strncmp", "aesyjrHVWy4"), ("strcpy_s", "5Xa2ACNECdo")):
        assert nid(name) == want, ("the NID calculator fails its self-check", name, nid(name), want)
    for want, name in NIDS:
        assert nid(name) == want, ("NID", name, nid(name), want)


# =====================================================================================================================
# src/kernel/memory.cpp: the JIT areas
# =====================================================================================================================
MEM_BLOCK_ANCHOR = "// Experiment 0405 series e5, BC5_R3_MPROTECT_GAPS (M1): protection over gaps, as a PS5 does. AnyPS5 measured on\n"
MEM_BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401), KYTY_BC5_JIT_SHM: JIT shared memory (exp 0405 R3 M31) ----
// What a JIT engine (an emulator, a script runtime) asks for to write code through one view and run it through another.
// libKernel.cpp registers the three calls under the NIDs of their public names only when KYTY_BC5_JIT_SHM is on; with it
// off nothing here is reachable and today's path is unchanged. Behaviour of AnyPS5 4f41f4c375f5 (GPL-2.0-only):
// core/libs/prx/libkernel/DirectMemory/Jit.cpp:197-237, its note docs/dev/debt/libkernel.md:175 and the close path
// core/libs/prx/libkernel/File/src/Open.cpp:312-320. Adapted, no code copied; the names and the structure are ours.
//   create (label, bytes, ceiling, handle out): a new area of `bytes` whose views never get more than `ceiling` (CPU
//       read 1, write 2, execute 4). The label is not used. No handle out, `bytes` 0 or not a multiple of the 16 KiB
//       guest page, or other bits in `ceiling`: EINVAL. The host out of descriptors or memory: EMFILE, ENFILE or ENOMEM.
//   alias (handle, ceiling, handle out): one more handle on the same area, with a ceiling no wider than the handle's.
//       No handle out or other bits: EINVAL; not an area's handle: EBADF; a wider ceiling: EACCES.
//   map (handle, prot, address in/out): the whole area at a free guest address; the address passed in is a hint only,
//       and the address chosen is written back. No address or other bits: EINVAL; not an area's handle: EBADF; prot
//       above the handle's ceiling: EACCES.
//   Write and execute count as read when two protections are compared. A closed handle is gone (libKernel.cpp's close
//   wrappers call Bc5JitHandleClose); views stay mapped until munmap, and an area lives as long as one of its views.
// Host side, Linux: an area is a memfd of `bytes`. A view is a guest runtime range made by AllocateGuestRuntimeMemory (the
// range table and the guest address space, so VirtualQuery, QueryMemoryProtection, mprotect and munmap treat it as any
// other committed range), whose host pages are then replaced by a MAP_SHARED mapping of the memfd: every view of an area
// shows the same bytes. munmap puts the placeholder back over it. As everywhere in this file the host view is read-write,
// plus execute when prot has it; the range table keeps the guest's prot. Areas count against no memory budget. Other
// hosts: create answers ENOMEM. Handles are our own numbers, 0x40000 up and never reused, clear of the file system's
// descriptors (3 up), the sockets (128-1023) and the epoll ids (1024 up).
// TODO(verify): the error answers and the budget are not measured on a console (AnyPS5's note says the same).
static constexpr int      BC5_JIT_CPU_BITS     = PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC;
static constexpr uint64_t BC5_JIT_PAGE         = 0x4000; // the guest page, as GuestPageSize in this file
static constexpr int      BC5_JIT_FIRST_HANDLE = 0x40000;
static constexpr int      BC5_JIT_LAST_HANDLE  = 0x7fffffff;
static constexpr char     BC5_JIT_VIEW_NAME[]  = "bc5-jit";

// The bits a protection grants, write and execute taken to include read.
static int Bc5JitGrants(int prot) {
»return (prot & (PROT_CPU_WRITE | PROT_CPU_EXEC)) != 0 ? (prot | PROT_CPU_READ) : prot;
}

static bool Bc5JitFits(int prot, int ceiling) {
»return (Bc5JitGrants(prot) & ~Bc5JitGrants(ceiling)) == 0;
}

// The host memory of one area. Its descriptor is closed with the area's last handle; mapped views keep their pages.
struct Bc5JitArea {
»int      host_fd = -1;
»uint64_t bytes   = 0;

»Bc5JitArea(int fd, uint64_t size): host_fd(fd), bytes(size) {}
»~Bc5JitArea() {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
»»::close(host_fd);
#endif
»}
»KYTY_CLASS_NO_COPY(Bc5JitArea);
};

struct Bc5JitHandle {
»std::shared_ptr<Bc5JitArea> area;
»int                         ceiling = 0;
};

static std::mutex                  g_bc5_jit_mutex;
static std::map<int, Bc5JitHandle> g_bc5_jit_handles;
static int                         g_bc5_jit_next_handle = BC5_JIT_FIRST_HANDLE;

// A host errno as the guest's answer.
static int Bc5JitHostAnswer(int error) {
»switch (error) {
»»case EMFILE: return KERNEL_ERROR_EMFILE;
»»case ENFILE: return KERNEL_ERROR_ENFILE;
»»default: return KERNEL_ERROR_ENOMEM;
»}
}

static std::shared_ptr<Bc5JitArea> Bc5JitNewArea(uint64_t bytes, int* error) {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
»if (bytes > static_cast<uint64_t>(INT64_MAX)) {
»»*error = ENOMEM;
»»return nullptr;
»}
»// 0x0001 is MFD_CLOEXEC (Linux include/uapi/linux/memfd.h); this file calls memfd_create through syscall, as here.
»const int fd = static_cast<int>(syscall(SYS_memfd_create, "bc5-jit", 0x0001u));
»if (fd < 0) {
»»*error = errno;
»»return nullptr;
»}
»if (ftruncate(fd, static_cast<off_t>(bytes)) != 0) {
»»*error = errno;
»»::close(fd);
»»return nullptr;
»}
»return std::make_shared<Bc5JitArea>(fd, bytes);
#else
»(void)bytes;
»*error = ENOMEM;
»return nullptr;
#endif
}

// Puts a shared view of the area over the host pages of the committed guest range at vaddr, area.bytes long.
static bool Bc5JitShowArea(const Bc5JitArea& area, uint64_t vaddr, int prot) {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
»const int host_prot = PROT_READ | PROT_WRITE | ((prot & PROT_CPU_EXEC) != 0 ? PROT_EXEC : 0);
»void*     view =
»    mmap(reinterpret_cast<void*>(vaddr), area.bytes, host_prot, MAP_SHARED | MAP_FIXED, area.host_fd, 0);
»return view != MAP_FAILED && reinterpret_cast<uint64_t>(view) == vaddr;
#else
»(void)area;
»(void)vaddr;
»(void)prot;
»return false;
#endif
}

static int Bc5JitAddHandle(std::shared_ptr<Bc5JitArea> area, int ceiling, int* handle_out) {
»std::lock_guard<std::mutex> lock(g_bc5_jit_mutex);
»if (g_bc5_jit_next_handle == BC5_JIT_LAST_HANDLE) {
»»return KERNEL_ERROR_EMFILE;
»}
»const int handle            = g_bc5_jit_next_handle++;
»g_bc5_jit_handles[handle]   = Bc5JitHandle {std::move(area), ceiling};
»*handle_out                 = handle;
»return OK;
}

// The area behind a handle, if the handle is one and `prot` fits under its ceiling; else the answer.
static int Bc5JitLookUp(int handle, int prot, std::shared_ptr<Bc5JitArea>* area) {
»std::lock_guard<std::mutex> lock(g_bc5_jit_mutex);
»const auto                  it = g_bc5_jit_handles.find(handle);
»if (it == g_bc5_jit_handles.end()) {
»»return KERNEL_ERROR_EBADF;
»}
»if (!Bc5JitFits(prot, it->second.ceiling)) {
»»return KERNEL_ERROR_EACCES;
»}
»*area = it->second.area;
»return OK;
}

int KYTY_SYSV_ABI Bc5JitAreaCreate(const char* label, size_t bytes, int ceiling, int* handle_out) {
»PRINT_NAME();

»(void)label;
»if (handle_out == nullptr || bytes == 0 || (bytes & (BC5_JIT_PAGE - 1u)) != 0 || (ceiling & ~BC5_JIT_CPU_BITS) != 0) {
»»return KERNEL_ERROR_EINVAL;
»}
»int  error = 0;
»auto area  = Bc5JitNewArea(bytes, &error);
»if (area == nullptr) {
»»LOGF("\t jit area of 0x%016" PRIx64 " bytes: the host refused it (errno %d)\n", static_cast<uint64_t>(bytes), error);
»»return Bc5JitHostAnswer(error);
»}
»const int result = Bc5JitAddHandle(std::move(area), ceiling, handle_out);
»LOGF("\t jit area: 0x%016" PRIx64 " bytes, ceiling 0x%x, handle %d\n", static_cast<uint64_t>(bytes), ceiling,
»     result == OK ? *handle_out : -1);
»return result;
}

int KYTY_SYSV_ABI Bc5JitAreaAlias(int handle, int ceiling, int* handle_out) {
»PRINT_NAME();

»if (handle_out == nullptr || (ceiling & ~BC5_JIT_CPU_BITS) != 0) {
»»return KERNEL_ERROR_EINVAL;
»}
»std::shared_ptr<Bc5JitArea> area;
»if (const int result = Bc5JitLookUp(handle, ceiling, &area); result != OK) {
»»return result;
»}
»const int result = Bc5JitAddHandle(std::move(area), ceiling, handle_out);
»LOGF("\t jit alias of handle %d: ceiling 0x%x, handle %d\n", handle, ceiling, result == OK ? *handle_out : -1);
»return result;
}

int KYTY_SYSV_ABI Bc5JitAreaMap(int handle, int prot, void** where) {
»PRINT_NAME();

»if (where == nullptr || (prot & ~BC5_JIT_CPU_BITS) != 0) {
»»return KERNEL_ERROR_EINVAL;
»}
»std::shared_ptr<Bc5JitArea> area;
»if (const int result = Bc5JitLookUp(handle, prot, &area); result != OK) {
»»return result;
»}

»std::lock_guard<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex);

»const auto mode  = static_cast<VirtualMemory::Mode>(prot);
»const auto hint  = reinterpret_cast<uint64_t>(*where) & ~(BC5_JIT_PAGE - 1u);
»uint64_t   vaddr = 0;
»if (hint != 0) {
»»vaddr = AllocateGuestRuntimeMemory(hint, area->bytes, mode, BC5_JIT_VIEW_NAME, VirtualRangeType::Runtime, false);
»}
»if (vaddr == 0) {
»»vaddr = AllocateGuestRuntimeMemory(0, area->bytes, mode, BC5_JIT_VIEW_NAME, VirtualRangeType::Runtime, false);
»}
»if (vaddr == 0) {
»»return KERNEL_ERROR_ENOMEM;
»}
»if (!Bc5JitShowArea(*area, vaddr, prot)) {
»»UnmapGpuRange(vaddr, area->bytes);
»»EXIT_IF(!FreeGuestMemoryOwner(vaddr, area->bytes));
»»return KERNEL_ERROR_ENOMEM;
»}
»*where = reinterpret_cast<void*>(vaddr);
»LOGF("\t jit view of handle %d: 0x%016" PRIx64 "..0x%016" PRIx64 ", prot 0x%x\n", handle, vaddr, vaddr + area->bytes,
»     prot);
»return OK;
}

// Lets a JIT handle go; false when `handle` is not one (the caller then does today's close).
bool Bc5JitHandleClose(int handle) {
»if (handle < BC5_JIT_FIRST_HANDLE) {
»»return false;
»}
»std::shared_ptr<Bc5JitArea> last; // destroyed after the lock is released
»std::lock_guard<std::mutex>  lock(g_bc5_jit_mutex);
»const auto                   it = g_bc5_jit_handles.find(handle);
»if (it == g_bc5_jit_handles.end()) {
»»return false;
»}
»last = std::move(it->second.area);
»g_bc5_jit_handles.erase(it);
»LOGF("\t jit handle %d closed\n", handle);
»return true;
}
// ---- end of BC5 experiment 0405 series e6, KYTY_BC5_JIT_SHM ----------------------------------------------------------

"""
MEM_EDITS = ()
MEM_BEFORE = ("static uint64_t AllocateGuestRuntimeMemory(uint64_t search_addr, uint64_t size,\n",
              "static bool FreeGuestMemoryOwner(uint64_t vaddr, uint64_t size) {\n",
              "static void UnmapGpuRange(uint64_t vaddr, uint64_t size) {\n",
              "static std::recursive_mutex g_memory_operation_mutex;\n",
              "constexpr int PROT_CPU_WRITE = 0x02;\n")
MEM_AFTER = ("int KYTY_SYSV_ABI KernelMprotect(const void* addr, size_t len, int prot) {\n",)
MEM_USES = (("Bc5JitGrants(", 3), ("Bc5JitFits(", 2), ("Bc5JitNewArea(", 2), ("Bc5JitShowArea(", 2),
            ("Bc5JitAddHandle(", 3), ("Bc5JitLookUp(", 3), ("Bc5JitHostAnswer(", 2), ("g_bc5_jit_mutex", 4),
            ("int KYTY_SYSV_ABI Bc5JitAreaCreate(", 1), ("int KYTY_SYSV_ABI Bc5JitAreaAlias(", 1),
            ("int KYTY_SYSV_ABI Bc5JitAreaMap(", 1), ("bool Bc5JitHandleClose(int handle)", 1))

# =====================================================================================================================
# src/libs/libKernel.cpp: the switches, the close wrappers, the notification request, the registrations
# =====================================================================================================================
LK_BLOCK_ANCHOR = "} // namespace LibKernel\n\nnamespace LibKernelWriteThrottling {\n"
LK_BLOCK = r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_JIT_SHM and KYTY_BC5_FW_KERNEL ----------------------
// KYTY_BC5_JIT_SHM (exp 0405 R3 M31; the maintainer's decision 3 of 2026-11-04): registers the three JIT shared-memory
// calls (kernel/memory.cpp, Bc5JitArea*; behaviour after AnyPS5 4f41f4c375f5 core/libs/prx/libkernel/DirectMemory/
// Jit.cpp:197-237, GPL-2.0-only) under the NIDs of their public names, and puts a wrapper in front of today's close
// entry points so that closing a JIT handle lets it go (AnyPS5 core/libs/prx/libkernel/File/src/Open.cpp:312-320); any
// other descriptor goes on to today's function. Off: nothing is registered and close is today's.
// KYTY_BC5_FW_KERNEL (exp 0405 R1 row 520a8249a; decision 1, a firmware run): item "notify", see below.
// Each is read once, at registration, and its first use prints one stderr line: "[bc5] exp 0405: jit shm on (items:
// create,alias,map,close)" or "[bc5] exp 0405: jit shm off"; "[bc5] exp 0405: fw kernel on (items: notify)" or
// "[bc5] exp 0405: fw kernel off". A switch is on when set, non-empty and not "0"; KYTY_BC5_FW_KERNEL may name its items
// in a comma list, and any other value turns all of them on.
namespace Memory { // defined in kernel/memory.cpp (declared here: no header change)
int KYTY_SYSV_ABI Bc5JitAreaCreate(const char* label, size_t bytes, int ceiling, int* handle_out);
int KYTY_SYSV_ABI Bc5JitAreaAlias(int handle, int ceiling, int* handle_out);
int KYTY_SYSV_ABI Bc5JitAreaMap(int handle, int prot, void** where);
bool              Bc5JitHandleClose(int handle);
} // namespace Memory

static bool Bc5JitEnvOn(const char* value) {
»return value != nullptr && value[0] != '\0' && std::strcmp(value, "0") != 0;
}

static bool Bc5JitShmOn() {
»static const bool on = [] {
»»const bool v = Bc5JitEnvOn(std::getenv("KYTY_BC5_JIT_SHM"));
»»std::fprintf(stderr, "%s",
»»             v ? "[bc5] exp 0405: jit shm on (items: create,alias,map,close)\n" : "[bc5] exp 0405: jit shm off\n");
»»return v;
»}();
»return on;
}

// sceKernelClose: a JIT handle is let go here; any other descriptor goes to today's function.
static int KYTY_SYSV_ABI Bc5JitSceClose(int d) {
»if (Memory::Bc5JitHandleClose(d)) {
»»return OK;
»}
»return FileSystem::KernelClose(d);
}

// close and _close (the errno convention): the same, with today's LibKernel::close behind it.
static int KYTY_SYSV_ABI Bc5JitPosixClose(int d) {
»if (Memory::Bc5JitHandleClose(d)) {
»»return 0;
»}
»return LibKernel::close(d);
}

static constexpr uint32_t BC5_FW_NOTIFY = 1u << 0u;
static constexpr uint32_t BC5_FW_ALL    = BC5_FW_NOTIFY;

// The items of KYTY_BC5_FW_KERNEL that are on (0: off), read once.
static uint32_t Bc5FwKernelItems() {
»static const uint32_t items = [] {
»»const char* e = std::getenv("KYTY_BC5_FW_KERNEL");
»»uint32_t    v = 0;
»»if (Bc5JitEnvOn(e)) {
»»»const std::string list = std::string(",") + e + ",";
»»»if (list.find(",notify,") != std::string::npos) {
»»»»v |= BC5_FW_NOTIFY;
»»»}
»»»if (v == 0) {
»»»»v = BC5_FW_ALL;
»»»}
»»}
»»std::fprintf(stderr, "%s",
»»             v != 0 ? "[bc5] exp 0405: fw kernel on (items: notify)\n" : "[bc5] exp 0405: fw kernel off\n");
»»return v;
»}();
»return items;
}

static bool Bc5FwKernelOn(uint32_t item) {
»return (Bc5FwKernelItems() & item) != 0;
}

// KYTY_BC5_FW_KERNEL "notify": sceKernelSendNotificationRequest (NID zl7hupSO0C0), not registered today. AnyPS5
// 4f41f4c375f5 docs/dev/debt/libkernel.md and libSceSysUtil.md (commit 520a8249a, GPL-2.0-only) give @BunnyFl's run of
// firmware 13.42 under an emulator (AnyPS5 pull request 9081, comment 6418015178): the library only writes the request
// to a notification descriptor, retrying on EINTR, and returns 0 or 0x80020000 | errno; the request
// sceSysUtilSendSystemNotificationWithText makes is 0xc30 bytes, kind 5 in its first int32 and the text at +0x2d (at
// most 179 characters). There is no notification device here: the request is taken (0) and, for a kind 5 request of
// 0xc30 bytes, its text goes to the log. AnyPS5's own refusals of other kinds, sizes, devices and flags are not the
// firmware's (its note says so) and are not ported. Adapted, no code copied.
// TODO(verify): a NULL request answers EFAULT, as the descriptor write would fault; inferred from the run's
// "0x80020000 | errno", not measured.
static int KYTY_SYSV_ABI Bc5KernelSendNotificationRequest(int sink, const void* block, size_t block_bytes, int options) {
»PRINT_NAME();

»if (block == nullptr) {
»»return KERNEL_ERROR_EFAULT;
»}
»constexpr size_t SYSTEM_TEXT_BYTES = 0xc30;
»constexpr size_t TEXT_AT           = 0x2d;
»constexpr int    SYSTEM_TEXT_KIND  = 5;
»int32_t          kind              = 0;
»if (block_bytes >= sizeof(kind)) {
»»std::memcpy(&kind, block, sizeof(kind));
»}
»const char* text = static_cast<const char*>(block) + TEXT_AT;
»const auto* stop = (kind == SYSTEM_TEXT_KIND && block_bytes == SYSTEM_TEXT_BYTES)
»                       ? static_cast<const char*>(std::memchr(text, 0, block_bytes - TEXT_AT))
»                       : nullptr;
»if (stop != nullptr) {
»»const std::string message(text, stop);
»»LOGF("[bc5] notification (kind 5): %s\n", message.c_str());
»} else {
»»LOGF("[bc5] notification request: sink %d, kind %d, %" PRIu64 " bytes, options 0x%x\n", sink, static_cast<int>(kind),
»»     static_cast<uint64_t>(block_bytes), static_cast<unsigned>(options));
»}
»return OK;
}
// ---- end of BC5 experiment 0405 series e6 -----------------------------------------------------------------------------

"""
LK_EDITS = (
    ("Posix close",
     "»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::close);\n»LIB_FUNC(\"FN4gaPmuFV8\", LibKernel::write);\n»LIB_FUNC(\"Oy6IpwgtYOk\", Posix::lseek);\n",
     "»if (LibKernel::Bc5JitShmOn()) { // BC5 experiment 0405 series e6 (KYTY_BC5_JIT_SHM): close lets a JIT handle go\n"
     "»»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::Bc5JitPosixClose);\n"
     "»} else {\n"
     "»»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::close);\n"
     "»}\n"
     "»LIB_FUNC(\"FN4gaPmuFV8\", LibKernel::write);\n»LIB_FUNC(\"Oy6IpwgtYOk\", Posix::lseek);\n"),
    ("sceKernelClose",
     "»LIB_FUNC(\"UK2Tl2DWUns\", FileSystem::KernelClose);\n",
     "»if (LibKernel::Bc5JitShmOn()) { // BC5 experiment 0405 series e6 (KYTY_BC5_JIT_SHM): close lets a JIT handle go\n"
     "»»LIB_FUNC(\"UK2Tl2DWUns\", LibKernel::Bc5JitSceClose);\n"
     "»} else {\n"
     "»»LIB_FUNC(\"UK2Tl2DWUns\", FileSystem::KernelClose);\n"
     "»}\n"),
    ("libkernel close",
     "»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::close); // experiment 0338: the posix entry point\n",
     "»if (LibKernel::Bc5JitShmOn()) { // BC5 experiment 0405 series e6 (KYTY_BC5_JIT_SHM): close lets a JIT handle go\n"
     "»»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::Bc5JitPosixClose);\n"
     "»} else {\n"
     "»»LIB_FUNC(\"bY-PO6JhzhQ\", LibKernel::close); // experiment 0338: the posix entry point\n"
     "»}\n"),
    ("_close",
     "»LIB_FUNC(\"NNtFaKJbPt0\", LibKernel::close);\n",
     "»if (LibKernel::Bc5JitShmOn()) { // BC5 experiment 0405 series e6 (KYTY_BC5_JIT_SHM): close lets a JIT handle go\n"
     "»»LIB_FUNC(\"NNtFaKJbPt0\", LibKernel::Bc5JitPosixClose);\n"
     "»} else {\n"
     "»»LIB_FUNC(\"NNtFaKJbPt0\", LibKernel::close);\n"
     "»}\n"),
    ("JIT registrations",
     "»LIB_FUNC(\"bvD+95Q6asU\", Memory::KernelMemoryPoolGetBlockStats);\n",
     "»LIB_FUNC(\"bvD+95Q6asU\", Memory::KernelMemoryPoolGetBlockStats);\n"
     "»if (LibKernel::Bc5JitShmOn()) { // BC5 experiment 0405 series e6 (KYTY_BC5_JIT_SHM): exp 0405 R3 M31\n"
     "»»LIB_FUNC(\"avvJ3J0H0EY\", Memory::Bc5JitAreaCreate); // sceKernelJitCreateSharedMemory\n"
     "»»LIB_FUNC(\"MR221Mwo0Pc\", Memory::Bc5JitAreaAlias);  // sceKernelJitCreateAliasOfSharedMemory\n"
     "»»LIB_FUNC(\"YKT49TOLQWs\", Memory::Bc5JitAreaMap);    // sceKernelJitMapSharedMemory\n"
     "»}\n"),
    ("notification registration",
     "»LIB_FUNC(\"NH6xARDOVv8\", Bc5KernelGetOperationMode);\n",
     "»LIB_FUNC(\"NH6xARDOVv8\", Bc5KernelGetOperationMode);\n"
     "»if (LibKernel::Bc5FwKernelOn(LibKernel::BC5_FW_NOTIFY)) { // BC5 experiment 0405 series e6 (KYTY_BC5_FW_KERNEL notify)\n"
     "»»LIB_FUNC(\"zl7hupSO0C0\", LibKernel::Bc5KernelSendNotificationRequest); // sceKernelSendNotificationRequest\n"
     "»}\n"),
)
LK_BEFORE = ("static int KYTY_SYSV_ABI close(int d) {\n",)
LK_AFTER = ("LIB_DEFINE(InitLibKernel_1_Posix) {\n", "LIB_DEFINE(InitLibKernel_1_FS) {\n", "LIB_DEFINE(InitLibKernel_1_Mem) {\n",
            "LIB_DEFINE(InitLibKernel_1) {\n")
LK_USES = (("Bc5JitShmOn()", 6), ("Bc5JitPosixClose", 4), ("Bc5JitSceClose", 2), ("Bc5JitEnvOn(", 3),
           ("Bc5FwKernelItems()", 2), ("Bc5FwKernelOn(", 2), ("Bc5KernelSendNotificationRequest", 2),
           ("Memory::Bc5JitHandleClose(", 2), ("Memory::Bc5JitArea", 3))

UNITS = (
    # rel, pinned input md5, crlf, block anchor, block, edits, defined-before, used-after, helper uses
    ("src/kernel/memory.cpp", "95d9ca880d01db26d51f0ecabcdfa7e1", False, MEM_BLOCK_ANCHOR, MEM_BLOCK, MEM_EDITS,
     MEM_BEFORE, MEM_AFTER, MEM_USES),
    ("src/libs/libKernel.cpp", "b353287342a8eb82305a4592a4021e3d", False, LK_BLOCK_ANCHOR, LK_BLOCK, LK_EDITS,
     LK_BEFORE, LK_AFTER, LK_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses):
    A, B = T(anchor, crlf), T(block, crlf)
    assert s.count(A) == 1, ("block anchor", rel, s.count(A))
    assert balance(B) == (0, 0, 0), ("the block is not balanced", rel, balance(B))
    at = s.index(A)
    for b in before:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", rel, b[:70], s.count(bb))
    for b in after:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", rel, b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in edits:
        o, n = T(old, crlf), T(new, crlf)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII.
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    if crlf:
        assert out.count(b"\n") == out.count(b"\r\n"), ("a bare LF in the CRLF unit", rel)
    else:
        assert b"\r" not in out, ("a CR in the LF unit", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    check_nids()
    outs = []
    for rel, expect, crlf, anchor, block, edits, before, after, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == expect, ("refused: not the pinned input", rel, md5(s), expect)
        out = edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, {'CRLF' if crlf else 'LF'})", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when both are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()

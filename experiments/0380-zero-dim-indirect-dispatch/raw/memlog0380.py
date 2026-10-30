#!/usr/bin/env python3
# BC5 experiment 0380 (F580): make a PRIVATE copy of the KytyPlus tree's src/kernel/memory.cpp (patch 0001 applied) that
# also prints, to stderr, every direct-memory allocation, map, map2 type, name, range name and Mtypeprotect call: the
# range, the memory type the title passes or the block carries, and the caller's return address. Logging only: no
# behaviour changes. Literal anchors, each must occur once.
# usage: python3 memlog0380.py <tree memory.cpp> <out memory.cpp>
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def rep(a, b):
    global s
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:80]!r}")
    s = s.replace(a, b)


rep('#include "kernel/memory.h"\n',
    '#include "kernel/memory.h"\n'
    '// BC5 experiment 0380 (F580): memory-type logging only, to stderr; changes nothing\n'
    '#define BC5_MEMLOG(...) std::fprintf(stderr, "bc5-0380 mem: " __VA_ARGS__)\n')
rep("""	*phys_addr_out = static_cast<int64_t>(addr);

	LOGF_COLOR(Log::Color::Green, "\\tphys_addr    = %016" PRIx64 "\\n\\t[Ok]\\n", addr);""",
    """	*phys_addr_out = static_cast<int64_t>(addr);
	BC5_MEMLOG("alloc phys 0x%" PRIx64 " len 0x%" PRIx64 " type %d caller %p\\n", addr, static_cast<uint64_t>(len),
	           memory_type, __builtin_return_address(0));

	LOGF_COLOR(Log::Color::Green, "\\tphys_addr    = %016" PRIx64 "\\n\\t[Ok]\\n", addr);""")
rep("""	MapGpuRange(out_addr, len);

	if (g_alloc_callback != nullptr) {
		g_alloc_callback(out_addr, len);
	}

	LOGF_COLOR(Log::Color::Green, "\\t [Ok]\\n");""",
    """	BC5_MEMLOG("map va 0x%" PRIx64 " len 0x%" PRIx64 " phys 0x%" PRIx64 " prot 0x%x flags 0x%x type %d caller %p\\n",
	           static_cast<uint64_t>(out_addr), static_cast<uint64_t>(len), static_cast<uint64_t>(direct_memory_start), prot,
	           flags, mapped_block.memory_type, __builtin_return_address(0));
	MapGpuRange(out_addr, len);

	if (g_alloc_callback != nullptr) {
		g_alloc_callback(out_addr, len);
	}

	LOGF_COLOR(Log::Color::Green, "\\t [Ok]\\n");""")
rep("""		g_physical_memory->SetVirtualRangeMemoryType(out_addr, len, type);
		g_virtual_ranges->SetMemoryType(out_addr, len, type);""",
    """		g_physical_memory->SetVirtualRangeMemoryType(out_addr, len, type);
		g_virtual_ranges->SetMemoryType(out_addr, len, type);
		BC5_MEMLOG("map2 va 0x%" PRIx64 " len 0x%" PRIx64 " type %d caller %p\\n", static_cast<uint64_t>(out_addr),
		           static_cast<uint64_t>(len), type, __builtin_return_address(0));""")
rep("""		g_physical_memory->SetVirtualRangeName(reinterpret_cast<uint64_t>(*addr), len, name);
		g_virtual_ranges->Rename(reinterpret_cast<uint64_t>(*addr), len, name);""",
    """		g_physical_memory->SetVirtualRangeName(reinterpret_cast<uint64_t>(*addr), len, name);
		g_virtual_ranges->Rename(reinterpret_cast<uint64_t>(*addr), len, name);
		BC5_MEMLOG("name va 0x%" PRIx64 " len 0x%" PRIx64 " name %s caller %p\\n", reinterpret_cast<uint64_t>(*addr),
		           static_cast<uint64_t>(len), name, __builtin_return_address(0));""")
rep("""	     reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len), static_cast<uint32_t>(type),
	     static_cast<uint32_t>(prot));

	return KernelMprotect(addr, len, prot);""",
    """	     reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len), static_cast<uint32_t>(type),
	     static_cast<uint32_t>(prot));
	BC5_MEMLOG("mtypeprotect va 0x%" PRIx64 " len 0x%" PRIx64 " type %d prot 0x%x caller %p\\n",
	           reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len), type, prot, __builtin_return_address(0));

	return KernelMprotect(addr, len, prot);""")
rep("""	     vaddr, len, name != nullptr ? name : "(null)");

	if (name == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	if (std::strlen(name) >= KERNEL_MAXIMUM_NAME_LENGTH) {
		return KERNEL_ERROR_ENAMETOOLONG;
	}
""",
    """	     vaddr, len, name != nullptr ? name : "(null)");

	if (name == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	if (std::strlen(name) >= KERNEL_MAXIMUM_NAME_LENGTH) {
		return KERNEL_ERROR_ENAMETOOLONG;
	}
	BC5_MEMLOG("rangename va 0x%" PRIx64 " len 0x%" PRIx64 " name %s caller %p\\n", vaddr, static_cast<uint64_t>(len),
	           name, __builtin_return_address(0));
""")
open(out, "w", encoding="utf-8", newline="\n").write(s)
print(f"{out} written, {s.count('BC5_MEMLOG(') - 1} log points")

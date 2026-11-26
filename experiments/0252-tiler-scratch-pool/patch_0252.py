#!/usr/bin/env python3
# BC5 experiment 0252: reuse the tiler's scratch buffers (KYTY_BC5_TILER_POOL=1, off by default) in a copy of the
# shared tree's src/graphics/host_gpu/renderer/image/tiler.cpp. F308: TileManager::AllocateScratch makes a new VMA
# buffer for every detile and DeferDestroy frees it after the tick; with the launchers' 16-MiB VMA block the display
# buffer's scratch is a dedicated vkAllocateMemory at every flip, which holds the GPU thread for 0.3-0.7 s when the
# box is short of memory. With the switch on, a scratch whose tick has completed goes back to a small pool (at most 4
# buffers, 128 MiB; the smallest dropped first) instead of being destroyed, and AllocateScratch hands out the smallest
# free buffer that fits, else creates one rounded up to 1 MiB. The return happens in the same deferred operation, at
# the same moment, as the original destroy, so a buffer still used by an in-flight upload is never handed out again.
# The header (and so the TileManager layout) is not changed. One stderr line per 1024 scratch requests counts them.
# usage: patch_0252.py <tiler.cpp in> <tiler.cpp out>
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def sub(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit("anchor found %d times, expected %d: %r" % (n, count, old[:80]))
    s = s.replace(old, new)


sub("#include <limits>\n",
    "#include <limits>\n"
    "#include <atomic>\n"
    "#include <cinttypes>\n"
    "#include <cstdio>\n"
    "#include <cstdlib>\n"
    "#include <map>\n"
    "#include <memory>\n"
    "#include <mutex>\n"
    "#include <unordered_map>\n"
    "#include <vector>\n")

POOL = r'''
namespace {

// BC5 (experiment 0252, KYTY_BC5_TILER_POOL=1): the scratch pool of TileManager::AllocateScratch.
constexpr uint64_t TilerPoolGranule  = 1024u * 1024u;
constexpr size_t   TilerPoolMaxFree  = 4;
constexpr uint64_t TilerPoolMaxBytes = 128u * 1024u * 1024u;

// Counted in both modes (the pool off too), for the A/B: scratch requests and new VMA buffers.
std::atomic<uint64_t> g_tiler_requests {0};
std::atomic<uint64_t> g_tiler_new {0};
std::atomic<uint64_t> g_tiler_new_bytes {0};

struct TilerScratchEntry {
	VkBuffer      buffer     = VK_NULL_HANDLE;
	VmaAllocation allocation = nullptr;
	uint64_t      capacity   = 0;
};

struct TilerScratchPool {
	std::mutex                             mutex;
	VmaAllocator                           allocator = nullptr;
	bool                                   closed    = false;
	std::vector<TilerScratchEntry>         free;
	std::unordered_map<VkBuffer, uint64_t> capacity;
	uint64_t                               created       = 0;
	uint64_t                               reused        = 0;
	uint64_t                               destroyed     = 0;
	uint64_t                               created_bytes = 0;
};

bool TilerPoolOn() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_TILER_POOL");
		return e != nullptr && std::strcmp(e, "0") != 0;
	}();
	return on;
}

std::shared_ptr<TilerScratchPool> TilerPoolFor(VmaAllocator allocator) {
	static std::mutex                                               m;
	static std::map<VmaAllocator, std::shared_ptr<TilerScratchPool>> pools;
	std::lock_guard                                                 lock(m);
	auto&                                                           pool = pools[allocator];
	if (pool == nullptr) {
		pool            = std::make_shared<TilerScratchPool>();
		pool->allocator = allocator;
	}
	return pool;
}

// One stderr line per 1024 scratch requests, in both modes; reused and free come from the pool when it is on.
void TilerScratchReport(uint64_t requests, uint64_t reused, size_t free_count) {
	if (requests == 0 || requests % 1024 != 0) {
		return;
	}
	std::fprintf(stderr,
	             "bc5 tiler scratch: %" PRIu64 " requests, %" PRIu64 " new buffers (%.1f MiB), pool %s, %" PRIu64
	             " reused, %zu free\n",
	             requests, g_tiler_new.load(), static_cast<double>(g_tiler_new_bytes.load()) / 1048576.0,
	             TilerPoolOn() ? "on" : "off", reused, free_count);
}

void TilerPoolDestroy(TilerScratchPool& pool, const TilerScratchEntry& entry) {
	pool.capacity.erase(entry.buffer);
	pool.destroyed++;
	VulkanTraceMemory("free", entry.allocation, 0, "tiler scratch");
	vmaDestroyBuffer(pool.allocator, entry.buffer, entry.allocation);
}

void TilerPoolReturn(TilerScratchPool& pool, VkBuffer buffer, VmaAllocation allocation, uint64_t size) {
	std::lock_guard lock(pool.mutex);
	const auto      it = pool.capacity.find(buffer);
	const TilerScratchEntry entry {buffer, allocation, it != pool.capacity.end() ? it->second : size};
	if (pool.closed) {
		TilerPoolDestroy(pool, entry);
		return;
	}
	pool.free.push_back(entry);
	std::sort(pool.free.begin(), pool.free.end(),
	          [](const TilerScratchEntry& a, const TilerScratchEntry& b) { return a.capacity > b.capacity; });
	uint64_t total = 0;
	for (const auto& f: pool.free) {
		total += f.capacity;
	}
	while (!pool.free.empty() && (pool.free.size() > TilerPoolMaxFree || total > TilerPoolMaxBytes)) {
		const auto drop = pool.free.back();
		pool.free.pop_back();
		total -= drop.capacity;
		TilerPoolDestroy(pool, drop);
	}
}

} // namespace

TileManager::TileManager(GraphicContext& graphics, CommandScheduler& scheduler,'''
sub("\nTileManager::TileManager(GraphicContext& graphics, CommandScheduler& scheduler,", POOL)

sub("TileManager::~TileManager() {\n",
    "TileManager::~TileManager() {\n"
    "\tif (TilerPoolOn()) { // BC5 (experiment 0252): the pooled scratch buffers go with the TileManager\n"
    "\t\tauto            pool = TilerPoolFor(m_graphics.allocator);\n"
    "\t\tstd::lock_guard lock(pool->mutex);\n"
    "\t\tpool->closed = true;\n"
    "\t\tfor (const auto& entry: pool->free) {\n"
    "\t\t\tTilerPoolDestroy(*pool, entry);\n"
    "\t\t}\n"
    "\t\tpool->free.clear();\n"
    "\t}\n")

a = s.find("TileManager::Scratch TileManager::AllocateScratch(uint64_t size) {")
b = s.find("void TileManager::Prepare(bool tile")
if a < 0 or b < 0 or b < a:
    sys.exit("AllocateScratch/DeferDestroy region not found")
old_region = s[a:b]
for must in ("vmaCreateBuffer(", "VulkanTraceMemory(\"buffer\", memory, size, \"tiler scratch\");", "void TileManager::DeferDestroy(Scratch scratch) {",
             "VulkanTraceMemory(\"free\", scratch.allocation, 0, \"tiler scratch\");"):
    if must not in old_region:
        sys.exit("region lacks %r (not the patched shared tree?)" % must)

NEW = r'''TileManager::Scratch TileManager::AllocateScratch(uint64_t size) {
	EXIT_IF(size == 0);
	// BC5 (experiment 0252, KYTY_BC5_TILER_POOL=1): hand out a pooled scratch whose last tick has completed
	// instead of a new VMA buffer per detile (F308).
	const bool                        pooled   = TilerPoolOn();
	std::shared_ptr<TilerScratchPool> pool     = pooled ? TilerPoolFor(m_graphics.allocator) : nullptr;
	const uint64_t                    requests = ++g_tiler_requests;
	if (pooled) {
		std::lock_guard lock(pool->mutex);
		size_t          best = pool->free.size();
		for (size_t i = 0; i < pool->free.size(); i++) {
			if (pool->free[i].capacity >= size &&
			    (best == pool->free.size() || pool->free[i].capacity < pool->free[best].capacity)) {
				best = i;
			}
		}
		if (best != pool->free.size()) {
			const auto entry = pool->free[best];
			pool->free.erase(pool->free.begin() + static_cast<std::ptrdiff_t>(best));
			pool->reused++;
			TilerScratchReport(requests, pool->reused, pool->free.size());
			return {vk::Buffer(entry.buffer), entry.allocation, size};
		}
	}
	const uint64_t capacity = pooled ? (size + TilerPoolGranule - 1) / TilerPoolGranule * TilerPoolGranule : size;
	vk::BufferCreateInfo create {};
	create.sType = vk::StructureType::eBufferCreateInfo;
	create.size  = capacity;
	create.usage = vk::BufferUsageFlagBits::eStorageBuffer | vk::BufferUsageFlagBits::eTransferSrc |
	               vk::BufferUsageFlagBits::eTransferDst;
	create.sharingMode = vk::SharingMode::eExclusive;

	VmaAllocationCreateInfo allocate {};
	allocate.usage       = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
	VkBuffer      buffer = VK_NULL_HANDLE;
	VmaAllocation memory = nullptr;
	const auto    raw    = static_cast<VkBufferCreateInfo>(create);
	RequireVulkanSuccess(static_cast<vk::Result>(vmaCreateBuffer(
	                         m_graphics.allocator, &raw, &allocate, &buffer, &memory, nullptr)),
	                     "allocate TileManager scratch buffer");
	VulkanTraceMemory("buffer", memory, capacity, "tiler scratch");
	g_tiler_new++;
	g_tiler_new_bytes += capacity;
	if (pooled) {
		std::lock_guard lock(pool->mutex);
		pool->capacity[buffer] = capacity;
		pool->created++;
		pool->created_bytes += capacity;
		TilerScratchReport(requests, pool->reused, pool->free.size());
	} else {
		TilerScratchReport(requests, 0, 0);
	}
	return {buffer, memory, size};
}

void TileManager::DeferDestroy(Scratch scratch) {
	auto allocator = m_graphics.allocator;
	if (!TilerPoolOn()) {
		m_scheduler.DeferOperation(
		    [allocator, scratch] {
			    VulkanTraceMemory("free", scratch.allocation, 0, "tiler scratch");
			    vmaDestroyBuffer(allocator, scratch.buffer, scratch.allocation);
		    });
		return;
	}
	// BC5 (experiment 0252): back to the pool when its tick has completed -- the moment the original code
	// destroyed it -- so a buffer still read or written by an in-flight upload is never handed out again.
	auto pool = TilerPoolFor(allocator);
	m_scheduler.DeferOperation([pool, scratch] {
		TilerPoolReturn(*pool, static_cast<VkBuffer>(scratch.buffer), scratch.allocation, scratch.size);
	});
}

'''
s = s[:a] + NEW + s[b:]
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("patched: %s -> %s" % (src, dst))

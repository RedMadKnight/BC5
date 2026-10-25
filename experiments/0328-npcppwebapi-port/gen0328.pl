# exp 0328: generates src/libs/libNpCppWebApi.cpp for KytyPlus from AnyPS5's bodies (anyps5-bodies.cpp, the 135 extracted
# + the one hand-added) and the NID map (S1-stub-list-resolved.txt): a GPL-2.0 header naming the origin, the helpers,
# the extern "C" functions named by their mangled symbols (APS5_VABI -> KYTY_SYSV_ABI, NotImplemented -> the tree's
# EXIT), and the LIB_DEFINE with one LIB_FUNC per NID. usage: gen0328.pl <bodies.cpp> <resolved list> <anyps5 commit> <out.cpp>
use strict; use warnings;
my ($bodies, $listf, $commit, $out) = @ARGV;
open(my $bh, "<", $bodies) or die; my $src = do { local $/; <$bh> }; close $bh;
# the one the extractor missed (its argument list holds a function-pointer type with parentheses)
$src .= <<'EOT';
void APS5_VABI _ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS2_6VectorINS2_6StringEEEEC1EPS6_PFvS8_EPNS2_10LibContextE(IntrusivePtr* self, void* body, void (APS5_VABI* deleter)(void*), void* libContext) {
    self->object = body;
    self->deleter = deleter;
    self->libContext = libContext;
}

EOT
$src =~ s/APS5_VABI/KYTY_SYSV_ABI/g;
$src =~ s/NotImplemented_nid_no_patch\(/NotImplemented(/g;
my %nid; open(my $l, '<', $listf) or die; while (<$l>) { next if /^#/; my ($n, $lib, $name) = split; $nid{$name} = $n if defined $name && $name =~ /^_Z/; } close $l;
my @syms = ($src =~ /KYTY_SYSV_ABI\s+(_Z[A-Za-z0-9_]+)\s*\(/g);
my %seen; my @table;
for my $s (@syms) { next if $seen{$s}++; die "no NID for $s\n" unless $nid{$s}; push @table, [$nid{$s}, $s]; }
my $n = scalar @table;
open(my $o, '>', $out) or die;
print $o <<"EOT";
// SPDX-License-Identifier: GPL-2.0-only
// KytyPlus host library: libSceNpCppWebApi (the PS5's C++ web API — Common, SessionManager V1, TitleCloudStorage V1)
// for a console that is not signed in to PSN.
//
// BC5 experiment 0328. Ported from AnyPS5 (boykopovar/AnyPS5, GPL-2.0, commit $commit), file
// core/libs/prx/libSceNpCppWebApi/Export.cpp: the intrusive-pointer, string and vector machinery and the $n
// entry points the second title imports (the title's link list, experiment 0327). AnyPS5's design is kept: each
// exported C++ member is an extern "C" function named by its mangled symbol, taking `this` explicitly; objects
// are constructed and released properly (reference counts at the console's offsets, the deleter the object
// carries); every request entry point fails as a console without a PSN sign-in fails, with
// SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN (0x80552907, the constant shadPS4 and fpPS4 document); parameter bookkeeping
// succeeds; response accessors cannot be reached after a failed request and stop the emulator with a named
// message instead of returning garbage. Changes from AnyPS5: APS5_VABI -> KYTY_SYSV_ABI, NotImplemented ->
// the tree's EXIT, the registration through LIB_FUNC by NID (SHA1 of the mangled name, experiment 0327's calculator).
// AnyPS5's copyright remains with its authors; this file is GPL-2.0 as the rest of the KytyPlus host.

#include "common/abi.h"
#include "common/assert.h"
#include "common/hostException.h"
#include "common/logging/log.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace Libs::NpCppWebApi {

LIB_VERSION("NpCppWebApi", 1, "NpCppWebApi", 1, 1);

static constexpr int SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN = static_cast<int>(0x80552907);

// A response accessor or an unknown object layout: on the console this cannot happen after a request that failed,
// so the title is stopped with the symbol's name rather than handed a wrong value (AnyPS5 aborts the same way).
[[noreturn]] static void NotImplemented(const char* function) {
	{
		Common::HostException::RawLog log;
		log.Append("[bc5] NpCppWebApi: not reachable offline, stopping: ");
		log.Append(function);
		log.Append("\\n");
		log.Flush();
	}
	EXIT("NpCppWebApi: %s is not reachable on an offline console\\n", function);
}

extern "C" {

struct IntrusivePtr {
	void* object;
	void (KYTY_SYSV_ABI* deleter)(void*);
	void* libContext;
};
static_assert(sizeof(IntrusivePtr) == 0x18);

static constexpr std::size_t ReferenceCountOffset       = 0;
static constexpr std::size_t VectorReferenceCountOffset = 0x30;

static std::atomic_ref<std::int32_t> ReferenceCount(void* object, const std::size_t offset) {
	return std::atomic_ref<std::int32_t>(*reinterpret_cast<std::int32_t*>(static_cast<std::uint8_t*>(object) + offset));
}

static void CopyIntrusivePtr(IntrusivePtr* self, const IntrusivePtr* source, const std::size_t referenceCountOffset) {
	*self = *source;
	if (self->object) ReferenceCount(self->object, referenceCountOffset).fetch_add(1);
}

static void ReleaseIntrusivePtr(IntrusivePtr* self, const std::size_t referenceCountOffset, const char* function) {
	if (!self->object) return;
	if (ReferenceCount(self->object, referenceCountOffset).fetch_sub(1) != 1) return;
	if (!self->deleter) NotImplemented(function);
	self->deleter(self->object);
	self->object  = nullptr;
	self->deleter = nullptr;
}

struct CommonString {
	std::int32_t  referenceCount;
	char*         buffer;
	std::uint64_t bufferSize;
	void*         libContext;
};
static_assert(sizeof(CommonString) == 0x20 && offsetof(CommonString, buffer) == 0x08);
static_assert(offsetof(CommonString, bufferSize) == 0x10 && offsetof(CommonString, libContext) == 0x18);

static constexpr std::uint64_t VectorBodyMagic = 0x434e507056656342ULL;
struct VectorBody {
	std::uint64_t magic;
	std::uint8_t  reserved[0x28];
	std::int32_t  referenceCount;
	std::int32_t  elementKind; // 1 = IntrusivePtr elements, 2 = String elements
	void*         elements;
	std::uint64_t size;
	std::uint64_t capacity;
};
static_assert(sizeof(VectorBody) == 0x50 && offsetof(VectorBody, referenceCount) == 0x30);

static void KYTY_SYSV_ABI DestroyVectorBody(void* object) {
	auto* body = static_cast<VectorBody*>(object);
	if (body->elementKind == 1) {
		auto* elements = static_cast<IntrusivePtr*>(body->elements);
		for (std::uint64_t index = 0; index < body->size; ++index) {
			ReleaseIntrusivePtr(&elements[index], 0x00, __func__);
		}
	} else if (body->elementKind == 2) {
		auto* elements = static_cast<CommonString*>(body->elements);
		for (std::uint64_t index = 0; index < body->size; ++index) {
			std::free(elements[index].buffer);
		}
	}
	std::free(body->elements);
	std::free(body);
}

static VectorBody* VectorBodyFor(IntrusivePtr* self, const std::int32_t elementKind, const char* function) {
	auto* body = static_cast<VectorBody*>(self->object);
	if (body == nullptr) {
		body = static_cast<VectorBody*>(std::calloc(1, sizeof(VectorBody)));
		if (body == nullptr) return nullptr;
		body->magic          = VectorBodyMagic;
		body->referenceCount = 1;
		body->elementKind    = elementKind;
		self->object         = body;
		self->deleter        = &DestroyVectorBody;
		return body;
	}
	if (body->magic != VectorBodyMagic || body->elementKind != elementKind) {
		// appending to a title-provided body needs its element layout, which is unknown
		NotImplemented(function);
		return nullptr;
	}
	return body;
}

static bool VectorGrow(VectorBody* body, const std::size_t elementSize) {
	if (body->size < body->capacity) return true;
	const std::uint64_t capacity = body->capacity != 0 ? body->capacity * 2 : 4;
	void* elements = std::realloc(body->elements, static_cast<std::size_t>(capacity) * elementSize);
	if (elements == nullptr) return false;
	body->elements = elements;
	body->capacity = capacity;
	return true;
}

static int VectorPushBackIntrusivePtr(IntrusivePtr* self, const IntrusivePtr* element) {
	VectorBody* body = VectorBodyFor(self, 1, __func__);
	if (body == nullptr) return -1;
	if (!VectorGrow(body, sizeof(IntrusivePtr))) return -1;
	auto* elements = static_cast<IntrusivePtr*>(body->elements);
	elements[body->size] = *element;
	if (element->object != nullptr) ReferenceCount(element->object, ReferenceCountOffset).fetch_add(1);
	body->size += 1;
	return 0;
}

static int VectorPushBackString(IntrusivePtr* self, const CommonString* element) {
	VectorBody* body = VectorBodyFor(self, 2, __func__);
	if (body == nullptr) return -1;
	if (!VectorGrow(body, sizeof(CommonString))) return -1;
	CommonString copy   = *element;
	copy.referenceCount = 0;
	copy.buffer         = nullptr;
	copy.bufferSize     = 0;
	if (element->buffer != nullptr) {
		const std::size_t length = std::strlen(element->buffer) + 1;
		copy.buffer = static_cast<char*>(std::malloc(length));
		if (copy.buffer == nullptr) return -1;
		std::memcpy(copy.buffer, element->buffer, length);
		copy.bufferSize = length;
	}
	static_cast<CommonString*>(body->elements)[body->size] = copy;
	body->size += 1;
	return 0;
}

// ---- the title's $n entry points (AnyPS5's bodies) ----

EOT
print $o $src;
print $o "} // extern \"C\"\n\nLIB_DEFINE(InitNpCppWebApi_1) {\n";
for my $t (sort { $a->[1] cmp $b->[1] } @table) { printf $o "\tLIB_FUNC(\"%s\", %s);\n", $t->[0], $t->[1]; }
print $o "}\n\n} // namespace Libs::NpCppWebApi\n";
close $o;
print "wrote $out: $n entry points registered\n";

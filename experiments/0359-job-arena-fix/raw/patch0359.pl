#!/usr/bin/perl
# BC5 experiment 0359: the job-arena fix (a TEMPORARY game-code workaround for the second title, PPSA03671) in a PRIVATE
# copy of four host units (the shared tree is only read). See backend/include/bc5/job_arena_fix.hpp for what it does.
#   loader/gamePatch.cpp (+ .h): the host hook bc5_job_arena_owner_help() (the title's own override window around the
#       owner's help call) and GamePatch::ApplyJobArenaFix(): title check, exact expected bytes at the site and the
#       slot, the slot written with the hook's address, the site rewritten to call through the slot; a log line
#       either way.
#   loader/runtimeLinker.cpp: bc5_tls_main_tcb() (the current thread's thread control block of the main program) and
#       the call to ApplyJobArenaFix() right after the game-patch plan, before the modules start.
#   graphics/presentation/window/hostInput.cpp (+ .h): JobArenaFix.<TITLE_ID>=on|off in the input configuration
#       (read, saved, kept for other titles), HostInputJobArenaFix() / HostInputSetJobArenaFix(), the environment
#       override KYTY_BC5_JOB_ARENA_FIX=0|1, and the extern "C" getter the loader calls.
#   graphics/presentation/hostMenu.cpp: Emulation -> Game fixes -> "Job-arena fix (temporary, next start)".
# usage: patch0359.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0359.pl <src root>\n" unless defined $root;
my $marks = 0;
sub patch {
	my ($file, @pairs) = @_;
	open(my $h, "<", $file) or die "$file: $!\n";
	my $s = do { local $/; <$h> };
	close $h;
	my $crlf = ($s =~ /\r\n/) ? 1 : 0;
	while (@pairs) {
		my $old = shift @pairs;
		my $new = shift @pairs;
		if ($crlf) {
			$old =~ s/\n/\r\n/g;
			$new =~ s/\n/\r\n/g;
		}
		my $n = () = $s =~ /\Q$old\E/g;
		die "$file: anchor found $n times, expected once:\n$old\n" unless $n == 1;
		$s =~ s/\Q$old\E/$new/;
		$marks++;
	}
	open(my $w, ">", $file) or die "$file: $!\n";
	print $w $s;
	close $w;
}

# ---- loader/gamePatch.h
patch("$root/src/loader/gamePatch.h",
	"bool Apply(const std::filesystem::path& plan_path, Program* program);\n",
	"bool Apply(const std::filesystem::path& plan_path, Program* program);\n\n" .
	"// BC5 (experiment 0359): the job-arena fix for PPSA03671, a TEMPORARY game-code workaround (bc5/job_arena_fix.hpp).\n" .
	"// setting: the title's switch, -1 not set (on for that title), 0 off, 1 on. True when applied.\n" .
	"bool ApplyJobArenaFix(Program* program, int setting);\n",
);

# ---- loader/gamePatch.cpp
my $hook =
	"// BC5 (experiment 0359): the job-arena fix, a TEMPORARY game-code workaround for the second title. What and why:\n" .
	"// bc5/job_arena_fix.hpp. The hook replaces the owner's help call `call [r15+0x80]` (eboot.bin+0x3cca87b) and\n" .
	"// wraps the title's own call in the title's own override window: the special index into the thread's worker slot\n" .
	"// and a stack arena, built as the title builds it, into image+0xb064018; both restored after. To be REMOVED once\n" .
	"// the host's throughput at the fight is fixed (docs/HANDOFF.md Q24).\n" .
	"extern \"C\" uint8_t* bc5_tls_main_tcb(); // loader/runtimeLinker.cpp: the current thread's tcb of the main program\n" .
	"static uint64_t              g_bc5_jaf_base = 0;\n" .
	"static std::atomic<uint64_t> g_bc5_jaf_calls {0};\n" .
	"static std::atomic<uint64_t> g_bc5_jaf_wrapped {0};\n" .
	"using bc5_guest_block_fn = void (KYTY_SYSV_ABI*)(void* job, void* block, uint64_t size, uint32_t n1);\n" .
	"extern \"C\" KYTY_SYSV_ABI void bc5_job_arena_owner_help(void* job, void* block, uint64_t size, uint32_t n1) {\n" .
	"\tusing namespace bc5::job_arena_fix;\n" .
	"\tconst uint64_t base = g_bc5_jaf_base;\n" .
	"\tconst auto     fn   = *reinterpret_cast<const bc5_guest_block_fn*>(static_cast<uint8_t*>(job) + 0x80);\n" .
	"\tuint8_t*       tcb  = bc5_tls_main_tcb();\n" .
	"\tauto*          index = reinterpret_cast<int32_t*>(tcb + kIndexSlotFromTcb);\n" .
	"\tauto*          slot  = reinterpret_cast<uint64_t*>(base + kOverrideArenaOffset);\n" .
	"\tconst int32_t  old_index = *index;\n" .
	"\tconst uint64_t old_slot  = *slot;\n" .
	"\tconst bool     wrap      = wrap_needed(old_index);\n" .
	"\talignas(16) OverrideArena arena {};\n" .
	"\tif (wrap) {\n" .
	"\t\tbuild_arena(&arena, reinterpret_cast<uint64_t>(block), static_cast<uint32_t>(size), reinterpret_cast<const uint8_t*>(base + kArenaConstsOffset),\n" .
	"\t\t            base + kArenaTailOffset);\n" .
	"\t\t*slot  = reinterpret_cast<uint64_t>(&arena);\n" .
	"\t\t*index = *reinterpret_cast<const int32_t*>(base + kSpecialIndexOffset);\n" .
	"\t}\n" .
	"\tconst uint64_t n = g_bc5_jaf_calls.fetch_add(1, std::memory_order_relaxed) + 1;\n" .
	"\tconst uint64_t w = wrap ? g_bc5_jaf_wrapped.fetch_add(1, std::memory_order_relaxed) + 1 : g_bc5_jaf_wrapped.load(std::memory_order_relaxed);\n" .
	"\tif (n == 1 || n % 1000 == 0) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: job-arena hook call %\" PRIu64 \" (%\" PRIu64 \" wrapped), thread index %d%s\\n\", n, w, old_index, wrap ? \" -> the window\" : \"\");\n" .
	"\t}\n" .
	"\tfn(job, block, size, n1);\n" .
	"\tif (wrap) {\n" .
	"\t\t*slot  = old_slot;\n" .
	"\t\t*index = old_index;\n" .
	"\t}\n" .
	"}\n\n" .
	"bool ApplyJobArenaFix(Program* program, int setting) {\n" .
	"\tusing namespace bc5::job_arena_fix;\n" .
	"\tstd::string title;\n" .
	"\tSystemContentParamSfoGetString(\"TITLE_ID\", &title);\n" .
	"\tconst bool  title_ok = Common::EqualNoCase(title, kTitleId);\n" .
	"\tconst char* src      = setting == 1 ? \"input.cfg on\" : setting == 0 ? \"input.cfg off\" : \"not set, on for that title\";\n" .
	"\tconst bool  on       = setting == 1 || (setting < 0 && title_ok);\n" .
	"\tstd::fprintf(stderr, \"game fix (temporary, exp 0359): job-arena fix %s for %s (%s)\\n\", on ? \"ON\" : \"OFF\", title.c_str(), src);\n" .
	"\tif (!on) return false;\n" .
	"\tif (!title_ok) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: not applied, the fix is for %s only\\n\", kTitleId);\n" .
	"\t\treturn false;\n" .
	"\t}\n" .
	"\tif (program == nullptr || program->elf == nullptr || program->base_vaddr == 0) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: not applied, the main executable is not loaded\\n\");\n" .
	"\t\treturn false;\n" .
	"\t}\n" .
	"\tconst uint64_t base = program->base_vaddr;\n" .
	"\tauto*          site = reinterpret_cast<uint8_t*>(base + kSiteOffset);\n" .
	"\tauto*          slot = reinterpret_cast<uint8_t*>(base + kSlotOffset);\n" .
	"\tif (!site_matches(site) || !slot_matches(slot)) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: not applied, the bytes at +0x%\" PRIx64 \" or +0x%\" PRIx64 \" are not the expected ones (another build of the title?)\\n\", kSiteOffset, kSlotOffset);\n" .
	"\t\treturn false;\n" .
	"\t}\n" .
	"\tstd::array<uint8_t, 7> enc {};\n" .
	"\tif (!encode_site(base + kSiteOffset, base + kSlotOffset, &enc)) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: not applied, the slot is out of reach\\n\");\n" .
	"\t\treturn false;\n" .
	"\t}\n" .
	"\tg_bc5_jaf_base      = base;\n" .
	"\tconst uint64_t hook = reinterpret_cast<uint64_t>(&bc5_job_arena_owner_help);\n" .
	"\tstd::memcpy(slot, &hook, sizeof(hook));\n" .
	"\tstd::memcpy(site, enc.data(), enc.size());\n" .
	"\tif (!Common::VirtualMemory::FlushInstructionCache(reinterpret_cast<uint64_t>(site), enc.size()) ||\n" .
	"\t    !Common::VirtualMemory::FlushInstructionCache(reinterpret_cast<uint64_t>(slot), sizeof(hook))) {\n" .
	"\t\tstd::fprintf(stderr, \"game fix: the instruction cache flush failed after the write\\n\");\n" .
	"\t}\n" .
	"\tstd::fprintf(stderr, \"game fix: job-arena fix APPLIED: site +0x%\" PRIx64 \" -> slot +0x%\" PRIx64 \" -> host hook %p (temporary; input.cfg JobArenaFix.%s=off turns it off)\\n\",\n" .
	"\t             kSiteOffset, kSlotOffset, reinterpret_cast<void*>(hook), kTitleId);\n" .
	"\treturn true;\n" .
	"}\n\n";
patch("$root/src/loader/gamePatch.cpp",
	"#include \"loader/systemContent.h\"\n",
	"#include \"loader/systemContent.h\"\n#include \"bc5/job_arena_fix.hpp\" // BC5 (experiment 0359)\n#include \"common/abi.h\"\n\n#include <array>\n#include <atomic>\n#include <cinttypes>\n#include <cstdint>\n",

	"} // namespace\n\nbool Apply(const std::filesystem::path& plan_path, Program* program) {\n",
	"} // namespace\n\n" . $hook . "bool Apply(const std::filesystem::path& plan_path, Program* program) {\n",
);

# ---- loader/runtimeLinker.cpp
patch("$root/src/loader/runtimeLinker.cpp",
	"static Program*              g_tls_main_program        = nullptr;\n",
	"static Program*              g_tls_main_program        = nullptr;\n" .
	"extern \"C\" int bc5_title_switch_job_arena_fix(); // graphics/presentation/window/hostInput.cpp, BC5 (experiment 0359)\n",

	"\tg_tls_cached_main_tcb =\n\t    RuntimeLinker::TlsGetAddr(g_tls_main_program) + g_tls_main_program->tls.tcb_offset;\n\treturn g_tls_cached_main_tcb;\n}\n",
	"\tg_tls_cached_main_tcb =\n\t    RuntimeLinker::TlsGetAddr(g_tls_main_program) + g_tls_main_program->tls.tcb_offset;\n\treturn g_tls_cached_main_tcb;\n}\n\n" .
	"// BC5 (experiment 0359): the current thread's thread control block of the main program, for the job-arena hook.\n" .
	"extern \"C\" uint8_t* bc5_tls_main_tcb() {\n\treturn TlsMainGetAddr();\n}\n",

	"\tif (!game_patch.empty()) {\n\t\tGamePatch::Apply(game_patch, m_programs.empty() ? nullptr : m_programs.front());\n\t}\n",
	"\tif (!game_patch.empty()) {\n\t\tGamePatch::Apply(game_patch, m_programs.empty() ? nullptr : m_programs.front());\n\t}\n" .
	"\t// BC5 (experiment 0359): the job-arena fix (a temporary game-code workaround), per the title's switch.\n" .
	"\tGamePatch::ApplyJobArenaFix(m_programs.empty() ? nullptr : m_programs.front(), bc5_title_switch_job_arena_fix());\n",
);

# ---- graphics/presentation/window/hostInput.h
patch("$root/src/graphics/presentation/window/hostInput.h",
	"std::string HostInputTitleId();\n",
	"std::string HostInputTitleId();\n" .
	"// BC5 (experiment 0359): the job-arena fix switch (JobArenaFix.<TITLE_ID>=on|off): -1 not set, 0 off, 1 on;\n" .
	"// KYTY_BC5_JOB_ARENA_FIX=0|1 overrides the file.\n" .
	"int  HostInputJobArenaFix();\n" .
	"void HostInputSetJobArenaFix(int v);\n",
);

# ---- graphics/presentation/window/hostInput.cpp
patch("$root/src/graphics/presentation/window/hostInput.cpp",
	"\t\tif (m_mangohud >= 0) out.emplace_back(\"MangoHud.\" + HostInputTitleId() + (m_mangohud == 1 ? \"=on\" : \"=off\")); // experiment 0301\n",
	"\t\tif (m_mangohud >= 0) out.emplace_back(\"MangoHud.\" + HostInputTitleId() + (m_mangohud == 1 ? \"=on\" : \"=off\")); // experiment 0301\n" .
	"\t\tif (m_job_arena_fix >= 0) out.emplace_back(\"JobArenaFix.\" + HostInputTitleId() + (m_job_arena_fix == 1 ? \"=on\" : \"=off\")); // experiment 0359\n",

	"\t[[nodiscard]] int    MangoHud() const { return m_mangohud; } // experiment 0301: -1 not set, 0 off, 1 on\n",
	"\t[[nodiscard]] int    MangoHud() const { return m_mangohud; } // experiment 0301: -1 not set, 0 off, 1 on\n" .
	"\t[[nodiscard]] int    JobArenaFix() const { return m_job_arena_fix; } // experiment 0359: -1 not set, 0 off, 1 on\n" .
	"\tvoid                 SetJobArenaFix(int v) { m_job_arena_fix = v; }\n",

	"\t\t\t\tm_other_title_scales.emplace_back(\"MangoHud.\" + id + (v == 1 ? \"=on\" : \"=off\")); // another title's line, kept\n\t\t\t}\n\t\t\treturn true;\n\t\t}\n",
	"\t\t\t\tm_other_title_scales.emplace_back(\"MangoHud.\" + id + (v == 1 ? \"=on\" : \"=off\")); // another title's line, kept\n\t\t\t}\n\t\t\treturn true;\n\t\t}\n\n" .
	"\t\tif (left.size() > 12 && EqualNoCase(left.substr(0, 12), \"JobArenaFix.\")) { // experiment 0359, per title (a temporary game fix)\n" .
	"\t\t\tint v = -1;\n" .
	"\t\t\tif (EqualNoCase(right, \"on\") || EqualNoCase(right, \"true\") || right == \"1\") {\n" .
	"\t\t\t\tv = 1;\n" .
	"\t\t\t} else if (EqualNoCase(right, \"off\") || EqualNoCase(right, \"false\") || right == \"0\") {\n" .
	"\t\t\t\tv = 0;\n" .
	"\t\t\t} else {\n" .
	"\t\t\t\treturn Fail(error, where + \": JobArenaFix takes on or off, got: \" + std::string(right));\n" .
	"\t\t\t}\n" .
	"\t\t\tconst std::string id(left.substr(12));\n" .
	"\t\t\tif (EqualNoCase(id, HostInputTitleId())) {\n" .
	"\t\t\t\tm_job_arena_fix = v;\n" .
	"\t\t\t} else {\n" .
	"\t\t\t\tm_other_title_scales.emplace_back(\"JobArenaFix.\" + id + (v == 1 ? \"=on\" : \"=off\")); // another title's line, kept\n" .
	"\t\t\t}\n" .
	"\t\t\treturn true;\n" .
	"\t\t}\n",

	"\tint                  m_mangohud         = -1;  // experiment 0301: -1 not set (off, or KYTY_BC5_MANGOHUD=1), 0 off, 1 on\n",
	"\tint                  m_mangohud         = -1;  // experiment 0301: -1 not set (off, or KYTY_BC5_MANGOHUD=1), 0 off, 1 on\n" .
	"\tint                  m_job_arena_fix    = -1;  // experiment 0359: -1 not set (on for PPSA03671), 0 off, 1 on; a temporary game fix\n",

	"int HostInputSystemLanguage() {\n",
	"// BC5 (experiment 0359): the job-arena fix switch, JobArenaFix.<TITLE_ID>=on|off; KYTY_BC5_JOB_ARENA_FIX=0|1 overrides it.\n" .
	"int HostInputJobArenaFix() {\n" .
	"\tif (const char* e = std::getenv(\"KYTY_BC5_JOB_ARENA_FIX\"); e != nullptr && *e != 0) return *e == '0' ? 0 : 1;\n" .
	"\treturn g_map != nullptr ? g_map->JobArenaFix() : -1;\n" .
	"}\n" .
	"void HostInputSetJobArenaFix(int v) {\n" .
	"\tif (g_map != nullptr) g_map->SetJobArenaFix(v);\n" .
	"}\n" .
	"extern \"C\" int bc5_title_switch_job_arena_fix() { // for loader/runtimeLinker.cpp\n" .
	"\treturn HostInputJobArenaFix();\n" .
	"}\n\n" .
	"int HostInputSystemLanguage() {\n",
);

# ---- graphics/presentation/hostMenu.cpp
patch("$root/src/graphics/presentation/hostMenu.cpp",
	"\t\t\t\tif (g_hud_lost.load(std::memory_order_acquire) && ImGui::IsItemHovered()) {\n" .
	"\t\t\t\t\tImGui::SetTooltip(\"MangoHud is not loaded: only the game's frame rate is shown.\");\n" .
	"\t\t\t\t}\n" .
	"\t\t\t}\n",
	"\t\t\t\tif (g_hud_lost.load(std::memory_order_acquire) && ImGui::IsItemHovered()) {\n" .
	"\t\t\t\t\tImGui::SetTooltip(\"MangoHud is not loaded: only the game's frame rate is shown.\");\n" .
	"\t\t\t\t}\n" .
	"\t\t\t}\n" .
	"\t\t\t// Experiment 0359: game fixes - TEMPORARY game-code workarounds, per title, saved like the switches above;\n" .
	"\t\t\t// applied at load, so a change takes effect at the next start.\n" .
	"\t\t\tif (ImGui::BeginMenu(\"Game fixes\")) {\n" .
	"\t\t\t\tconst int  v  = HostInputJobArenaFix();\n" .
	"\t\t\t\tconst bool on = v == 1 || (v < 0 && HostInputTitleId() == \"PPSA03671\");\n" .
	"\t\t\t\tif (ImGui::MenuItem(\"Job-arena fix (temporary, next start)\", nullptr, on, !launcher)) {\n" .
	"\t\t\t\t\tHostInputSetJobArenaFix(on ? 0 : 1);\n" .
	"\t\t\t\t\tSaveTitleSwitch(\"JobArenaFix\", \"job-arena fix\", !on);\n" .
	"\t\t\t\t}\n" .
	"\t\t\t\tif (ImGui::IsItemHovered()) {\n" .
	"\t\t\t\t\tImGui::SetTooltip(\"Wraps the title's frame-end job run on its main thread in the title's own arena window\\n\"\n" .
	"\t\t\t\t\t                  \"(experiment 0359): a workaround for the null-arena crash at the fight. Takes effect at the\\n\"\n" .
	"\t\t\t\t\t                  \"next start. To be removed once the host's throughput at the fight is fixed.\");\n" .
	"\t\t\t\t}\n" .
	"\t\t\t\tImGui::EndMenu();\n" .
	"\t\t\t}\n",
);
print "patch0359.pl: $marks edits\n";

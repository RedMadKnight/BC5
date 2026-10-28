#!/usr/bin/perl
# BC5 experiment 0356: the AMM fault ledger in a PRIVATE copy of three host units (the shared tree is only read).
#   libAmpr.cpp: the ledger (ammLedger.h beside it); every AMM command pends at submission, executed commands
#                move to the ring; a dropped buffer's commands leave the pending list; bc5_amm_fault() for the
#                fault handler: a pending map covering the page is waited for (up to 3 s) and the access retried,
#                else the page's history is printed and the host gives up as before.
#   memory.cpp:  KernelHandleReservedRangeAccessViolation asks bc5_amm_fault() before the EXIT, and says so.
#   runtimeLinker.cpp: the faulting instruction (module + offset) is printed for every fault that reaches the
#                reserved-range handler, not only with KYTY_BC5_AMM_TRACE.
# usage: patch0356.pl <private src root>   (holds src/libs/libAmpr.cpp, src/kernel/memory.cpp, src/loader/runtimeLinker.cpp)
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0356.pl <src root>\n" unless defined $root;
my $marks = 0;
sub patch {
	my ($file, @pairs) = @_;
	open(my $h, "<", $file) or die "$file: $!\n";
	my $s = do { local $/; <$h> };
	close $h;
	while (@pairs) {
		my $old = shift @pairs;
		my $new = shift @pairs;
		my $n = () = $s =~ /\Q$old\E/g;
		die "$file: anchor found $n times, expected once:\n$old\n" unless $n == 1;
		$s =~ s/\Q$old\E/$new/;
		$marks++;
	}
	open(my $w, ">", $file) or die "$file: $!\n";
	print $w $s;
	close $w;
}

my $ampr = "$root/src/libs/libAmpr.cpp";
patch($ampr,
	"#include \"loader/symbolDatabase.h\"\n",
	"#include \"loader/symbolDatabase.h\"\n#include \"libs/ammLedger.h\" // BC5 (experiment 0356)\nusing Kyty::Libs::LibAmpr::AmmLedger; // BC5 (experiment 0356): the unit's code sits in a nested namespace\n",

	"static uint64_t g_amm_window_start = 0;\n",
	"static uint64_t g_amm_window_start = 0;\n" .
	"// BC5 (experiment 0356): the AMM command ledger, asked by the reserved-range fault handler (memory.cpp).\n" .
	"static AmmLedger g_amm_ledger;\n" .
	"static uint64_t  AmmLedgerNow() {\n" .
	"\treturn static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());\n" .
	"}\n" .
	"static AmmLedger::Kind AmmLedgerKind(AmmCommandKind k) {\n" .
	"\tswitch (k) {\n" .
	"\t\tcase AmmCommandKind::MapAuto: return AmmLedger::MapAuto;\n" .
	"\t\tcase AmmCommandKind::MapDirect: return AmmLedger::MapDirect;\n" .
	"\t\tcase AmmCommandKind::Unmap: return AmmLedger::Unmap;\n" .
	"\t\tdefault: return AmmLedger::Other;\n" .
	"\t}\n" .
	"}\n" .
	"// The fault handler's question (experiment 0356): is the page the title touched about to be mapped by a\n" .
	"// submitted AMM command the worker has not reached yet? Then the access waits for that command (polled,\n" .
	"// at most 3 s) and retries; the console's AMM unit is fast enough that a title can touch a page right\n" .
	"// after submitting its map, the host's worker is not. Any other case prints the page's history and\n" .
	"// returns 0: the host gives up as before, now with the cause on record.\n" .
	"extern \"C\" int bc5_amm_fault(uint64_t vaddr) {\n" .
	"\tAmmLedger::Entry e {};\n" .
	"\tif (g_amm_ledger.PendingMapCovering(vaddr, &e)) {\n" .
	"\t\tstd::fprintf(stderr, \"amm fault: 0x%016\" PRIx64 \" lies in a pending %s (va 0x%016\" PRIx64 \" size 0x%\" PRIx64 \" cb 0x%016\" PRIx64 \" +0x%\" PRIx64 \" sub %u q%u, submitted %.3f s): waiting for it\\n\",\n" .
	"\t\t             vaddr, AmmLedger::KindName(e.kind), e.va, e.size, e.command_buffer, e.record_offset, e.submission_id, e.queue, static_cast<double>(e.t_ns) / 1e9);\n" .
	"\t\tconst auto t0 = std::chrono::steady_clock::now();\n" .
	"\t\twhile (g_amm_ledger.IsPending(e.command_buffer, e.record_offset)) {\n" .
	"\t\t\tif (std::chrono::steady_clock::now() - t0 > std::chrono::seconds(3)) {\n" .
	"\t\t\t\tstd::fprintf(stderr, \"amm fault: the pending map did not execute within 3 s\\n\");\n" .
	"\t\t\t\tg_amm_ledger.Dump(vaddr, stderr);\n" .
	"\t\t\t\treturn 0;\n" .
	"\t\t\t}\n" .
	"\t\t\tstd::this_thread::sleep_for(std::chrono::microseconds(200));\n" .
	"\t\t}\n" .
	"\t\tstd::fprintf(stderr, \"amm fault: the map executed after %.1f ms; the access is retried\\n\",\n" .
	"\t\t             std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count());\n" .
	"\t\treturn 1;\n" .
	"\t}\n" .
	"\tg_amm_ledger.Dump(vaddr, stderr);\n" .
	"\treturn 0;\n" .
	"}\n",

	"\t\t\t\tif (command.kind == AmmCommandKind::Unmap) {\n\t\t\t\t\tresult = LibKernel::Memory::KernelMunmap(command.va, command.size);\n",
	"\t\t\t\tif (command.kind == AmmCommandKind::Unmap) {\n\t\t\t\t\tresult = LibKernel::Memory::KernelMunmap(command.va, command.size);\n\t\t\t\t\tg_amm_ledger.Executed(command_buffer, command.record_offset, result, AmmLedgerNow()); // BC5 (experiment 0356)\n",

	"\t\t\t\t} else {\n\t\t\t\t\tresult = ExecuteAmmMapCommand(command);\n\t\t\t\t}\n",
	"\t\t\t\t} else {\n\t\t\t\t\tresult = ExecuteAmmMapCommand(command);\n\t\t\t\t\tg_amm_ledger.Executed(command_buffer, command.record_offset, result, AmmLedgerNow()); // BC5 (experiment 0356)\n\t\t\t\t}\n",

	"\tconst bool amm_only = !state.amm_map_commands.empty() && state.read_file_commands.empty();\n\tconst size_t qi = AprQueueIndex(priority);\n",
	"\tconst bool amm_only = !state.amm_map_commands.empty() && state.read_file_commands.empty();\n\tconst size_t qi = AprQueueIndex(priority);\n" .
	"\tfor (const auto& oc : ordered) { // BC5 (experiment 0356): every AMM command of this submission pends until the worker runs it\n" .
	"\t\tif (oc.kind != CommandKind::AmmMap) continue;\n" .
	"\t\tconst auto&      c = state.amm_map_commands[oc.index];\n" .
	"\t\tAmmLedger::Entry e {};\n" .
	"\t\te.command_buffer = command_buffer;\n" .
	"\t\te.record_offset  = c.record_offset;\n" .
	"\t\te.va             = c.va;\n" .
	"\t\te.size           = c.size;\n" .
	"\t\te.kind           = AmmLedgerKind(c.kind);\n" .
	"\t\te.submission_id  = submission_id;\n" .
	"\t\te.queue          = static_cast<uint8_t>(qi);\n" .
	"\t\te.t_ns           = AmmLedgerNow();\n" .
	"\t\tg_amm_ledger.Pend(e);\n" .
	"\t}\n",
);

# a buffer that stops at a failed command leaves its remaining AMM commands pending forever: FinishAprSubmission drops them
patch($ampr,
	"static void FinishAprSubmission(const ParkedAprBuffer& b, int32_t result, uint32_t offset) {\n",
	"static void FinishAprSubmission(const ParkedAprBuffer& b, int32_t result, uint32_t offset) {\n\tg_amm_ledger.Dropped(b.command_buffer); // BC5 (experiment 0356): nothing of it pends any more\n",
);

my $mem = "$root/src/kernel/memory.cpp";
patch($mem,
	"\t// Experiment 0035 tried committing such pages lazily (removed in cleanup batch 3): the AMM\n\t// failures seen were the fixed window reservation wiping the game's mappings, not pages it\n\t// expected to appear.\n\tEXIT(\"AMM virtual-memory unmap is unsupported: addr=0x%016\" PRIx64 \"\\n\", vaddr);\n\treturn false;\n",
	"\t// Experiment 0035 tried committing such pages lazily (removed in cleanup batch 3): the AMM\n\t// failures seen were the fixed window reservation wiping the game's mappings, not pages it\n\t// expected to appear.\n" .
	"\t// BC5 (experiment 0356): a page whose AMM map is submitted but not executed yet is waited for and the\n" .
	"\t// access retried; otherwise the ledger prints the page's history and the host gives up as before.\n" .
	"\tif (bc5_amm_fault(vaddr) != 0) {\n\t\treturn true;\n\t}\n" .
	"\tEXIT(\"AMM page not mapped at the access, no pending map covers it (was: AMM virtual-memory unmap is unsupported): addr=0x%016\" PRIx64 \"\\n\", vaddr);\n\treturn false;\n",

	"bool KernelHandleReservedRangeAccessViolation(uint64_t vaddr) {\n",
	"extern \"C\" int bc5_amm_fault(uint64_t vaddr); // libAmpr.cpp, BC5 (experiment 0356)\n\nbool KernelHandleReservedRangeAccessViolation(uint64_t vaddr) {\n",
);

my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	"\t\tif (::Log::Bc5LoggingOn() && BC5_DIAG_ENV(\"KYTY_BC5_AMM_TRACE\") != nullptr) {\n\t\t\tauto* rt   = Common::Singleton<Loader::RuntimeLinker>::Instance();\n",
	"\t\t{ // BC5 (experiment 0356): for every fault that reaches the reserved-range handler, not only with the trace\n\t\t\tauto* rt   = Common::Singleton<Loader::RuntimeLinker>::Instance();\n",
);
print "patch0356.pl: $marks edits\n";

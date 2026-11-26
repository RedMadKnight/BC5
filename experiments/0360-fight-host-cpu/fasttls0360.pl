#!/usr/bin/perl
# BC5 experiment 0360, candidate A: the fast path for the title's thread-pointer reads. Applied to a PRIVATE copy of
# src/loader/runtimeLinker.cpp (the shared tree's e37ed5cd).
# Every `mov reg, qword ptr fs:[0]` in the title's code is patched by the loader to `call <stub>` (Jit::Call9). The
# stub saves nine registers and the flags (Jit::SafeCall, with pushfq/popfq), calls TlsMainGetAddr through an
# indirect call, and restores everything. TlsMainGetAddr then returns the thread's cached TCB, a host thread_local
# (g_tls_cached_main_tcb). The M1 sampler put TlsMainGetAddr alone at 54 % of game-main's samples in the emulator's
# code; the trampoline around it runs in guest memory and was counted as title code.
# The candidate writes, per register (rax, rcx, rdx, rbx, rbp, rsi, rdi), a stub at handler_vaddr + 0x400 + reg * 32:
#     mov reg, qword ptr fs:[D]   ; D = &g_tls_cached_main_tcb - the thread pointer, the same in every thread
#                                 ;     (static TLS of the executable; the x86-64 TLS ABI puts the thread pointer at fs:0)
#     test reg, reg
#     jz slow
#     ret
#   slow:
#     jmp <the existing stub of that register>   ; SafeCall / TlsRegStub, which fill the cache (the first access)
# and points the patched call sites at it. The flags and the return address slot below rsp are clobbered exactly as
# on the existing path (SafeCall ends with `add rsp, 0x80` after its popfq). If D does not fit 32 bits the stubs
# are bare jumps to the existing ones. BC5_0360_FAST_TLS=0 keeps the original call sites.
# usage: fasttls0360.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: fasttls0360.pl <src root>\n" unless defined $root;
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
	open(my $o, ">", $file) or die "$file: $!\n";
	print $o $s;
	close $o;
}
my $rtl = "$root/src/loader/runtimeLinker.cpp";

my $helper_old = <<'EOF';
static KYTY_MS_ABI uint8_t* TlsMainGetAddr() {
EOF
my $helper_new = <<'EOF';
// BC5 (experiment 0360, candidate A): the fast stubs for the title's fs:[0] reads (fasttls0360.pl's header).
static bool Bc5FastTlsOn() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0360_FAST_TLS");
		return !(e != nullptr && std::strcmp(e, "0") == 0);
	}();
	return on;
}
static uint64_t Bc5FastTlsOffset(uint32_t reg) {
	return 0x400u + static_cast<uint64_t>(reg) * 32u;
}
static bool Bc5FastTlsDisp(int32_t* disp) {
	uint64_t tp = 0;
	asm volatile("mov %%fs:0, %0" : "=r"(tp));
	const int64_t d = static_cast<int64_t>(reinterpret_cast<uintptr_t>(&g_tls_cached_main_tcb)) - static_cast<int64_t>(tp);
	if (tp == 0 || d < INT32_MIN || d > INT32_MAX) return false;
	*disp = static_cast<int32_t>(d);
	return true;
}

static KYTY_MS_ABI uint8_t* TlsMainGetAddr() {
EOF

my $site_old = <<'EOF';
				code->SetFunc(reg == 0
				                  ? program->tls.handler_vaddr
				                  : program->tls.handler_vaddr + Jit::TlsRegStub::GetOffset(reg));
EOF
my $site_new = <<'EOF';
				code->SetFunc(Bc5FastTlsOn() ? program->tls.handler_vaddr + Bc5FastTlsOffset(reg) // experiment 0360, candidate A
				              : reg == 0     ? program->tls.handler_vaddr
				                             : program->tls.handler_vaddr + Jit::TlsRegStub::GetOffset(reg));
EOF

my $stub_old = <<'EOF';
		stub->SetFunc(program->tls.handler_vaddr);
		stub->SetOutputReg(reg);
	}

	EXIT_IF(!Libs::LibKernel::Memory::ProtectGuestMemory(program->tls.handler_vaddr,
EOF
my $stub_new = <<'EOF';
		stub->SetFunc(program->tls.handler_vaddr);
		stub->SetOutputReg(reg);
	}

	// BC5 (experiment 0360, candidate A): the fast stubs, after the existing ones in the same page.
	if (Bc5FastTlsOn()) {
		int32_t    disp = 0;
		const bool ok   = Bc5FastTlsDisp(&disp);
		EXIT_IF(Jit::SafeCall::GetSize() < Bc5FastTlsOffset(8)); // the handler page holds the fast stubs
		for (uint32_t reg = 0; reg < 8; reg++) {
			if (reg == 4) {
				continue;
			}
			auto*          p    = reinterpret_cast<uint8_t*>(program->tls.handler_vaddr + Bc5FastTlsOffset(reg));
			const uint64_t slow = reg == 0 ? program->tls.handler_vaddr : program->tls.handler_vaddr + Jit::TlsRegStub::GetOffset(reg);
			size_t         n    = 0;
			if (ok) {
				const uint8_t mov[5] = {0x64, 0x48, 0x8B, static_cast<uint8_t>(0x04u | (reg << 3u)), 0x25}; // mov reg, qword ptr fs:[disp32]
				std::memcpy(p + n, mov, sizeof(mov));
				n += sizeof(mov);
				std::memcpy(p + n, &disp, sizeof(disp));
				n += sizeof(disp);
				p[n++] = 0x48; // test reg, reg
				p[n++] = 0x85;
				p[n++] = static_cast<uint8_t>(0xC0u | (reg << 3u) | reg);
				p[n++] = 0x74; // jz +1 (the ret)
				p[n++] = 0x01;
				p[n++] = 0xC3; // ret
			}
			p[n++]          = 0xE9; // jmp the existing stub (fills the cache)
			const auto rel  = static_cast<int32_t>(static_cast<int64_t>(slow) - static_cast<int64_t>(reinterpret_cast<uint64_t>(p + n + 4)));
			std::memcpy(p + n, &rel, sizeof(rel));
		}
		LOGF("[bc5] experiment 0360: fast TLS stubs %s, fs displacement %d\n", ok ? "on" : "FALLBACK to the original stubs (displacement out of range)", disp);
	}

	EXIT_IF(!Libs::LibKernel::Memory::ProtectGuestMemory(program->tls.handler_vaddr,
EOF

patch($rtl, $helper_old, $helper_new, $site_old, $site_new, $stub_old, $stub_new);
print "fasttls0360.pl: $marks edits\n";

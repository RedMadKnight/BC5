#!/usr/bin/perl
# BC5 experiment 0360, candidate B: one TSC read per clock call. Applied to a PRIVATE copy of src/kernel/pthread.cpp
# (the shared tree's 46c7ac3a, CRLF; the anchors are converted).
# KernelGetProcessTimeCounter (KernelGetElapsedTsc) and KernelReadTsc read the TSC, then exp 0166's KernelPausedTsc
# reads it a second time to take off the window's pause. The M1 sampler put KernelGetProcessTimeCounter at 36 % of
# game-main's samples in the emulator's code (~4 % of its CPU). With one read, the same `now` serves both; the pause
# arithmetic is unchanged. BC5_0360_ONE_TSC=0 keeps the two reads.
# usage: onetsc0360.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: onetsc0360.pl <src root>\n" unless defined $root;
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
my $pt = "$root/src/kernel/pthread.cpp";

my $el_old = <<'EOF';
static uint64_t KernelGetElapsedTsc() {
	const auto initial_tsc = KernelGetInitialTsc();
	const auto current_tsc = KernelReadTscNative() - KernelPausedTsc(); // BC5 (experiment 0166)
	return current_tsc >= initial_tsc ? current_tsc - initial_tsc : 0;
}
EOF
my $el_new = <<'EOF';
// BC5 (experiment 0360, candidate B): the paused ticks at a TSC value already read, so a clock call reads the TSC once.
static uint64_t KernelPausedTscAt(uint64_t now) {
	const uint64_t start = g_pause_tsc_start.load(std::memory_order_acquire);
	return g_pause_tsc_total.load(std::memory_order_acquire) + (start != 0 && now > start ? now - start : 0);
}
static bool Bc5OneTsc() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0360_ONE_TSC");
		return !(e != nullptr && std::strcmp(e, "0") == 0);
	}();
	return on;
}
static uint64_t KernelGetElapsedTsc() {
	const auto     initial_tsc = KernelGetInitialTsc();
	const uint64_t now         = KernelReadTscNative();
	const auto     current_tsc = now - (Bc5OneTsc() ? KernelPausedTscAt(now) : KernelPausedTsc()); // BC5 (experiments 0166, 0360)
	return current_tsc >= initial_tsc ? current_tsc - initial_tsc : 0;
}
EOF

my $rd_old = <<'EOF';
uint64_t KYTY_SYSV_ABI KernelReadTsc() {
	return KernelReadTscNative() - KernelPausedTsc(); // BC5 (experiment 0166)
}
EOF
my $rd_new = <<'EOF';
uint64_t KYTY_SYSV_ABI KernelReadTsc() {
	const uint64_t now = KernelReadTscNative();
	return now - (Bc5OneTsc() ? KernelPausedTscAt(now) : KernelPausedTsc()); // BC5 (experiments 0166, 0360)
}
EOF

patch($pt, $el_old, $el_new, $rd_old, $rd_new);
print "onetsc0360.pl: $marks edits\n";

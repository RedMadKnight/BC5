#!/usr/bin/perl
# BC5 experiment 0344: which packet of a timeout dump sits at the CP's fetch point of the job IB the GPU ran.
# Reads a BC5_DIRECT_TIMEOUT_PROBE dump (ib-timeout-<n>-<kind>-<dwords>.bin: the buffer the host handed to the
# backend, little-endian dwords, before the backend's passes) and replays the SIZE effect of the passes
# Device::submit runs on a GFX-ring job as exp 0342's launcher configures them (backend/src/direct.cpp at main
# d0c2668; BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_DMA_SYNC=1 BC5_DIRECT_GPU_CHECK_PRODUCT=1
# BC5_DIRECT_SHADOW_LABELS=1, no CU mask, no job timestamps, no prologue, no epilogue, DMA idle at the end):
#   policy::filter         in place (a compute-form DISPATCH_INDIRECT, 4 dwords, becomes the GFX form, 3 + a NOP;
#                          a dispatch whose address high dword differs from the IB's base is dropped, unchecked)
#   shadow_labels::apply   a copy of each writer (RELEASE_MEM with data, WRITE_DATA to memory) of a label that a
#                          WAIT_REG_MEM[64] on memory waits on after a writer, inserted right before the writer
#   DMA syncs              7 dwords before the first dispatch after a DMA_DATA without CP_SYNC (dword 1 bit 31 clear)
#   indirect_check::apply  before each GFX-form DISPATCH_INDIRECT with a base: the CP check with the product staircase,
#                          88 dwords (5 + 5 + 3 x 9 + 2 x 9 + 5 + 2 + 5 + 9 + 5 + 2 + 5); DRAW_[INDEX_]INDIRECT 35;
#                          unbased: a PFP_SYNC_ME, 2
#   dma_idle               7 dwords at the end; the IB padded to 8 dwords (the CS's size)
# Only packet headers, offsets, counts, opcodes, program and argument addresses are printed; no dwords of the
# buffer leave it. Nothing is written. GPL-2.0.
# usage: ibmap0344.pl <dump.bin> <ib dwords as the CS saw it> <CP_IB1_BUFSZ dwords> [known programs file]
use strict;
use warnings;

my ($file, $cs_size, $bufsz, $known_file) = @ARGV;
die "usage: ibmap0344.pl <dump.bin> <ib dwords> <CP_IB1_BUFSZ dwords> [known programs]\n" unless defined $bufsz;
open(my $h, '<', $file) or die "$file: $!\n";
binmode $h;
local $/;
my $raw = <$h>;
close $h;
my @ib = unpack('V*', $raw);
my $n  = scalar @ib;
printf "dump %s: %u dwords (%u bytes)\n", $file, $n, length $raw;

my %known;
if (defined $known_file && open(my $k, '<', $known_file)) {
	while (<$k>) { next unless /^\s*(0x[0-9a-f]+)\s+(.*\S)/i; $known{lc $1} = $2; }
	close $k;
}

# ---- pass 0: the packets of the dump, with the SH register shadow for the program of each dispatch
sub plen { my ($hd) = @_; my $t = $hd >> 30; return 1 unless $t == 3 || $t == 0; my $c = ($hd >> 16) & 0x3fff; return $c == 0x3fff ? 1 : $c + 2; }
my @pk;            # [q, len, type, op]
my %sh;            # SH offset -> value (SET_SH_REG only; tables in memory are not read here)
my @disp;          # dispatches: [q, len, form, pgm, args_lo, args_hi]
my %mec_hi;        # address high dword -> count, of compute-form dispatches
my @ibp;           # INDIRECT_BUFFER packets: [q, target size]
my @cond;          # COND_EXEC: [q, count]
my (@writers, @waits); # [q, len, label]
for (my $q = 0; $q < $n;) {
	my $hd = $ib[$q]; my $t = $hd >> 30; my $len = plen($hd);
	$len = $n - $q if $q + $len > $n;
	my $op = $t == 3 ? ($hd >> 8) & 0xff : -1;
	push @pk, [$q, $len, $t, $op];
	if ($t == 3) {
		if (($op == 0x76 || $op == 0x9b) && $len >= 3) { # SET_SH_REG[_INDEX]
			my $first = $ib[$q + 1] & 0xffff;
			for (my $i = 0; $i + 2 < $len; $i++) { $sh{$first + $i} = $ib[$q + 2 + $i]; }
		} elsif ($op == 0x15 && $len >= 4) {
			my $pgm = exists $sh{0x20c} ? (($sh{0x20c} | ((($sh{0x20d} // 0) & 0xff) << 32)) << 8) : -1;
			push @disp, [$q, $len, 'direct', $pgm, 0, 0];
		} elsif ($op == 0x16 && $len >= 3) {
			my $pgm = exists $sh{0x20c} ? (($sh{0x20c} | ((($sh{0x20d} // 0) & 0xff) << 32)) << 8) : -1;
			my ($lo, $hi) = ($ib[$q + 1], $len >= 4 ? ($ib[$q + 2] & 0xffff) : -1);
			$mec_hi{$hi}++ if $len == 4;
			push @disp, [$q, $len, $len == 4 ? 'mec' : 'gfx', $pgm, $lo, $hi];
		} elsif (($op == 0x3f || $op == 0x33) && $len >= 4) {
			push @ibp, [$q, $ib[$q + 3] & 0xfffff];
		} elsif ($op == 0x22 && $len >= 5) {
			push @cond, [$q, $ib[$q + 4] & 0x3fff];
		} elsif ($op == 0x49 && $len >= 6 && (($ib[$q + 2] >> 29) & 7) != 0) { # RELEASE_MEM with data
			push @writers, [$q, $len, ($ib[$q + 3] & ~3) | (($ib[$q + 4] & 0xffff) << 32)];
		} elsif ($op == 0x37 && $len >= 5) {                                   # WRITE_DATA to memory
			my $dst = ($ib[$q + 1] >> 8) & 0xf;
			push @writers, [$q, $len, ($ib[$q + 2] & ~3) | (($ib[$q + 3] & 0xffff) << 32)] if $dst == 1 || $dst == 2 || $dst == 5;
		} elsif (($op == 0x3c || $op == 0x93) && $len >= 7 && (($ib[$q + 1] >> 4) & 1)) { # WAIT_REG_MEM[64] on memory
			push @waits, [$q, $len, ($ib[$q + 2] & ~3) | (($ib[$q + 3] & 0xffff) << 32)];
		}
	}
	$q += $len;
}
my %ops; $ops{$_->[3]}++ for grep { $_->[2] == 3 } @pk;
printf "packets %u (type-3 %u); opcodes:%s\n", scalar @pk, scalar(grep { $_->[2] == 3 } @pk),
	join('', map { sprintf ' %02x:%u', $_, $ops{$_} } sort { $a <=> $b } keys %ops);
printf "dispatches %u: direct %u, indirect compute-form %u, indirect gfx-form %u; INDIRECT_BUFFER packets %u%s; COND_EXEC %u\n",
	scalar @disp, scalar(grep { $_->[2] eq 'direct' } @disp), scalar(grep { $_->[2] eq 'mec' } @disp), scalar(grep { $_->[2] eq 'gfx' } @disp),
	scalar @ibp, @ibp ? ' (target sizes ' . join(' ', map { $_->[1] } @ibp) . ' dwords)' : '', scalar @cond;
my $base_hi = -1;
if (%mec_hi) {
	($base_hi) = sort { $mec_hi{$b} <=> $mec_hi{$a} } keys %mec_hi;
	printf "compute-form address high dwords:%s -> the IB's base 0x%x (the others are dropped, unchecked)\n",
		join('', map { sprintf ' 0x%x:%u', $_, $mec_hi{$_} } sort keys %mec_hi), $base_hi;
}

# ---- pass 1: the shadow labels (the labels a writer precedes, in order of first wait; 64 slots)
my (%label_slot, @copies);
my @labels;
for my $w (@waits) {
	next if exists $label_slot{$w->[2]};
	my $written = grep { $_->[2] == $w->[2] && $_->[0] < $w->[0] } @writers;
	next unless $written;
	next if @labels >= 64;
	push @labels, $w->[2];
	$label_slot{$w->[2]} = $#labels;
}
for my $wr (@writers) { push @copies, [$wr->[0], $wr->[1]] if exists $label_slot{$wr->[2]}; }
printf "shadow labels: %u writers, %u memory waits, %u labels get a slot, %u writer copies (%u dwords)\n",
	scalar @writers, scalar @waits, scalar @labels, scalar @copies, eval { my $s = 0; $s += $_->[1] for @copies; $s };

# ---- pass 2: the inserts, anchored at the packet they precede (shadow copies, then DMA syncs, then the checks)
my %ins; # q -> dwords inserted before the packet at q
$ins{$_->[0]} += $_->[1] for @copies;
my ($pending, $dma_syncs, $checks, $unbased, $dropped) = (0, 0, 0, 0, 0);
for my $p (@pk) {
	my ($q, $len, $t, $op) = @$p;
	next unless $t == 3;
	if ($op == 0x50 && $len >= 2) { $pending = ($ib[$q + 1] & 0x80000000) == 0 ? 1 : 0; next; }
	next unless $op == 0x15 || $op == 0x16 || $op == 0x24 || $op == 0x25;
	my $is_mec = $op == 0x16 && $len == 4;
	if ($is_mec && ($ib[$q + 2] & 0xffff) != $base_hi) { $dropped++; next; } # the filter drops it: no sync, no check
	if ($pending) { $ins{$q} += 7; $dma_syncs++; $pending = 0; }
	if ($op == 0x16 && ($is_mec || $len == 3)) { $ins{$q} += 88; $checks++; }       # based: the IB's base
	elsif (($op == 0x24 || $op == 0x25) && $len == 5) { $ins{$q} += 35; $checks++; }
}
my $inserted = 0; $inserted += $_ for values %ins;
my $main_n  = $n + $inserted + 7;
my $padded  = ($main_n + 7) & ~7;
printf "inserts: %u DMA syncs (7), %u checks (88 per dispatch, 35 per draw), %u compute-form dispatches dropped; DMA idle 7 at the end\n", $dma_syncs, $checks, $dropped;
printf "job IB computed: %u + %u inserted + 7 = %u dwords, padded %u; the CS saw %u (%s)\n", $n, $inserted, $main_n, $padded, $cs_size,
	$padded == $cs_size ? 'EQUAL' : sprintf('DIFFERENT by %d: a pass is not replayed here as it ran (tables, drops, the tracker)', $cs_size - $padded);

# ---- pass 3: old offset -> new offset, and the packet at the fetch point
my %new_at;
{
	my $shift = 0;
	for my $p (@pk) { my $q = $p->[0]; $shift += $ins{$q} // 0; $new_at{$q} = $q + $shift; }
}
sub packet_at { # the dump packet (or the insert before it) holding new offset $x
	my ($x) = @_;
	my $prev;
	for my $p (@pk) {
		my ($q, $len) = @$p;
		my $start = $new_at{$q} - ($ins{$q} // 0);
		return ($p, $x < $new_at{$q} ? 'inside the inserts before it' : 'inside the packet') if $x >= $start && $x < $new_at{$q} + $len;
		$prev = $p;
	}
	return ($prev, 'past the last packet (the DMA idle or the padding)');
}
sub describe {
	my ($x, $what) = @_;
	my ($p, $where) = packet_at($x);
	my ($q, $len, $t, $op) = @$p;
	my $k = -1;
	for my $i (0 .. $#disp) { $k = $i if $disp[$i][0] <= $q; }
	printf "%s: job dword %u -> dump packet at %u (len %u, op %02x), %s; the last dispatch at or before it is #%d of %u\n",
		$what, $x, $q, $len, $t == 3 ? $op : -1, $where, $k, scalar @disp;
	return $k;
}
my $fetched = $cs_size - $bufsz;
printf "fetch point: CS size %u, CP_IB1_BUFSZ %u -> %u fetched (%.1f %%) if BUFSZ is what is left, %u if BUFSZ is what was fetched\n",
	$cs_size, $bufsz, $fetched, 100 * $fetched / $cs_size, $bufsz;
my $k1 = describe($fetched, 'left reading');
my $k2 = describe($bufsz, 'fetched reading');

# ---- the dispatches around the point, with their programs (SET_SH_REG only) and argument addresses
sub pgm_name { my ($pgm) = @_; return 'not set by SET_SH_REG in this buffer' if $pgm < 0; my $s = sprintf('0x%x', $pgm); return $s . (exists $known{$s} ? " [$known{$s}]" : ''); }
my %want;
for my $k ($k1, $k2) { next if $k < 0; $want{$_} = 1 for grep { $_ >= 0 && $_ <= $#disp } ($k - 3 .. $k + 3); }
print "dispatches around the point (index: dump offset -> job offset, form, program, arguments):\n";
for my $i (sort { $a <=> $b } keys %want) {
	my ($q, $len, $form, $pgm, $lo, $hi) = @{$disp[$i]};
	my $args = $form eq 'mec' ? sprintf('arguments at 0x%x', ($lo & ~3) | ($hi << 32)) : $form eq 'gfx' ? sprintf('offset 0x%x from the base', $lo) : 'direct';
	my $mark = ($i == $k1 ? ' <- left reading' : '') . ($i == $k2 ? ' <- fetched reading' : '');
	printf "  #%d: %u -> %u, %s, program %s, %s%s\n", $i, $q, $new_at{$q}, $form, pgm_name($pgm), $args, $mark;
}
my %pgms; $pgms{$_->[3]}++ for @disp;
print "programs of the buffer (dispatches each):\n";
printf "  %s: %u\n", pgm_name($_), $pgms{$_} for sort { $pgms{$b} <=> $pgms{$a} } keys %pgms;

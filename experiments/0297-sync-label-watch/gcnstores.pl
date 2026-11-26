#!/usr/bin/perl
# BC5 experiment 0297: a store/load scanner for gfx10 (RDNA 1) shader dumps, for a laptop without llvm-mc.
# It walks the instruction stream with the encodings' lengths and prints the memory stores (MUBUF, MTBUF,
# FLAT/GLOBAL/SCRATCH, MIMG store, SMEM store), the SMEM loads that fill the scalar registers those stores use,
# and the MUBUF/FLAT loads, so that each store's address source (a V# in s[4k:4k+3], a 64-bit SADDR pair, or a
# VGPR-only address) and its origin (which s_load from which base pair) can be read.
# Encodings and opcode numbers: LLVM llvm/lib/Target/AMDGPU — SIInstrFormats.td (the format bits), BUFInstructions.td
# (MUBUF_Real_gfx10 opcodes), FLATInstructions.td (FLAT_Real_gfx10, SEG 0 flat / 1 scratch / 2 global), SMInstructions.td
# (SMEM gfx10), MIMGInstructions.td (MIMGe_gfx10; op bit 7 in Inst{0}, NSA extra dwords in Inst{2:1}). TODO(verify): the
# opcode tables below were written from memory of those files and should be checked against the tree before any number
# here is cited as fact; the structural output (which SGPRs a store goes through) does not depend on exact opcode names.
# usage: gcnstores.pl <dump.bin> [max dwords]
use strict; use warnings;
my ($f, $maxdw) = @ARGV; $maxdw ||= 16384;
open(my $fh, '<:raw', $f) or die "$f: $!"; local $/; my $d = <$fh>; close $fh;
my @w = unpack('V*', $d); $#w = $maxdw - 1 if @w > $maxdw;
my %mubuf = (0x00=>'buffer_load_format_x',0x01=>'buffer_load_format_xy',0x02=>'buffer_load_format_xyz',0x03=>'buffer_load_format_xyzw',
             0x04=>'buffer_store_format_x',0x05=>'buffer_store_format_xy',0x06=>'buffer_store_format_xyz',0x07=>'buffer_store_format_xyzw',
             0x08=>'buffer_load_ubyte',0x09=>'buffer_load_sbyte',0x0a=>'buffer_load_ushort',0x0b=>'buffer_load_sshort',
             0x0c=>'buffer_load_dword',0x0d=>'buffer_load_dwordx2',0x0e=>'buffer_load_dwordx4',0x0f=>'buffer_load_dwordx3',
             0x18=>'buffer_store_byte',0x19=>'buffer_store_byte_d16_hi',0x1a=>'buffer_store_short',0x1b=>'buffer_store_short_d16_hi',
             0x1c=>'buffer_store_dword',0x1d=>'buffer_store_dwordx2',0x1e=>'buffer_store_dwordx4',0x1f=>'buffer_store_dwordx3');
my %flat  = (0x08=>'load_ubyte',0x09=>'load_sbyte',0x0a=>'load_ushort',0x0b=>'load_sshort',0x0c=>'load_dword',0x0d=>'load_dwordx2',
             0x0e=>'load_dwordx4',0x0f=>'load_dwordx3',0x18=>'store_byte',0x19=>'store_byte_d16_hi',0x1a=>'store_short',
             0x1b=>'store_short_d16_hi',0x1c=>'store_dword',0x1d=>'store_dwordx2',0x1e=>'store_dwordx4',0x1f=>'store_dwordx3');
my %smem  = (0x00=>'s_load_dword',0x01=>'s_load_dwordx2',0x02=>'s_load_dwordx4',0x03=>'s_load_dwordx8',0x04=>'s_load_dwordx16',
             0x08=>'s_buffer_load_dword',0x09=>'s_buffer_load_dwordx2',0x0a=>'s_buffer_load_dwordx4',0x0b=>'s_buffer_load_dwordx8',
             0x0c=>'s_buffer_load_dwordx16',0x10=>'s_store_dword',0x11=>'s_store_dwordx2',0x12=>'s_store_dwordx4',
             0x18=>'s_buffer_store_dword',0x19=>'s_buffer_store_dwordx2',0x1a=>'s_buffer_store_dwordx4');
my @seg = ('flat', 'scratch', 'global', 'seg3');
my ($i, $n, %stat) = (0, 0);
my $end = $#w;
for my $k (0..$#w) { if ($w[$k] == 0xbf9f0000) { $end = $k; last } if ($w[$k] == 0xbf810000 && $k + 4 <= $#w && !$w[$k+1] && !$w[$k+2] && !$w[$k+3] && !$w[$k+4]) { $end = $k; last } }
printf "%s: program %d dwords (to s_code_end / s_endpgm+pad)\n", $f, $end + 1;
while ($i <= $end) {
    my $d0 = $w[$i]; my $len = 1; my $top6 = $d0 >> 26; my $top7 = $d0 >> 25; my $top9 = $d0 >> 23;
    my $off = $i * 4;
    if ($top6 == 0x3d) {                      # SMEM, 64-bit
        $len = 2; my $d1 = $w[$i+1] // 0;
        my $op = ($d0 >> 18) & 0xff; my $sbase = ($d0 & 0x3f) * 2; my $sdata = ($d0 >> 6) & 0x7f; my $imm = $d1 & 0x1fffff; my $soff = $d1 >> 25;
        my $name = $smem{$op} // sprintf('smem_op%02x', $op);
        my $kind = $name =~ /store/ ? 'SSTORE' : 'sload';
        $stat{$kind}++;
        printf "%06x %-8s %-24s sdata s%-3d base s[%d:%d]%s off 0x%x%s\n", $off, $kind, $name, $sdata, $sbase, $sbase+ ($name =~ /buffer/ ? 3 : 1), ($name =~ /buffer/ ? ' (V#)' : ''), $imm, ($soff != 0x7d ? " + s$soff" : '');
    } elsif ($top6 == 0x38 || $top6 == 0x3a) { # MUBUF / MTBUF, 64-bit
        $len = 2; my $d1 = $w[$i+1] // 0;
        my $op = $top6 == 0x38 ? (($d0 >> 18) & 0x7f) : (($d0 >> 15) & 0x7) | ((($d0 >> 26) & 0) );
        my $name = $top6 == 0x38 ? ($mubuf{$op} // sprintf('mubuf_op%02x', $op)) : 'tbuffer_op';
        my $srsrc = (($d1 >> 16) & 0x1f) * 4; my $soffset = ($d1 >> 24) & 0xff; my $vaddr = $d1 & 0xff; my $vdata = ($d1 >> 8) & 0xff;
        my $idxen = ($d0 >> 13) & 1; my $offen = ($d0 >> 12) & 1; my $imm = $d0 & 0xfff;
        my $kind = $name =~ /store/ ? 'STORE' : ($name =~ /load/ ? 'load' : 'buf');
        $kind = 'ATOMIC' if $top6 == 0x38 && $op >= 0x30;
        $stat{$kind}++;
        printf "%06x %-8s %-24s V# s[%d:%d] vaddr v%d%s%s off 0x%x soff %s vdata v%d\n", $off, $kind, $name, $srsrc, $srsrc+3, $vaddr, ($idxen ? ' idxen' : ''), ($offen ? ' offen' : ''), $imm, ($soffset >= 128 ? sprintf('%d', $soffset - 128) : "s$soffset"), $vdata;
    } elsif ($top6 == 0x37) {                 # FLAT / GLOBAL / SCRATCH, 64-bit
        $len = 2; my $d1 = $w[$i+1] // 0;
        my $op = ($d0 >> 18) & 0x7f; my $sg = ($d0 >> 14) & 3; my $saddr = ($d1 >> 16) & 0x7f; my $addr = $d1 & 0xff; my $data = ($d1 >> 8) & 0xff;
        my $imm = $d0 & 0xfff; $imm -= 0x1000 if $sg && ($imm & 0x800);
        my $name = $seg[$sg] . '_' . ($flat{$op} // sprintf('op%02x', $op));
        my $kind = $name =~ /store/ ? 'STORE' : ($name =~ /load/ ? 'load' : ($op >= 0x30 ? 'ATOMIC' : 'flat'));
        $stat{$kind}++;
        printf "%06x %-8s %-24s %s off %d data v%d\n", $off, $kind, $name, ($saddr != 0x7f ? sprintf('saddr s[%d:%d] + v%d', $saddr, $saddr+1, $addr) : sprintf('addr v[%d:%d] (VGPR-only 64-bit address)', $addr, $addr+1)), $imm, $data;
    } elsif ($top6 == 0x3c) {                 # MIMG, 64-bit + NSA dwords
        my $nsa = ($d0 >> 1) & 3; $len = 2 + $nsa; my $d1 = $w[$i+1] // 0;
        my $op = (($d0 >> 18) & 0x7f) | (($d0 & 1) << 7); my $srsrc = (($d1 >> 16) & 0x1f) * 4; my $ssamp = (($d1 >> 21) & 0x1f) * 4;
        my $name = ($op >= 0x08 && $op <= 0x0b) ? 'image_store*' : ($op == 0xe6 ? 'image_bvh_intersect_ray' : $op == 0xe7 ? 'image_bvh64_intersect_ray' : ($op >= 0x10 && $op <= 0x1f ? 'image_atomic*' : sprintf('mimg_op%02x', $op)));
        my $kind = $name =~ /store|atomic/ ? 'STORE' : 'mimg';
        $stat{$kind}++;
        printf "%06x %-8s %-24s T# s[%d:%d]%s\n", $off, $kind, $name, $srsrc, $srsrc+7, ($op == 0xe6 || $op == 0xe7 ? ' (BVH descriptor s[' . $srsrc . ':' . ($srsrc+3) . '])' : '');
    } elsif ($top6 == 0x36) { $len = 2; $stat{ds}++;            # DS (LDS/GDS), 64-bit
    } elsif ($top6 == 0x3e) { $len = 2; $stat{exp}++;           # EXP
    } elsif ($top6 == 0x35) {                                   # VOP3, 64-bit, + literal when a source is 255
        $len = 2; my $d1 = $w[$i+1] // 0; my $s0 = $d1 & 0x1ff; my $s1 = ($d1 >> 9) & 0x1ff; my $s2 = ($d1 >> 18) & 0x1ff;
        $len = 3 if $s0 == 255 || $s1 == 255 || $s2 == 255; $stat{vop3}++;
    } elsif ($top6 == 0x33) { $len = 2; my $d1 = $w[$i+1] // 0; $len = 3 if (($d1 & 0x1ff) == 255 || (($d1 >> 9) & 0x1ff) == 255 || (($d1 >> 18) & 0x1ff) == 255); $stat{vop3p}++; # VOP3P
    } elsif ($top6 == 0x32) { $len = 1; $stat{vintrp}++;        # VINTRP
    } elsif (($d0 >> 31) == 0) {                                # VOP2
        my $s0 = $d0 & 0x1ff; $len = ($s0 == 255 || $s0 == 0xf9 || $s0 == 0xfa) ? 2 : 1; my $op = ($d0 >> 25) & 0x3f;
        $len = 2 if ($op == 0x2c || $op == 0x2d || $op == 0x2f || $op == 0x37 || $op == 0x38) && $len == 1; # v_fmamk/fmaak/madmk/madak/pk_fmac carry a literal
        $stat{vop2}++;
    } elsif ($top7 == 0x3f) {                                   # VOP1
        my $s0 = $d0 & 0x1ff; $len = ($s0 == 255 || $s0 == 0xf9 || $s0 == 0xfa) ? 2 : 1; $stat{vop1}++;
    } elsif ($top7 == 0x3e) {                                   # VOPC
        my $s0 = $d0 & 0x1ff; $len = ($s0 == 255 || $s0 == 0xf9 || $s0 == 0xfa) ? 2 : 1; $stat{vopc}++;
    } elsif ($top9 == 0x17d) {                                  # SOP1 (1011 1110 1)
        my $s0 = $d0 & 0xff; $len = $s0 == 255 ? 2 : 1; $stat{sop1}++;
    } elsif ($top9 == 0x17e) {                                  # SOPC (1011 1111 0)
        $len = (($d0 & 0xff) == 255 || (($d0 >> 8) & 0xff) == 255) ? 2 : 1; $stat{sopc}++;
    } elsif ($top9 == 0x17f) {                                  # SOPP (1011 1111 1)
        $len = 1; $stat{sopp}++;
        my $op = ($d0 >> 16) & 0x7f; printf "%06x %-8s s_endpgm\n", $off, 'end' if $op == 1;
    } elsif (($d0 >> 28) == 0xb) {                              # SOPK (1011 0xxx)
        $len = 1; $stat{sopk}++;
    } elsif (($d0 >> 30) == 2) {                                # SOP2 (10xx)
        $len = (($d0 & 0xff) == 255 || (($d0 >> 8) & 0xff) == 255) ? 2 : 1; $stat{sop2}++;
    } else { $stat{unknown}++; printf "%06x %-8s 0x%08x\n", $off, '???', $d0; }
    $i += $len; $n++;
}
printf "summary: %d instructions; %s\n", $n, join(', ', map { "$_ $stat{$_}" } sort keys %stat);

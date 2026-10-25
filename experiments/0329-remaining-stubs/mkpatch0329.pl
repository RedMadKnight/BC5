# patch0329.py = patch0328.py (exp 0327's seven files + 0328's libs.cpp) with the edits of frag0329.txt: APPEND adds
# edits to an existing file's block, REPLACE swaps a block, NEWBLOCKS go before runtimeLinker.cpp's block.
use strict; use warnings;
my ($src, $frag, $out) = @ARGV;
open(my $h, '<', $src) or die; my $t = do { local $/; <$h> }; close $h;
open(my $g, '<', $frag) or die; my $f = do { local $/; <$g> }; close $g;
my @sections = split(/^## (APPEND|REPLACE|NEWBLOCKS) ?(\S*)\n/m, $f);
shift @sections;  # text before the first marker (empty)
while (@sections) {
	my ($kind, $rel, $body) = splice(@sections, 0, 3);
	if ($kind eq 'APPEND') {
		my $head = "    '$rel': [\n";
		my $i = index($t, $head); die "no block for $rel" if $i < 0;
		my $j = index($t, "\n    ],\n", $i); die "no end of block $rel" if $j < 0;
		substr($t, $j + 1, 0) = $body;
	} elsif ($kind eq 'REPLACE') {
		my $head = "    '$rel': [\n";
		my $i = index($t, $head); die "no block for $rel" if $i < 0;
		my $j = index($t, "\n    ],\n", $i); die "no end of block $rel" if $j < 0;
		substr($t, $i, $j + length("\n    ],\n") - $i) = $body;
	} else {
		my $anchor = "    'src/loader/runtimeLinker.cpp': [\n";
		my $i = index($t, $anchor); die "no runtimeLinker block" if $i < 0;
		substr($t, $i, 0) = $body;
	}
}
# the header: everything before "EDITS = {" is rewritten
my $k = index($t, "EDITS = {\n"); die "no EDITS" if $k < 0;
my $header = <<'H';
#!/usr/bin/env python3
# BC5 experiment 0329: the second title's remaining 61 missing imports (exp 0328's link-time list), implemented the way
# the console behaves (no return-0 stubs), on top of exp 0327's twelve and exp 0328's NpCppWebApi port, in the tree
# ~/src/KytyPlus (f266548 + patch 0001) as the box has it. The EDITS of patch0328.py are kept as they were (the seven
# files of 0327, the libs.cpp registration of 0328) and these are added — see the README's table for the function list:
#   src/libs/libKernel.cpp             posix sleep, fsync, fcntl (variadic), shutdown; libkernel signal (the disposition
#       table), rmdir, sceKernelInternalMemoryGetModuleSegmentInfo (the main program's first segment); sceKernelFsync
#       made real; the five coredump calls (outside a handler: the console's NOT_IN_COREDUMP_HANDLER); sceKernelMlock's NID
#   src/kernel/fileSystem.{h,cpp}      KernelFsync (fflush + fsync(2) on the host file), KernelFcntl (FD_CLOEXEC, the
#       status flags, O_APPEND), a close_on_exec flag on the descriptor
#   src/kernel/memory.{h,cpp}          KernelMlock: the range checked against the virtual ranges, mlock(2) on the host
#   src/libs/libC.cpp                  sceLibcInternalBacktraceForGame: the host's backtrace of the thread on stderr
#   src/libs/network.{h,cpp}           sceHttpReadData over the request's response body (a read position per request)
#   src/libs/libNet.cpp                sceNpGetAccountLanguage2 (signed out), NpSessionSignaling Terminate / Deactivate /
#       DestroyContext (state; no context exists), NpEntitlementAccessAbortRequest (the request registry), NpWebApi2's
#       four push-event calls (no sign-in: NOT_SIGNED_IN; DeleteFilter on the filters CreateFilter handed out)
#   src/libs/libSaveData.cpp           sceSaveDataGetConvertProgress (0.0: none runs), sceSaveDataCancel (none runs)
#   src/libs/audio.{h,cpp}, libAudio.cpp   sceAcmBatchJobPriority: a job recorded in the batch as the library's others
#   src/libs/controller.{h,cpp}, libPad.cpp scePadGetAccessibilityControllerState: handle / pointer checks, state 0
#   src/graphics/presentation/videoOut.{h,cpp}, src/libs/libVideoOut.cpp   WQHD detection, VRR peg / unpeg (recorded
#       on the port), the VideoOutVrrStatus library with AddVrrStatusFlagsPrivilege
#   src/libs/libs.cpp                  the new units registered: libPngEnc.cpp (a real PNG encoder over the vendored
#       zlib), libPlayGoDialog.cpp, libNpCommerceDialog.cpp, libPlayerInvitationDialog.cpp (copied in by build0329.sh and,
#       for the integration, added to the tree beside this patch — src/CMakeLists.txt globs libs/*.cpp)
# usage: patch0329.py <src root of the tree> <out dir>   (python3 on the box; the laptop applies it with apply0327.pl)
import difflib, hashlib, os, sys

H
substr($t, 0, $k) = $header;
$t =~ s/patch_0328\.diff/patch_0329.diff/g;
$t =~ s/usage: patch0328\.py/usage: patch0329.py/g;
open(my $o, '>', $out) or die; binmode $o; print $o $t; close $o;
my $n = () = $t =~ /^    '[^']+': \[$/mg; print "patch0329.py written: $n file blocks\n";

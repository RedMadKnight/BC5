#!/usr/bin/perl
# BC5 experiment 0342: the F2 overlay's left stick through its dead zone for the analog value too
# (src/graphics/presentation/settingsOverlay.cpp in ~/src/KytyPlus, the host tree of patch 0001). The overlay gave ImGui
# the stick's down state past a 0.25 dead zone but its analog value raw; ImGui 1.92's gamepad navigation scrolls the
# focused window by the left stick's analog value every frame (NavUpdate, "Manual scroll with LStick"), so a resting
# stick's drift scrolled lists by itself: the System tab's language list ran up while the maintainer chose (2026-10-27,
# F415). The analog value is now 0 inside the dead zone and rescaled to 0..1 beyond it, as imgui_impl_sdl2 maps an
# axis. The old block must occur exactly once; the file is LF, tab-indented.
# usage: deadzone0342.pl <settingsOverlay.cpp>
use strict;
use warnings;

my $f = shift or die "usage: deadzone0342.pl <settingsOverlay.cpp>\n";
sub block { return join '', map { ("\t" x $_->[0]) . $_->[1] . "\n" } @_; }

my $old = block(
    [4, 'case InputKind::PadAxis: {'],
    [5, 'const float value = event.x / (event.x < 0.0f ? 32768.0f : 32767.0f);'],
    [5, 'if (event.id == SDL_CONTROLLER_AXIS_LEFTX) {'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickLeft, value < -0.25f, std::max(-value, 0.0f));'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickRight, value > 0.25f, std::max(value, 0.0f));'],
    [5, '} else if (event.id == SDL_CONTROLLER_AXIS_LEFTY) {'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickUp, value < -0.25f, std::max(-value, 0.0f));'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickDown, value > 0.25f, std::max(value, 0.0f));'],
);
my $new = block(
    [4, 'case InputKind::PadAxis: {'],
    [5, '// Experiment 0342: the analog value goes through the dead zone too, 0 inside it and rescaled to 0..1'],
    [5, '// beyond it (as imgui_impl_sdl2 maps an axis). ImGui scrolls the focused window by the left stick\'s'],
    [5, '// analog value every frame, so the raw value of a resting stick\'s drift scrolled lists by itself.'],
    [5, 'const float value = event.x / (event.x < 0.0f ? 32768.0f : 32767.0f);'],
    [5, 'const auto  past  = [](float v) { return v > 0.25f ? (v - 0.25f) / 0.75f : 0.0f; };'],
    [5, 'if (event.id == SDL_CONTROLLER_AXIS_LEFTX) {'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickLeft, value < -0.25f, past(-value));'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickRight, value > 0.25f, past(value));'],
    [5, '} else if (event.id == SDL_CONTROLLER_AXIS_LEFTY) {'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickUp, value < -0.25f, past(-value));'],
    [6, 'io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickDown, value > 0.25f, past(value));'],
);

open my $in, '<', $f or die "$f: $!\n";
my $s = do { local $/; <$in> };
close $in;
my $n = () = $s =~ /\Q$old\E/g;
die "the old block occurs $n times in $f, expected once: not changed\n" unless $n == 1;
my $at = index($s, $old);
substr($s, $at, length $old) = $new;
open my $out, '>', $f or die "$f: $!\n";
print {$out} $s;
close $out or die "$f: $!\n";
print "patched $f: the left stick's analog value through the dead zone (", length($new) - length($old), " bytes more)\n";

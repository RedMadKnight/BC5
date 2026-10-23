pgrep "^kyty_emulator" >/dev/null && { echo EMULATOR_RUNNING; cat ~/bc5-work/BOX-LOCK; exit 1; }
cd ~/bc5-work || exit 1
G="nice -n 19 ionice -c3 grep"
{
echo; echo "# part 2, $(date '+%H:%M:%S')"
echo "## where KYTY_BC5_SAVE_TRACE is set"
$G -n "KYTY_BC5_SAVE_TRACE\|KYTY_BC5_PAD_RUMBLE\|KYTY_BC5_NO_PAD_AUDIO\|BC5_LOGGING" play-pkg-log.sh play-pkg-quiet.sh run-astro-kytyplus.sh bc5-run.env bc5-pkg.env 2>/dev/null | cut -c1-200
echo "## KYTY vars in bc5-run.env / bc5-pkg.env"
$G -h -o -E "^KYTY_[A-Z0-9_]+=[^ ]*" bc5-run.env bc5-pkg.env 2>/dev/null | sort -u | tr '\n' ' '; echo
echo "## how play-pkg-log.sh runs the emulator (lines with EMU or LOG after the header echo)"
$G -n -E '\$EMU|tee|2>&1|\$LOG' play-pkg-log.sh | tail -8 | cut -c1-200
echo "## how run-astro-kytyplus.sh logs"
$G -n -E 'kyty_emulator|tee|2>&1|LOG=|BC5_LOGGING|KYTY_BC5' run-astro-kytyplus.sh | head -12 | cut -c1-200
echo "## pad audio ports in the audio trace (type 4 speaker, type 10 vibration; '(pad)' = routed to the controller device)"
for f in play-pkg-last.log exp0242/raw/R1-play-pkg.log play-last.log exp0194/r-W253a/emu.log; do
  echo "=== $f: type-10 lines $($G -c 'audio trace: .* type 10 ' $f), of them '(pad)' $($G -c 'audio trace: .* type 10 .*(pad)' $f); type-4 lines $($G -c 'audio trace: .* type 4 ' $f), '(pad)' $($G -c 'audio trace: .* type 4 .*(pad)' $f); 'reopened' $($G -c 'audio device reopened' $f); 'opened SDL device' $($G -c 'opened SDL device' $f)"
  $G -m 2 'audio trace: .* type 10 ' $f | cut -c1-230 | sed 's/^/    /'
  $G -m 4 -E 'opened SDL device|no controller audio device|reopened|SDL device open failed' $f | cut -c1-200 | sed 's/^/    /'
  echo "    ports opened (distinct type/ch): $($G -o -E 'audio trace: t [0-9.]+ s port [0-9]+ type [0-9]+ [0-9]+ ch [0-9]+ Hz( \(pad\))?' $f | sed -E 's/t [0-9.]+ s //' | sort -u | tr '\n' ';')"
done
echo "## pad devices seen (SDL/udev lines)"
$G -h -m 6 -i -E 'controller|gamepad|joystick' play-last.log play-pkg-last.log | sort | uniq -c | sort -rn | head -10 | cut -c1-200
echo "## done part 2 $(date '+%H:%M:%S')"
} | tee -a ~/bc5-work/exp0256/log-check.txt

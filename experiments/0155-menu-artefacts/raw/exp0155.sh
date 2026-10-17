#!/usr/bin/env bash
# Experiment 0155: the second title's Initial Setup (private empty save directory, run 627) swept
# down and up 10 times (7 presses at 500 ms each way, 2.5 s pause), no cross after the first;
# a screenshot after each half-sweep; the pad script fully scripted (no live driving).
# Usage: exp0155.sh <run> <label> [ENV=VALUE ...] ; BC5_UNSET="A B" removes shortcut settings.
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
{ printf "wait 80000\npress cross\nwait 15000\n"; for s in $(seq 1 10); do for i in 1 2 3 4 5 6 7; do printf "press down\nwait 500\n"; done; printf "wait 2500\n"; for i in 1 2 3 4 5 6 7; do printf "press up\nwait 500\n"; done; printf "wait 2500\n"; done; } > input$R.cmd
{
  echo "#!/usr/bin/env bash"
  echo "# BC5 run $R (exp 0155, $LABEL): Initial Setup swept down/up 10 times, screenshots per half-sweep (watch$R.sh)."
  echo "export BC5_RUN_CWD=\$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=\$HOME/bc5-work/input$R.cmd"
  for kv in "$@"; do echo "export $kv"; done
  [ -n "${BC5_UNSET:-}" ] && echo "export BC5_UNSET=\"$BC5_UNSET\""
  echo "exec ~/bc5-work/play-pkg-exp0155.sh"
} > run$R.sh
cat > watch$R.sh <<EOW
#!/usr/bin/env bash
# BC5: watchdog for run $R (exp 0155): a screenshot at +93 s and after each half-sweep (from +100 s every 6 s, 20 in all), kill at +225 s.
cd ~/bc5-work; exec > ~/bc5-work/watch$R.log 2>&1
for i in \$(seq 1 120); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
pgrep -x kyty_emulator >/dev/null || { echo "no emulator within 120 s"; exit 1; }
T0=\$(date +%s); echo "emulator seen at \$(date +%T) (\$T0)"
at() { while [ \$(( \$(date +%s) - T0 )) -lt \$1 ]; do sleep 0.2; done; }
at 93; echo "shot s00 at +\$(( \$(date +%s) - T0 ))"; SHOTS=$R ./shot.sh s00 0 | tail -1
for k in \$(seq 1 20); do at \$(( 94 + k * 6 )); echo "shot s\$k at +\$(( \$(date +%s) - T0 )) done=\$(cat input$R.cmd.done)"; SHOTS=$R ./shot.sh s\$k 0 | tail -1; done
at 225; pkill -x kyty_emulator; echo "kill at +\$(( \$(date +%s) - T0 )) s"
sleep 4; pgrep -x kyty_emulator >/dev/null && { pkill -9 -x kyty_emulator; echo SIGKILL; } || echo killed
sleep 2; cp play-pkg-last.log run$R-stderr.log; echo DONE
EOW
chmod +x run$R.sh watch$R.sh
echo "run $R ($LABEL) written"

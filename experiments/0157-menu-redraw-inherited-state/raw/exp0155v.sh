#!/usr/bin/env bash
# Experiment 0155, Visuals route: Initial Setup > View All Settings > Visuals (run 627's route, scripted),
# then down every 2 s through the list (35 steps) and up again; a screenshot every 2 s from +95 s.
# Usage: exp0155v.sh <run> <label> [ENV=VALUE ...]; BC5_UNSET="A B" removes shortcut settings.
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
{ printf "wait 80000\npress cross\nwait 15000\n"; for i in 1 2 3 4 5 6 7; do printf "press down\nwait 700\n"; done; printf "wait 2000\npress cross\nwait 4000\n"
  for i in 1 2 3 4 5; do printf "press down\nwait 800\n"; done; printf "wait 2000\npress cross\nwait 4000\n"
  for i in $(seq 1 35); do printf "press down\nwait 2000\n"; done; for i in $(seq 1 35); do printf "press up\nwait 2000\n"; done; } > input$R.cmd
{
  echo "#!/usr/bin/env bash"
  echo "# BC5 run $R (exp 0155, $LABEL): Initial Setup > View All Settings > Visuals, the list scrolled down and up at 2 s a step; screenshots every 2 s (watch$R.sh)."
  echo "export BC5_RUN_CWD=\$HOME/bc5-work/exp0155-cwd KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-exp0155 KYTY_BC5_INPUT_CMD=\$HOME/bc5-work/input$R.cmd"
  for kv in "$@"; do echo "export $kv"; done
  [ -n "${BC5_UNSET:-}" ] && echo "export BC5_UNSET=\"$BC5_UNSET\""
  echo "exec ~/bc5-work/play-pkg-exp0155.sh"
} > run$R.sh
cat > watch$R.sh <<EOW
#!/usr/bin/env bash
# BC5: watchdog for run $R (exp 0155): a screenshot every 2 s from +93 s (shot number = seconds/2), kill at +270 s.
cd ~/bc5-work; exec > ~/bc5-work/watch$R.log 2>&1
for i in \$(seq 1 120); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
pgrep -x kyty_emulator >/dev/null || { echo "no emulator within 120 s"; exit 1; }
T0=\$(date +%s); echo "emulator seen at \$(date +%T) (\$T0)"
at() { while [ \$(( \$(date +%s) - T0 )) -lt \$1 ]; do sleep 0.1; done; }
for k in \$(seq 47 134); do at \$(( k * 2 )); echo "shot s\$k at +\$(( \$(date +%s) - T0 )) done=\$(cat input$R.cmd.done)"; SHOTS=$R ./shot.sh s\$k 0 | tail -1; done
at 270; pkill -x kyty_emulator; echo "kill at +\$(( \$(date +%s) - T0 )) s"
sleep 4; pgrep -x kyty_emulator >/dev/null && { pkill -9 -x kyty_emulator; echo SIGKILL; } || echo killed
sleep 2; cp play-pkg-last.log run$R-stderr.log; echo DONE
EOW
chmod +x run$R.sh watch$R.sh
echo "run $R ($LABEL) written: $(grep -c press input$R.cmd) presses"

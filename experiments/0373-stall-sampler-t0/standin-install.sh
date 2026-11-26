#!/usr/bin/env bash
# BC5 exp 0373 (T0, laptop only): a stand-in run of tools/scripts/gpu-stall-sampler/install.sh's real (root) path.
# No root, no device, no box: a copy of install.sh whose paths point into a scratch directory, with shims on PATH for
# id, getent, pgrep, install, chown, systemctl, sleep and umr. The fake umr prints umr's own formats (umr
# src/app/scan.c:108-109 for -r, with its colour codes; main.c:1112-1122 for -lr, dword addresses); the fake
# `--find` and `--once` stand in for the debugfs reads; everything else runs the real sampler. What it exercises:
# the self-test gate, the unit rendering, the umr regex arguments ("*.gfx1013.^mmNAME$"), the -lr filter, the
# comparison table, the stalls.log hand-off.
# usage: bash standin-install.sh SCRATCH_DIR [PYTHON]      (SCRATCH_DIR must not exist yet)
set -eu
REPO=$(cd "$(dirname "$0")/../.." && pwd)
SRC=$REPO/tools/scripts/gpu-stall-sampler
ST=${1:?usage: standin-install.sh SCRATCH_DIR [PYTHON]}
PYBIN=${2:-python3}
[ ! -e "$ST" ] || { echo "$ST exists"; exit 1; }
mkdir -p "$ST/shim" "$ST/sbin" "$ST/etc" "$ST/home/bc5-data/captures" "$ST/setup"
cp "$SRC/bc5-gpu-stall-sampler" "$SRC/bc5-gpu-stall-sampler.service" "$SRC/undo.sh" "$ST/setup/"
# install.sh with its system paths moved into the scratch directory ('|' delimiters; checked with grep below)
sed -e "s|/usr/local/sbin/bc5-gpu-stall-sampler|$ST/sbin/bc5-gpu-stall-sampler|g" \
    -e "s|/etc/systemd/system/bc5-gpu-stall-sampler.service|$ST/etc/bc5-gpu-stall-sampler.service|g" \
    -e "s|PY=/usr/bin/python3|PY=$PYBIN|" -e 's|PYF="-I -B"|PYF=""|' "$SRC/install.sh" > "$ST/setup/install.sh"
grep -q "BIN=$ST/sbin/bc5-gpu-stall-sampler" "$ST/setup/install.sh" || { echo "sed missed BIN"; exit 1; }
grep -q "UNIT=$ST/etc/" "$ST/setup/install.sh" || { echo "sed missed UNIT"; exit 1; }
grep -q "PY=$PYBIN\$" "$ST/setup/install.sh" || { echo "sed missed PY"; exit 1; }
if grep -q '/usr/local/sbin\|/etc/systemd' "$ST/setup/install.sh"; then echo "a system path is left"; exit 1; fi

cat > "$ST/shim/id" << 'EOF'
#!/usr/bin/env bash
case "$1" in -u) echo 0 ;; -gn) echo standin ;; -un) echo root ;; *) echo 0 ;; esac
EOF
cat > "$ST/shim/getent" << EOF
#!/usr/bin/env bash
echo "\$2:x:1000:1000::$ST/home:/bin/bash"
EOF
cat > "$ST/shim/pgrep" << 'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat > "$ST/shim/chown" << EOF
#!/usr/bin/env bash
echo "chown \$*" >> "$ST/actions.log"
EOF
cat > "$ST/shim/sleep" << 'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$ST/shim/systemctl" << EOF
#!/usr/bin/env bash
echo "systemctl \$*" >> "$ST/actions.log"
if [ "\$1" = restart ]; then   # the service's first line, as run_service writes it
  echo "2026-10-29T12:00:00.000 start pid=4242 version=0373-t0 debugfs=/sys/kernel/debug/dri/0000:01:00.0 (standin)" >> "$ST/home/bc5-data/captures/gpu-stall/stalls.log"
fi
if [ "\$1" = status ]; then echo "* bc5-gpu-stall-sampler.service - BC5: non-halting GPU stall sampler (stand-in)"; fi
EOF
cat > "$ST/shim/install" << EOF
#!/usr/bin/env bash
# install [-d] [-m MODE] [-o U] [-g G] SRC DST : copy or mkdir, owners ignored
echo "install \$*" >> "$ST/actions.log"
d=0; args=()
while [ \$# -gt 0 ]; do case "\$1" in -d) d=1 ;; -m|-o|-g) shift ;; *) args+=("\$1") ;; esac; shift; done
if [ \$d = 1 ]; then mkdir -p "\${args[@]}"; else cp "\${args[0]}" "\${args[1]}"; fi
EOF
# the fake umr: -r prints the value the fake --once stored for that name (coloured, as umr does); -lr lists dword
# addresses from --list-regs (byte / 4) plus registers the sampler does not use
cat > "$ST/shim/umr" << EOF
#!/usr/bin/env bash
echo "umr \$*" >> "$ST/actions.log"
if [ "\$1" = -r ]; then
  n=\$(printf '%s' "\$2" | sed -e 's|^\*\.gfx1013\.^mm||' -e 's|\\\$\$||')
  v=\$(awk -v n="\$n" '\$1 == n {print \$2}' "$ST/values.txt")
  printf '\033[36mgfx1013.mm%s\033[0m => \033[33m%s\033[0m\n' "\$n" "\${v:-0xdeadbeef}"
elif [ "\$1" = -lr ]; then
  printf '\tcyan_skillfish.gfx1013.mmSQ_THREAD_TRACE_CTRL (0) => 0x08de8\n'
  "$PYBIN" "$ST/setup/real-sampler" --list-regs | awk '{printf "\tcyan_skillfish.gfx1013.mm%s (0) => 0x%05x\n", \$1, strtonum(\$2) / 4}'
fi
EOF
# the installed sampler: --find and --once stand in for debugfs; the rest is the real tool
mv "$ST/setup/bc5-gpu-stall-sampler" "$ST/setup/real-sampler"
cat > "$ST/setup/bc5-gpu-stall-sampler" << EOF
#!/usr/bin/env bash
case " \$* " in
  *" --find "*) echo "debugfs /sys/kernel/debug/dri/0000:01:00.0 realpath /sys/kernel/debug/dri/0000:01:00.0 name 'amdgpu dev=0000:01:00.0 unique=0000:01:00.0' links 1 (stand-in)" ;;
  *" --once "*)
    echo "# bc5-gpu-stall-sampler 0373-t0 --once: debugfs (stand-in), pending rings: none, gfxoff 0"
    "$PYBIN" "$ST/setup/real-sampler" --list-regs | awk '\$3 == "sampled" {printf "%s 0x%08x\n", \$1, NR * 4096 + 7}' > "$ST/values.txt"
    awk '{printf "gfx1013.mm%s => %s   (byte -)\n", \$1, \$2}' "$ST/values.txt"
    echo "gfx1013.mmCC_GC_SHADER_ARRAY_CONFIG[se0.sa0] => 0x00180000" ;;
  *) exec "$PYBIN" "$ST/setup/real-sampler" "\$@" ;;
esac
EOF
chmod +x "$ST"/shim/* "$ST/setup/bc5-gpu-stall-sampler"
# install.sh runs "$PY $PYF <path>/bc5-gpu-stall-sampler ...": the stand-in python runs that (bash) wrapper
cat > "$ST/setup/py-wrapper" << EOF
#!/usr/bin/env bash
case "\${1:-}" in *bc5-gpu-stall-sampler) exec bash "\$@" ;; esac
exec "$PYBIN" "\$@"
EOF
chmod +x "$ST/setup/py-wrapper"
sed -i -e "s|PY=$PYBIN\$|PY=$ST/setup/py-wrapper|" "$ST/setup/install.sh"
grep -q "PY=$ST/setup/py-wrapper" "$ST/setup/install.sh" || { echo "sed missed the wrapper"; exit 1; }

echo "== stand-in: SUDO_USER=standin bash install.sh (paths under $ST)"
( cd "$ST/setup" && PATH="$ST/shim:$PATH" SUDO_USER=standin bash install.sh )
echo "== actions"
cat "$ST/actions.log"
echo "== install-check.txt"
cat "$ST/home/bc5-data/captures/gpu-stall/install-check.txt"
echo "== unit"
cat "$ST/etc/bc5-gpu-stall-sampler.service"

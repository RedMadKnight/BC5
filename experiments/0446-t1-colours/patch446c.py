import sys
p = sys.argv[1]
s = open(p).read()
o = 'if [ "$MODE" = any ]; then CMD=("$W/play-any.sh" "$PKG"); else ENVS+=("BC5_PKG=$PKG"); CMD=("$W/play-pkg.sh"); fi\n'
n = ('if [ "$MODE" = any ]; then CMD=("$W/play-any.sh" "$PKG")\n'
     'elif [ "$MODE" = drv ]; then ENVS+=("BC5_PKG=$PKG"); CMD=("$X/play-pkg-446.sh")  # his play-pkg.sh with 3 lines changed: lean log, mount log, working directory\n'
     'else ENVS+=("BC5_PKG=$PKG"); CMD=("$W/play-pkg.sh"); fi\n'
     'read -r -a XE <<< "${X446_ENV:-}"; ENVS+=("${XE[@]}")\n'
     '[ "${X446_MH:-0}" = 1 ] && ENVS+=(MANGOHUD=1 "MANGOHUD_CONFIG=fps_only=1,alpha=0,background_alpha=0,autostart_log=1,log_interval=0,output_folder=$R/$TAG-mh,log_duration=$((SECS - 10))")\n'
     'say "words added: ${XE[*]:-none}; MangoHud log ${X446_MH:-0}"\n')
assert s.count(o) == 1
s = s.replace(o, n)
open(p + ".new", "w").write(s)
print("ok")

# BC5 exp 0442 (tag bake442): sourced by swap0442.sh. Old md5s: the box's tree (patch 589ef163) and the shared backend
# source ~/bc5-work/d19/export/backend as read on 2026-11-22; new md5s: mk0442.py's output (host/) and the branch's
# backend/ files (be/), the ones box0442b.sh builds. be/CMakeLists.txt is the box export's own file (309acd3c) with the
# three lines of the deleted sources taken out, not main's (the export's test and experiment lines are older than main's).
# HOST_FILES: <tree path>:<old>:<new>:<file in host/>   HOST_ADD: <tree path>:<new>:<file in host/>
HOST_FILES="src/bc5/switch_defaults.hpp:48ae1cd6:7af89ba1:switch_defaults.hpp src/libs/bc5LleAgc.cpp:ed489aca:ea564dbd:bc5LleAgc.cpp src/graphics/presentation/settingsOverlay.cpp:0acb8d6b:b7757f72:settingsOverlay.cpp src/bc5/load_stat.hpp:e4090056:8e401e5f:load_stat.hpp src/graphics/presentation/hostMenu.cpp:34546c89:4168cdc1:hostMenu.cpp src/graphics/presentation/window/hostInput.cpp:83ef5bef:1892dce5:hostInput.cpp"
# bake 1d: the two lean words the ray-tracing switch read, gone with it (lean has no kGone0442 report); not in priv5
LEAN_EXTRA_LOST="KYTY_BC5_RT KYTY_BC5_RT_BUILD_PGM"
HOST_ADD="src/bc5/idraws0442.hpp:4254c562:idraws0442.hpp"
# BE_FILES: <path>:<old>:<new> (file in be/<path>)   BE_GONE: <path>:<old>
BE_FILES="src/direct.cpp:1b8b55ec:9956715f src/indirect_check.cpp:6c0adc0a:f07ba4bf src/shadow_labels.cpp:2cfbea8b:1fd2ec16 include/bc5/direct.hpp:18c66de8:77523d93 include/bc5/indirect_check.hpp:06bc795e:389f6add include/bc5/shadow_labels.hpp:a8bf0059:575f120b CMakeLists.txt:309acd3c:29e1c3ef"
BE_GONE="include/bc5/host_indirect.hpp:c9f68384 include/bc5/zero_skip.hpp:782ca0e9 src/host_indirect.cpp:3457152d tests/host_indirect_test.cpp:76a519af tests/zero_skip_test.cpp:2608c753"

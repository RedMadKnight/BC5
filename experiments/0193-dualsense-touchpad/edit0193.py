#!/usr/bin/env python3
# Experiment 0193 edits to ~/src/KytyPlus (exact replacements, each must match once).
import sys

ROOT = sys.argv[1]


def edit(path, pairs):
    p = f"{ROOT}/{path}"
    s = open(p, newline="").read()
    crlf = "\r\n" in s  # the KytyPlus sources are CRLF throughout
    for old, new in pairs:
        if crlf:
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        n = s.count(old)
        if n != 1:
            sys.exit(f"{path}: {n} matches for {old[:60]!r}")
        s = s.replace(old, new)
    open(p, "w", newline="").write(s)
    print(f"{path}: {len(pairs)} edits")


edit("src/graphics/presentation/window/window.cpp", [
    (
        "\t\tcase SDL_CONTROLLER_BUTTON_DPAD_RIGHT: return Controller::PAD_BUTTON_RIGHT;\n\t\tdefault: return 0;\n",
        "\t\tcase SDL_CONTROLLER_BUTTON_DPAD_RIGHT: return Controller::PAD_BUTTON_RIGHT;\n"
        "\t\t// BC5 (experiment 0193): the DualSense's touchpad click is a button of its own in SDL's HIDAPI\n"
        "\t\t// driver (SDL_hidapi_ps5.c, joystick button 15, \"touchpad:b15\" in the generated mapping);\n"
        "\t\t// only BACK (the Create button) was mapped to the touchpad bit, so a press on the touchpad\n"
        "\t\t// itself never reached the game. \"Pad:touchpad=none\" in the input configuration drops it.\n"
        "\t\tcase SDL_CONTROLLER_BUTTON_TOUCHPAD: return Controller::PAD_BUTTON_TOUCH_PAD;\n"
        "\t\tdefault: return 0;\n",
    ),
    (
        "\t\tcase SDL_CONTROLLERAXISMOTION: {\n",
        "\t\tcase SDL_CONTROLLERTOUCHPADDOWN:\n"
        "\t\tcase SDL_CONTROLLERTOUCHPADMOTION:\n"
        "\t\tcase SDL_CONTROLLERTOUCHPADUP: { // BC5 (experiment 0193): fingers on the pad's touchpad\n"
        "\t\t\tstatic const bool touch = [] {\n"
        "\t\t\t\tconst char* e = std::getenv(\"KYTY_BC5_PAD_TOUCH\");\n"
        "\t\t\t\treturn e != nullptr && std::atoi(e) == 1;\n"
        "\t\t\t}();\n"
        "\t\t\tif (touch && event->ctouchpad.touchpad == 0) {\n"
        "\t\t\t\tController::ControllerTouch(event->ctouchpad.which, event->ctouchpad.finger,\n"
        "\t\t\t\t                            event->ctouchpad.type != SDL_CONTROLLERTOUCHPADUP,\n"
        "\t\t\t\t                            event->ctouchpad.x, event->ctouchpad.y);\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "\t\t}\n"
        "\n"
        "\t\tcase SDL_CONTROLLERAXISMOTION: {\n",
    ),
])

edit("src/libs/controller.h", [
    (
        "void ControllerMotion(int id, bool gyro, const float* xyz);\n",
        "void ControllerMotion(int id, bool gyro, const float* xyz);\n"
        "// BC5 (experiment 0193): a finger on the pad's touchpad (SDL's controller touchpad events: finger\n"
        "// 0 or 1, x and y 0..1 from the left and the top). window.cpp forwards them only with\n"
        "// KYTY_BC5_PAD_TOUCH=1; without it the pad data carries no touch points, as before.\n"
        "void ControllerTouch(int id, int finger, bool down, float x, float y);\n",
    ),
])

edit("src/libs/controller.cpp", [
    (
        "\tfloat    orient[4]                             = {0.0f, 0.0f, 0.0f, 1.0f}; // BC5: x, y, z, w\n};\n",
        "\tfloat    orient[4]                             = {0.0f, 0.0f, 0.0f, 1.0f}; // BC5: x, y, z, w\n"
        "\t// BC5 (experiment 0193): the touch points the guest is given (touch_num 0: none).\n"
        "\tuint8_t  touch_num                             = 0;\n"
        "\tuint16_t touch_x[2]                            = {0, 0};\n"
        "\tuint16_t touch_y[2]                            = {0, 0};\n"
        "\tuint8_t  touch_id[2]                           = {0, 0};\n"
        "};\n"
        "\n"
        "// The touchpad resolution this host reports in scePadGetControllerInformation; touch positions\n"
        "// are given to the guest in it. TODO(verify) against a console.\n"
        "static constexpr int PAD_TOUCH_RESOLUTION_X = 1920;\n"
        "static constexpr int PAD_TOUCH_RESOLUTION_Y = 943;\n",
    ),
    (
        "\tvoid Motion(int id, bool gyro, const float* xyz);\n\tvoid ResetOrientation(int index);\n",
        "\tvoid Motion(int id, bool gyro, const float* xyz);\n"
        "\tvoid Touch(int id, int finger, bool down, float x, float y);\n"
        "\tvoid ResetOrientation(int index);\n",
    ),
    (
        "\t\tstd::chrono::steady_clock::time_point gyro_time;\n\t\tbool                                  gyro_seen = false;\n\t};\n",
        "\t\tstd::chrono::steady_clock::time_point gyro_time;\n"
        "\t\tbool                                  gyro_seen = false;\n"
        "\t\t// BC5 (experiment 0193): the two fingers on the touchpad, the latest sample like the motion\n"
        "\t\t// above; a finger's id changes with each new contact.\n"
        "\t\tbool     finger_down[2] = {false, false};\n"
        "\t\tuint16_t finger_x[2]    = {0, 0};\n"
        "\t\tuint16_t finger_y[2]    = {0, 0};\n"
        "\t\tuint8_t  finger_id[2]   = {0, 0};\n"
        "\t\tuint8_t  last_finger_id = 0;\n"
        "\t};\n",
    ),
    (
        "\t\tfor (int k = 0; k < 4; k++) {\n\t\t\tstate->orient[k] = s.orient[k];\n\t\t}\n\t}\n",
        "\t\tfor (int k = 0; k < 4; k++) {\n\t\t\tstate->orient[k] = s.orient[k];\n\t\t}\n\t}\n"
        "\tvoid ApplyTouch(int index, ControllerState* state) const {\n"
        "\t\tconst auto& s   = m_slots[static_cast<size_t>(index)];\n"
        "\t\tstate->touch_num = 0;\n"
        "\t\tfor (int f = 0; f < 2; f++) {\n"
        "\t\t\tif (!s.finger_down[f]) {\n"
        "\t\t\t\tcontinue;\n"
        "\t\t\t}\n"
        "\t\t\tconst int n      = state->touch_num++;\n"
        "\t\t\tstate->touch_x[n]  = s.finger_x[f];\n"
        "\t\t\tstate->touch_y[n]  = s.finger_y[f];\n"
        "\t\t\tstate->touch_id[n] = s.finger_id[f];\n"
        "\t\t}\n"
        "\t}\n",
    ),
    (
        "\tdata->touch_data_touch0_id   = 1;\n\tdata->touch_data_touch1_id   = 2;\n",
        "\tdata->touch_data_touch0_id   = 1;\n"
        "\tdata->touch_data_touch1_id   = 2;\n"
        "\t// BC5 (experiment 0193): the touch points, when KYTY_BC5_PAD_TOUCH=1 forwards them (without it\n"
        "\t// none, and the ids above as upstream had them).\n"
        "\tif (state.touch_num > 0) {\n"
        "\t\tdata->touch_data_touch_num = state.touch_num;\n"
        "\t\tdata->touch_data_touch0_x  = state.touch_x[0];\n"
        "\t\tdata->touch_data_touch0_y  = state.touch_y[0];\n"
        "\t\tdata->touch_data_touch0_id = state.touch_id[0];\n"
        "\t\tif (state.touch_num > 1) {\n"
        "\t\t\tdata->touch_data_touch1_x  = state.touch_x[1];\n"
        "\t\t\tdata->touch_data_touch1_y  = state.touch_y[1];\n"
        "\t\t\tdata->touch_data_touch1_id = state.touch_id[1];\n"
        "\t\t}\n"
        "\t}\n",
    ),
    (
        "void ControllerMotion(int id, bool gyro, const float* xyz) {\n"
        "\tif (g_controller != nullptr && xyz != nullptr) {\n"
        "\t\tg_controller->Motion(id, gyro, xyz);\n"
        "\t}\n"
        "}\n",
        "void ControllerMotion(int id, bool gyro, const float* xyz) {\n"
        "\tif (g_controller != nullptr && xyz != nullptr) {\n"
        "\t\tg_controller->Motion(id, gyro, xyz);\n"
        "\t}\n"
        "}\n"
        "\n"
        "void ControllerTouch(int id, int finger, bool down, float x, float y) {\n"
        "\tif (g_controller != nullptr) {\n"
        "\t\tg_controller->Touch(id, finger, down, x, y);\n"
        "\t}\n"
        "}\n",
    ),
    (
        "void GameController::ResetOrientation(int index) {\n",
        "void GameController::Touch(int id, int finger, bool down, float x, float y) {\n"
        "\tCommon::LockGuard lock(m_mutex);\n"
        "\n"
        "\tif (finger < 0 || finger > 1) {\n"
        "\t\treturn;\n"
        "\t}\n"
        "\tint slot = OwnerSlot(id);\n"
        "\tif (slot == -1) {\n"
        "\t\tslot = FallbackSlot();\n"
        "\t}\n"
        "\tEnsureSlot(slot);\n"
        "\tauto&      s     = m_slots[static_cast<size_t>(slot)];\n"
        "\tconst auto scale = [](float v, int size) {\n"
        "\t\tconst int p = static_cast<int>(v * static_cast<float>(size) + 0.5f);\n"
        "\t\treturn static_cast<uint16_t>(p < 0 ? 0 : (p >= size ? size - 1 : p));\n"
        "\t};\n"
        "\tconst bool contact = down && !s.finger_down[finger];\n"
        "\tif (contact) {\n"
        "\t\t// TODO(verify) how the console numbers contacts; here 1..127, a new one per contact.\n"
        "\t\ts.last_finger_id   = static_cast<uint8_t>(s.last_finger_id % 127 + 1);\n"
        "\t\ts.finger_id[finger] = s.last_finger_id;\n"
        "\t}\n"
        "\tconst bool lift        = !down && s.finger_down[finger];\n"
        "\ts.finger_down[finger] = down;\n"
        "\ts.finger_x[finger]    = scale(x, PAD_TOUCH_RESOLUTION_X);\n"
        "\ts.finger_y[finger]    = scale(y, PAD_TOUCH_RESOLUTION_Y);\n"
        "\n"
        "\tstatic const bool trace_env = BC5_DIAG_ENV(\"KYTY_BC5_INPUT_TRACE\") != nullptr;\n"
        "\tif (trace_env && ::Log::Bc5LoggingOn() && (contact || lift)) {\n"
        "\t\tstd::fprintf(stderr, \"input trace: t=%.3f touch finger %d %s at %u,%u id %u -> slot %d\\n\", InputTraceSeconds(), finger,\n"
        "\t\t             contact ? \"down\" : \"up\", s.finger_x[finger], s.finger_y[finger], s.finger_id[finger], slot);\n"
        "\t\tstd::fflush(stderr);\n"
        "\t}\n"
        "}\n"
        "\n"
        "void GameController::ResetOrientation(int index) {\n",
    ),
    (
        "\t*state = GetLastState(index);\n\tApplyMotion(index, state);\n",
        "\t*state = GetLastState(index);\n\tApplyMotion(index, state);\n\tApplyTouch(index, state);\n",
    ),
    (
        "\t\t\t\tApplyMotion(index, &states[ret_num]);\n",
        "\t\t\t\tApplyMotion(index, &states[ret_num]);\n\t\t\t\tApplyTouch(index, &states[ret_num]);\n",
    ),
    (
        "\tinfo->touch_resolution_x    = 1920;\n\tinfo->touch_resolution_y    = 943;\n",
        "\tinfo->touch_resolution_x    = PAD_TOUCH_RESOLUTION_X;\n\tinfo->touch_resolution_y    = PAD_TOUCH_RESOLUTION_Y;\n",
    ),
])

# SPDX-License-Identifier: GPL-2.0-only
cmake_minimum_required(VERSION 3.25)
project(bc5_backend VERSION 0.0.0 LANGUAGES CXX)

option(BC5_WITH_AMDGPU "Build the libdrm_amdgpu submission path" OFF)
option(BC5_BUILD_TESTS "Build unit tests (Catch2)" ON)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_library(bc5_warnings INTERFACE)
if(MSVC)
    target_compile_options(bc5_warnings INTERFACE /W4 /WX)
else()
    target_compile_options(bc5_warnings INTERFACE
        -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Werror)
endif()

# The submission policy table (ADR 0005) is embedded from backend/policy/pm4-policy.tsv; the same
# file is read by tools/bc5-agc.
file(READ ${CMAKE_CURRENT_SOURCE_DIR}/policy/pm4-policy.tsv BC5_POLICY_TSV)
configure_file(src/policy_tsv.hpp.in ${CMAKE_CURRENT_BINARY_DIR}/generated/policy_tsv.hpp @ONLY)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS policy/pm4-policy.tsv)

# PM4 builder, the phase-2 memset IB (ADR 0004) and the policy filter (ADR 0005): no GPU access,
# builds everywhere.
add_library(bc5_backend
    src/version.cpp
    src/pm4.cpp
    src/dispatch_min.cpp
    src/policy.cpp
)
target_include_directories(bc5_backend PUBLIC include PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/generated)
target_link_libraries(bc5_backend PRIVATE bc5_warnings)

# dispatch-min: --dump-ib everywhere; --info and --submit only with BC5_WITH_AMDGPU.
# --submit is never run by tests or CI (CLAUDE.md hard rule 5).
add_executable(dispatch-min experiments/dispatch-min/main.cpp)
target_link_libraries(dispatch-min PRIVATE bc5_backend bc5_warnings)

# userptr-min: phase-2 task 4 (Q1), CPU memory mapped 1:1 into the GPU VA space and written by
# the memset dispatch. Only --info (no GPU) without BC5_WITH_AMDGPU; --submit as above.
add_executable(userptr-min experiments/userptr-min/main.cpp)
target_link_libraries(userptr-min PRIVATE bc5_backend bc5_warnings)

if(BC5_WITH_AMDGPU)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(LIBDRM_AMDGPU REQUIRED IMPORTED_TARGET libdrm_amdgpu)
    pkg_check_modules(LIBDRM REQUIRED IMPORTED_TARGET libdrm)
    # Direct submission (ADR 0005): userptr mappings + filtered scratch IB + fence.
    target_sources(bc5_backend PRIVATE src/direct.cpp)
    target_link_libraries(bc5_backend PUBLIC PkgConfig::LIBDRM_AMDGPU PkgConfig::LIBDRM)
    target_compile_definitions(bc5_backend PUBLIC BC5_WITH_AMDGPU=1)
    target_link_libraries(dispatch-min PRIVATE PkgConfig::LIBDRM_AMDGPU)
    target_link_libraries(userptr-min PRIVATE PkgConfig::LIBDRM_AMDGPU PkgConfig::LIBDRM)
    # direct-selftest: the bc5::direct submission path with synthetic and recorded IBs, no host.
    add_executable(direct-selftest experiments/direct-selftest/main.cpp)
    target_link_libraries(direct-selftest PRIVATE bc5_backend bc5_warnings)
    # draw-min: libdrm's gfx10 memset-draw (one DRAW_INDEX_AUTO) through bc5::direct (phase-3 task 2).
    add_executable(draw-min experiments/draw-min/main.cpp)
    target_link_libraries(draw-min PRIVATE bc5_backend bc5_warnings)
endif()

if(BC5_BUILD_TESTS)
    enable_testing()
    # Prefer a system Catch2 so offline builds work; fetch only as a fallback.
    find_package(Catch2 3 QUIET)
    if(NOT Catch2_FOUND)
        include(FetchContent)
        FetchContent_Declare(Catch2
            GIT_REPOSITORY https://github.com/catchorg/Catch2.git
            GIT_TAG v3.7.1
            GIT_SHALLOW TRUE)
        FetchContent_MakeAvailable(Catch2)
        list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
    endif()
    include(Catch)

    add_executable(bc5_backend_tests tests/placeholder_test.cpp tests/pm4_test.cpp tests/policy_test.cpp)
    target_link_libraries(bc5_backend_tests PRIVATE bc5_backend bc5_warnings Catch2::Catch2WithMain)
    catch_discover_tests(bc5_backend_tests)
endif()

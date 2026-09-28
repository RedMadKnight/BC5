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

add_library(bc5_backend
    src/version.cpp
)
target_include_directories(bc5_backend PUBLIC include)
target_link_libraries(bc5_backend PRIVATE bc5_warnings)

if(BC5_WITH_AMDGPU)
    # Submission code lands in phase 2; this only proves the dependency resolves.
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(LIBDRM_AMDGPU REQUIRED IMPORTED_TARGET libdrm_amdgpu)
    target_link_libraries(bc5_backend PRIVATE PkgConfig::LIBDRM_AMDGPU)
    target_compile_definitions(bc5_backend PUBLIC BC5_WITH_AMDGPU=1)
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

    add_executable(bc5_backend_tests tests/placeholder_test.cpp)
    target_link_libraries(bc5_backend_tests PRIVATE bc5_backend bc5_warnings Catch2::Catch2WithMain)
    catch_discover_tests(bc5_backend_tests)
endif()

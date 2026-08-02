cmake_minimum_required(VERSION 3.20)

set(SHADPS4_PKG_ROOT "${CMAKE_SOURCE_DIR}/third_party/shadps4_pkg")
if(NOT EXISTS "${SHADPS4_PKG_ROOT}/core/file_format/pkg.cpp")
  message(FATAL_ERROR "The audited shadPS4 PKG source subset is missing")
endif()

find_package(ZLIB REQUIRED)
find_path(CRYPTOPP_INCLUDE_DIR cryptopp/aes.h
  HINTS /opt/homebrew/include /usr/local/include)
option(PS4FFPSC_STATIC_CRYPTOPP "Link Crypto++ statically for portable binaries" ON)
if(PS4FFPSC_STATIC_CRYPTOPP AND NOT WIN32)
  set(PS4FFPSC_SAVED_LIBRARY_SUFFIXES "${CMAKE_FIND_LIBRARY_SUFFIXES}")
  set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
  find_library(CRYPTOPP_LIBRARY NAMES cryptopp
    HINTS /opt/homebrew/opt/cryptopp/lib /opt/homebrew/lib /usr/local/lib)
  set(CMAKE_FIND_LIBRARY_SUFFIXES "${PS4FFPSC_SAVED_LIBRARY_SUFFIXES}")
else()
  find_library(CRYPTOPP_LIBRARY NAMES cryptopp
    HINTS /opt/homebrew/lib /usr/local/lib)
endif()
if(NOT CRYPTOPP_INCLUDE_DIR OR NOT CRYPTOPP_LIBRARY)
  message(FATAL_ERROR "Crypto++ was not found. Run scripts/bootstrap_macos.sh or install cryptopp.")
endif()

add_executable(ps4_pkg_extract
  src/main.cpp
  "${SHADPS4_PKG_ROOT}/core/file_format/pkg.cpp"
  "${SHADPS4_PKG_ROOT}/core/file_format/pkg_type.cpp"
  "${SHADPS4_PKG_ROOT}/core/file_format/psf.cpp"
  "${SHADPS4_PKG_ROOT}/core/crypto/crypto.cpp")

target_compile_features(ps4_pkg_extract PRIVATE cxx_std_23)
target_compile_definitions(ps4_pkg_extract PRIVATE PS4FFPSC_STANDALONE=1)
target_include_directories(ps4_pkg_extract PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/compat"
  "${SHADPS4_PKG_ROOT}"
  "${CRYPTOPP_INCLUDE_DIR}")
target_link_libraries(ps4_pkg_extract PRIVATE ZLIB::ZLIB "${CRYPTOPP_LIBRARY}")

set_target_properties(ps4_pkg_extract PROPERTIES
  POSITION_INDEPENDENT_CODE ON)
if(WIN32 AND MINGW)
  # MinGW needs this explicitly to select wmainCRTStartup for the wide entrypoint.
  target_link_options(ps4_pkg_extract PRIVATE -municode)
endif()
if(MSVC AND PS4FFPSC_STATIC_CRYPTOPP)
  set_property(TARGET ps4_pkg_extract PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

add_test(NAME ps4_pkg_extract_help COMMAND ps4_pkg_extract --help)

add_executable(ps4_pkg_extract_unicode_path_tests
  tests/unicode_path_tests.cpp)
target_compile_features(ps4_pkg_extract_unicode_path_tests PRIVATE cxx_std_23)
target_include_directories(ps4_pkg_extract_unicode_path_tests PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/compat")
add_test(NAME ps4_pkg_extract_unicode_path_tests
  COMMAND ps4_pkg_extract_unicode_path_tests)
add_test(NAME ps4_pkg_extract_unicode_path_integration
  COMMAND "${CMAKE_COMMAND}"
    "-DHELPER=$<TARGET_FILE:ps4_pkg_extract>"
    "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/unicode_path_integration"
    -P "${CMAKE_CURRENT_SOURCE_DIR}/tests/unicode_path_integration.cmake")

add_executable(ps4_pkg_extract_crypto_tests
  tests/crypto_tests.cpp
  "${SHADPS4_PKG_ROOT}/core/crypto/crypto.cpp")
target_compile_features(ps4_pkg_extract_crypto_tests PRIVATE cxx_std_23)
target_include_directories(ps4_pkg_extract_crypto_tests PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/compat"
  "${SHADPS4_PKG_ROOT}"
  "${CRYPTOPP_INCLUDE_DIR}")
target_link_libraries(ps4_pkg_extract_crypto_tests PRIVATE "${CRYPTOPP_LIBRARY}")
if(MSVC AND PS4FFPSC_STATIC_CRYPTOPP)
  set_property(TARGET ps4_pkg_extract_crypto_tests PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()
add_test(NAME ps4_pkg_extract_crypto_tests COMMAND ps4_pkg_extract_crypto_tests)

add_executable(ps4_pkg_extract_pkg_tests
  tests/pkg_extract_tests.cpp
  "${SHADPS4_PKG_ROOT}/core/file_format/pkg.cpp"
  "${SHADPS4_PKG_ROOT}/core/file_format/pkg_type.cpp"
  "${SHADPS4_PKG_ROOT}/core/crypto/crypto.cpp")
target_compile_features(ps4_pkg_extract_pkg_tests PRIVATE cxx_std_23)
target_compile_definitions(ps4_pkg_extract_pkg_tests PRIVATE PS4FFPSC_STANDALONE=1)
target_include_directories(ps4_pkg_extract_pkg_tests PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/compat"
  "${SHADPS4_PKG_ROOT}"
  "${CRYPTOPP_INCLUDE_DIR}")
target_link_libraries(ps4_pkg_extract_pkg_tests PRIVATE ZLIB::ZLIB "${CRYPTOPP_LIBRARY}")
if(MSVC AND PS4FFPSC_STATIC_CRYPTOPP)
  set_property(TARGET ps4_pkg_extract_pkg_tests PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()
add_test(NAME ps4_pkg_extract_pkg_tests COMMAND ps4_pkg_extract_pkg_tests)

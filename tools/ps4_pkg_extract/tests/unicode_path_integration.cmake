cmake_minimum_required(VERSION 3.20)

if(NOT DEFINED HELPER OR NOT EXISTS "${HELPER}")
  message(FATAL_ERROR "HELPER must name the built ps4_pkg_extract executable")
endif()
if(NOT DEFINED TEST_ROOT)
  message(FATAL_ERROR "TEST_ROOT is required")
endif()

file(REMOVE_RECURSE "${TEST_ROOT}")
file(MAKE_DIRECTORY "${TEST_ROOT}")

set(expected_name "™-Кириллица.pkg")
set(input "${TEST_ROOT}/${expected_name}")
file(WRITE "${input}" "not a PKG")

execute_process(
  COMMAND "${HELPER}" inspect "${input}" --json
  RESULT_VARIABLE status
  OUTPUT_VARIABLE output
  ERROR_VARIABLE error)

if(NOT status EQUAL 3)
  message(FATAL_ERROR
    "Unicode inspect fixture returned ${status}, expected 3. stderr=${error}; stdout=${output}")
endif()

string(JSON observed_path GET "${output}" path)
get_filename_component(observed_name "${observed_path}" NAME)
if(NOT observed_name STREQUAL expected_name)
  message(FATAL_ERROR
    "Unicode argument or JSON path round trip failed: expected '${expected_name}', got '${observed_name}'")
endif()

file(REMOVE_RECURSE "${TEST_ROOT}")

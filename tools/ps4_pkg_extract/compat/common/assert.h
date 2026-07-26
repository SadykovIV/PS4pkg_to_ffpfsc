// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdexcept>

#define ASSERT(condition)                                                                        \
    do {                                                                                         \
        if (!(condition))                                                                        \
            throw std::runtime_error("shadPS4 assertion failed: " #condition);                   \
    } while (false)
#define ASSERT_MSG(condition, ...) ASSERT(condition)
#define UNREACHABLE_MSG(...) throw std::runtime_error("shadPS4 unreachable code")


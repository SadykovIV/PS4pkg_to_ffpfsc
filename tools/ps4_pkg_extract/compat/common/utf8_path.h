// SPDX-License-Identifier: GPL-2.0-or-later
// UTF-8 serialization for native filesystem paths.
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace PS4FFPSC {

inline std::filesystem::path PathFromUtf8(std::string_view value) {
    if (value.empty()) {
        return {};
    }
    return std::filesystem::path(std::u8string(
        reinterpret_cast<const char8_t*>(value.data()), value.size()));
}

inline std::string PathToUtf8(const std::filesystem::path& path) {
    const auto encoded = path.u8string();
    return {
        reinterpret_cast<const char*>(encoded.data()),
        encoded.size(),
    };
}

} // namespace PS4FFPSC

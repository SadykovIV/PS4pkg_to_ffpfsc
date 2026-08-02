// SPDX-FileCopyrightText: Copyright 2026 ps4ffpsc contributors
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <cstdint>
#include <optional>
#include <string_view>

namespace PS4FFPSC {

inline constexpr std::uint32_t PkgContentTypeAc = 0x1B;
inline constexpr std::uint32_t PkgContentTypeAl = 0x1C;

constexpr std::optional<std::string_view> DlcPackageTypeFor(
    std::uint32_t pkg_content_type) noexcept {
    switch (pkg_content_type) {
    case PkgContentTypeAc:
        return "PSAC";
    case PkgContentTypeAl:
        return "PSAL";
    default:
        return std::nullopt;
    }
}

constexpr bool DlcPackageTypeMatches(std::uint32_t pkg_content_type,
                                     std::string_view dlc_package_type) noexcept {
    const auto expected = DlcPackageTypeFor(pkg_content_type);
    return expected && *expected == dlc_package_type;
}

} // namespace PS4FFPSC

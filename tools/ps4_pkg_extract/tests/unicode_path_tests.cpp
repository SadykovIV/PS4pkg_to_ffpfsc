// SPDX-License-Identifier: GPL-2.0-or-later

#include <filesystem>
#include <stdexcept>
#include <string>

#include "common/utf8_path.h"

namespace fs = std::filesystem;

static std::string AsBytes(const std::u8string& value) {
    return {
        reinterpret_cast<const char*>(value.data()),
        value.size(),
    };
}

static void VerifyUtf8RoundTrip() {
    const std::u8string encoded =
        u8"\u2122-\u041A\u0438\u0440\u0438\u043B\u043B\u0438\u0446\u0430.pkg";
    const auto expected = AsBytes(encoded);
    const fs::path path = PS4FFPSC::PathFromUtf8(expected);
    if (PS4FFPSC::PathToUtf8(path) != expected) {
        throw std::runtime_error("filesystem UTF-8 path round trip failed");
    }
}

#ifdef _WIN32
static void VerifyWideNativePath() {
    const fs::path path(
        L"C:\\PS4 \u0418\u0433\u0440\u044B\\\u2122-\u041A\u0438\u0440\u0438\u043B\u043B\u0438\u0446\u0430.pkg");
    const auto expected = AsBytes(
        u8"C:\\PS4 \u0418\u0433\u0440\u044B\\\u2122-\u041A\u0438\u0440\u0438\u043B\u043B\u0438\u0446\u0430.pkg");
    if (PS4FFPSC::PathToUtf8(path) != expected) {
        throw std::runtime_error("wide Windows path was not serialized as UTF-8");
    }
}
#endif

int main() {
    VerifyUtf8RoundTrip();
#ifdef _WIN32
    VerifyWideNativePath();
#endif
    return 0;
}

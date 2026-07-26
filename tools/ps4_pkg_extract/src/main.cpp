// SPDX-FileCopyrightText: Copyright 2026 ps4ffpsc contributors
// SPDX-License-Identifier: GPL-2.0-or-later

#include <array>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include <cryptopp/sha.h>

#include "core/file_format/pkg.h"
#include "core/file_format/psf.h"

namespace fs = std::filesystem;

static std::string JsonEscape(std::string_view value) {
    std::ostringstream out;
    for (const unsigned char ch : value) {
        switch (ch) {
        case '"':
            out << "\\\"";
            break;
        case '\\':
            out << "\\\\";
            break;
        case '\b':
            out << "\\b";
            break;
        case '\f':
            out << "\\f";
            break;
        case '\n':
            out << "\\n";
            break;
        case '\r':
            out << "\\r";
            break;
        case '\t':
            out << "\\t";
            break;
        default:
            if (ch < 0x20) {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                    << static_cast<unsigned>(ch) << std::dec;
            } else {
                out << static_cast<char>(ch);
            }
        }
    }
    return out.str();
}

static std::string Sha256File(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot open input");
    }
    CryptoPP::SHA256 hash;
    std::array<CryptoPP::byte, 1024 * 1024> buffer{};
    while (input) {
        input.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
        const auto read = input.gcount();
        if (read > 0) {
            hash.Update(buffer.data(), static_cast<size_t>(read));
        }
    }
    std::array<CryptoPP::byte, CryptoPP::SHA256::DIGESTSIZE> digest{};
    hash.Final(digest.data());
    std::ostringstream result;
    for (const auto byte : digest) {
        result << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(byte);
    }
    return result.str();
}

static bool ValidatePkgEnvelope(const fs::path& path, std::string& reason) {
    std::error_code ec;
    const auto size = fs::file_size(path, ec);
    if (ec || size < sizeof(PKGHeader)) {
        reason = "PKG is smaller than its header";
        return false;
    }
    std::ifstream input(path, std::ios::binary);
    PKGHeader header{};
    input.read(reinterpret_cast<char*>(&header), sizeof(header));
    if (!input || header.magic != 0x7F434E54) {
        reason = "Invalid PKG magic";
        return false;
    }
    const u64 declared = header.pkg_size;
    if (declared == 0 || declared > size) {
        reason = "PKG declared size exceeds file size";
        return false;
    }
    const u64 count = header.pkg_table_entry_count;
    const u64 table = header.pkg_table_entry_offset;
    if (count > 1'000'000 || table > size || count > (size - table) / sizeof(PKGEntry)) {
        reason = "PKG entry table is out of bounds";
        return false;
    }
    input.seekg(static_cast<std::streamoff>(table));
    for (u64 i = 0; i < count; ++i) {
        PKGEntry entry{};
        input.read(reinterpret_cast<char*>(&entry), sizeof(entry));
        if (!input) {
            reason = "Truncated PKG entry table";
            return false;
        }
        const u64 offset = entry.offset;
        const u64 entry_size = entry.size;
        if (offset > size || entry_size > size - offset) {
            reason = "PKG entry is out of bounds";
            return false;
        }
    }
    return true;
}

static bool ValidateSfoEnvelope(const std::vector<u8>& buffer, std::string& reason) {
    if (buffer.size() < sizeof(PSFHeader)) {
        reason = "param.sfo is truncated";
        return false;
    }
    PSFHeader header{};
    std::memcpy(&header, buffer.data(), sizeof(header));
    if (header.magic != PSF_MAGIC) {
        reason = "Invalid param.sfo magic";
        return false;
    }
    const u64 count = header.index_table_entries;
    const u64 index_end = sizeof(PSFHeader) + count * sizeof(PSFRawEntry);
    const u64 key_table = header.key_table_offset;
    const u64 data_table = header.data_table_offset;
    if (count > 4096 || index_end > buffer.size() || key_table < index_end ||
        key_table > buffer.size() || data_table < key_table || data_table > buffer.size()) {
        reason = "param.sfo tables are out of bounds";
        return false;
    }
    for (u64 i = 0; i < count; ++i) {
        PSFRawEntry entry{};
        std::memcpy(&entry, buffer.data() + sizeof(PSFHeader) + i * sizeof(entry), sizeof(entry));
        const u64 key = key_table + static_cast<u16>(entry.key_offset);
        const u64 data = data_table + static_cast<u32>(entry.data_offset);
        const u64 length = entry.param_len;
        if (key >= data_table || data > buffer.size() || length > buffer.size() - data) {
            reason = "param.sfo entry is out of bounds";
            return false;
        }
        const auto* key_end = static_cast<const u8*>(
            std::memchr(buffer.data() + key, 0, static_cast<size_t>(data_table - key)));
        if (!key_end) {
            reason = "param.sfo key is not terminated";
            return false;
        }
        if (entry.param_fmt.Raw() == static_cast<u16>(PSFEntryFmt::Text) &&
            (length == 0 || buffer[data + length - 1] != 0)) {
            reason = "param.sfo string is not terminated";
            return false;
        }
    }
    return true;
}

static std::string GetString(const PSF& psf, std::string_view key) {
    for (const auto& entry : psf.GetEntries()) {
        if (entry.key == key && entry.param_fmt != PSFEntryFmt::Text) {
            return {};
        }
    }
    const auto value = psf.GetString(key);
    return value ? std::string(*value) : std::string{};
}

static std::string GetIntegerString(const PSF& psf, std::string_view key) {
    for (const auto& entry : psf.GetEntries()) {
        if (entry.key != key) {
            continue;
        }
        if (entry.param_fmt != PSFEntryFmt::Integer) {
            return {};
        }
        const auto value = psf.GetInteger(key);
        if (!value) {
            return {};
        }
        std::ostringstream text;
        text << "0x" << std::hex << std::setw(8) << std::setfill('0')
             << static_cast<u32>(*value);
        return text.str();
    }
    return {};
}

static std::optional<std::string> EntitlementLabel(std::string_view content_id) {
    const auto first = content_id.find('-');
    const auto second = first == std::string_view::npos ? first : content_id.find('-', first + 1);
    if (first == std::string_view::npos || second == std::string_view::npos ||
        content_id.find('-', second + 1) != std::string_view::npos) {
        return std::nullopt;
    }
    const auto label = content_id.substr(second + 1);
    if (label.size() != 16) {
        return std::nullopt;
    }
    for (const unsigned char ch : label) {
        if (!(std::isupper(ch) || std::isdigit(ch) || ch == '_')) {
            return std::nullopt;
        }
    }
    return std::string(label);
}

struct Inspection {
    PKG pkg;
    PSF psf;
    std::string sha256;
    std::string title_id;
    std::string title;
    std::string category;
    std::string content_id;
    std::string app_version;
    std::string version;
    std::string system_version;
    std::string kind;
    std::optional<std::string> entitlement;
};

static bool Inspect(const fs::path& path, Inspection& result, std::string& reason,
                    bool compute_sha256) {
    if (!ValidatePkgEnvelope(path, reason)) {
        return false;
    }
    if (!result.pkg.Open(path, reason)) {
        if (reason.empty()) {
            reason = "shadPS4 PKG::Open rejected the package";
        }
        return false;
    }
    if (!ValidateSfoEnvelope(result.pkg.sfo, reason) || !result.psf.Open(result.pkg.sfo)) {
        if (reason.empty()) {
            reason = "shadPS4 PSF::Open rejected param.sfo";
        }
        return false;
    }
    if (compute_sha256) {
        result.sha256 = Sha256File(path);
    }
    result.title_id = GetString(result.psf, "TITLE_ID");
    if (result.title_id.empty()) {
        result.title_id = std::string(result.pkg.GetTitleID());
    }
    result.title = GetString(result.psf, "TITLE");
    result.category = GetString(result.psf, "CATEGORY");
    result.content_id = GetString(result.psf, "CONTENT_ID");
    if (result.content_id.empty()) {
        const auto header = result.pkg.GetPkgHeader();
        result.content_id.assign(reinterpret_cast<const char*>(header.pkg_content_id),
                                 sizeof(header.pkg_content_id));
        result.content_id.erase(result.content_id.find('\0'));
    }
    result.app_version = GetString(result.psf, "APP_VER");
    result.version = GetString(result.psf, "VERSION");
    result.system_version = GetString(result.psf, "SYSTEM_VER");
    if (result.system_version.empty()) {
        result.system_version = GetIntegerString(result.psf, "SYSTEM_VER");
    }
    result.entitlement = EntitlementLabel(result.content_id);

    const auto header = result.pkg.GetPkgHeader();
    const bool patch =
        PKG::isFlagSet(header.pkg_content_flags, PKGContentFlag::FIRST_PATCH) ||
        PKG::isFlagSet(header.pkg_content_flags, PKGContentFlag::SUBSEQUENT_PATCH) ||
        PKG::isFlagSet(header.pkg_content_flags, PKGContentFlag::DELTA_PATCH) ||
        PKG::isFlagSet(header.pkg_content_flags, PKGContentFlag::CUMULATIVE_PATCH) ||
        PKG::isFlagSet(header.pkg_content_flags, PKGContentFlag::PATCHGO);
    if (result.category == "ac") {
        result.kind = "dlc";
    } else if (patch) {
        result.kind = "patch";
    } else if (result.category == "gd") {
        result.kind = "base";
    } else {
        result.kind = "unknown";
    }
    return true;
}

static void PrintFailure(const fs::path& path, std::string_view reason) {
    std::cout << "{\"path\":\"" << JsonEscape(path.string())
              << "\",\"supported\":false,\"error\":\"unsupported_or_encrypted_pkg\","
                 "\"reason\":\""
              << JsonEscape(reason) << "\"}\n";
}

static void PrintInspection(const fs::path& path, const Inspection& item) {
    const auto header = item.pkg.GetPkgHeader();
    std::cout << "{\"path\":\"" << JsonEscape(path.string()) << "\",\"sha256\":";
    if (item.sha256.empty()) {
        std::cout << "null";
    } else {
        std::cout << '"' << item.sha256 << '"';
    }
    std::cout << ",\"supported\":true,\"title_id\":\""
              << JsonEscape(item.title_id) << "\",\"title\":\"" << JsonEscape(item.title)
              << "\",\"category\":\"" << JsonEscape(item.category) << "\",\"content_id\":\""
              << JsonEscape(item.content_id) << "\",\"app_version\":\""
              << JsonEscape(item.app_version) << "\",\"version\":\"" << JsonEscape(item.version)
              << "\",\"system_version\":\"" << JsonEscape(item.system_version)
              << "\",\"pkg_flags\":[";
    bool first = true;
    for (const auto& [flag, name] : PKG::flagNames) {
        if (PKG::isFlagSet(header.pkg_content_flags, flag)) {
            if (!first) {
                std::cout << ',';
            }
            std::cout << '"' << name << '"';
            first = false;
        }
    }
    std::cout << "],\"kind\":\"" << item.kind << "\",\"entitlement_label\":";
    if (item.entitlement) {
        std::cout << '"' << JsonEscape(*item.entitlement) << '"';
    } else {
        std::cout << "null";
    }
    std::cout << ",\"size\":" << item.pkg.GetPkgSize() << ",\"localized_titles\":{";
    first = true;
    for (int i = 0; i < 30; ++i) {
        std::ostringstream key;
        key << "TITLE_" << std::setw(2) << std::setfill('0') << i;
        const auto value = GetString(item.psf, key.str());
        if (!value.empty()) {
            if (!first) {
                std::cout << ',';
            }
            std::cout << '"' << key.str() << "\":\"" << JsonEscape(value) << '"';
            first = false;
        }
    }
    std::cout << "}}\n";
}

static bool SafeOutputRoot(const fs::path& output, std::string& reason) {
    if (output.empty() || output == output.root_path()) {
        reason = "unsafe empty or filesystem-root output";
        return false;
    }
    std::error_code ec;
    auto current = output;
    while (!current.empty()) {
        const auto status = fs::symlink_status(current, ec);
        if (!ec && fs::is_symlink(status)) {
            reason = "output path contains a symlink";
            return false;
        }
        ec.clear();
        const auto parent = current.parent_path();
        if (parent == current) {
            break;
        }
        current = parent;
    }
    if (fs::exists(output, ec) && !fs::is_empty(output, ec)) {
        reason = "output directory must be absent or empty";
        return false;
    }
    return true;
}

static int CommandInspect(const fs::path& path, bool fast) {
    Inspection item;
    std::string reason;
    try {
        if (!Inspect(path, item, reason, !fast)) {
            PrintFailure(path, reason);
            return 3;
        }
        PrintInspection(path, item);
        return 0;
    } catch (const std::exception& error) {
        PrintFailure(path, error.what());
        return 3;
    }
}

static int CommandExtract(const fs::path& path, const fs::path& output) {
    Inspection item;
    std::string reason;
    try {
        if (!Inspect(path, item, reason, false)) {
            PrintFailure(path, reason);
            return 3;
        }
        if (!SafeOutputRoot(output, reason)) {
            PrintFailure(path, reason);
            return 1;
        }
        fs::create_directories(output);
        std::cout << "{\"event\":\"extract_start\",\"files\":0}\n";
        if (!item.pkg.Extract(path, output, reason)) {
            PrintFailure(path, reason.empty() ? "shadPS4 PKG::Extract failed" : reason);
            return 3;
        }
        const u32 count = item.pkg.GetNumberOfFiles();
        for (u32 i = 0; i < count; ++i) {
            item.pkg.ExtractFiles(static_cast<int>(i));
            std::cout << "{\"event\":\"extract_progress\",\"current\":" << (i + 1)
                      << ",\"total\":" << count << "}\n";
        }
        std::cout << "{\"event\":\"extract_complete\",\"files\":" << count << "}\n";
        return 0;
    } catch (const std::exception& error) {
        PrintFailure(path, error.what());
        return 3;
    }
}

static void PrintHelp() {
    std::cout << "Usage:\n"
                 "  ps4_pkg_extract inspect <file.pkg> --json\n"
                 "  ps4_pkg_extract inspect <file.pkg> --json --fast\n"
                 "  ps4_pkg_extract extract <file.pkg> --output <directory> --json-progress\n";
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--help") {
        PrintHelp();
        return 0;
    }
    if (argc >= 3 && std::string_view(argv[1]) == "inspect") {
        bool fast = false;
        for (int i = 3; i < argc; ++i) {
            fast = fast || std::string_view(argv[i]) == "--fast";
        }
        return CommandInspect(fs::path(argv[2]), fast);
    }
    if (argc >= 5 && std::string_view(argv[1]) == "extract") {
        fs::path output;
        for (int i = 3; i + 1 < argc; ++i) {
            if (std::string_view(argv[i]) == "--output") {
                output = fs::path(argv[i + 1]);
                break;
            }
        }
        if (!output.empty()) {
            return CommandExtract(fs::path(argv[2]), output);
        }
    }
    PrintHelp();
    return 1;
}

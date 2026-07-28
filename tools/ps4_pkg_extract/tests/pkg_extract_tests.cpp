// SPDX-FileCopyrightText: Copyright 2026 ps4ffpsc contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <algorithm>
#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#include <cryptopp/aes.h>
#include <cryptopp/modes.h>

#include "core/crypto/crypto.h"
#include "core/file_format/pkg.h"

namespace fs = std::filesystem;

static constexpr u32 NpbindDeclaredSize = 532;
static constexpr u64 NpbindStoredSize = PkgEntryStoredSize(0x403, NpbindDeclaredSize);
static_assert(NpbindStoredSize == 544);

class TemporaryDirectory {
public:
    TemporaryDirectory() {
        const auto suffix = std::chrono::steady_clock::now().time_since_epoch().count();
        path = fs::temp_directory_path() /
               ("ps4_pkg_extract_regression_" + std::to_string(suffix));
        if (!fs::create_directory(path)) {
            throw std::runtime_error("failed to create temporary test directory");
        }
    }

    ~TemporaryDirectory() {
        std::error_code error;
        fs::remove_all(path, error);
    }

    fs::path path;
};

static std::vector<u8> ExpectedPlaintext() {
    std::vector<u8> plaintext(NpbindDeclaredSize);
    for (size_t index = 0; index < plaintext.size(); ++index) {
        plaintext[index] = static_cast<u8>((index * 17 + 3) & 0xff);
    }
    return plaintext;
}

static std::vector<u8> EncryptNpEntry(const PKGEntry& entry,
                                      std::span<const u8> plaintext) {
    std::array<u8, 64> key_material{};
    std::memcpy(key_material.data(), &entry, sizeof(entry));

    std::array<u8, 32> ivkey{};
    Crypto crypto;
    crypto.ivKeyHASH256(key_material, ivkey);

    std::vector<u8> stored_plaintext(NpbindStoredSize, 0xa5);
    std::copy(plaintext.begin(), plaintext.end(), stored_plaintext.begin());
    std::vector<u8> ciphertext(stored_plaintext.size());
    CryptoPP::CBC_Mode<CryptoPP::AES>::Encryption encryptor(
        ivkey.data() + CryptoPP::AES::BLOCKSIZE,
        CryptoPP::AES::DEFAULT_KEYLENGTH,
        ivkey.data());
    encryptor.ProcessData(
        ciphertext.data(),
        stored_plaintext.data(),
        stored_plaintext.size());
    return ciphertext;
}

static std::vector<u8> WriteSyntheticPkg(const fs::path& path,
                                         bool include_aligned_tail) {
    constexpr u64 table_offset = sizeof(PKGHeader);
    constexpr u64 data_offset = table_offset + sizeof(PKGEntry);
    const u64 available_ciphertext =
        include_aligned_tail ? NpbindStoredSize : NpbindDeclaredSize;
    const u64 package_size = data_offset + available_ciphertext;

    PKGEntry entry{};
    entry.id = 0x403;
    entry.offset = static_cast<u32>(data_offset);
    entry.size = NpbindDeclaredSize;

    PKGHeader header{};
    header.magic = 0x7F434E54;
    header.pkg_file_count = 1;
    header.pkg_table_entry_count = 1;
    header.pkg_table_entry_count_2 = 1;
    header.pkg_table_entry_offset = static_cast<u32>(table_offset);
    header.pkg_size = package_size;
    header.pfs_image_offset = 0;
    header.pfs_cache_size = 0;

    const auto plaintext = ExpectedPlaintext();
    const auto ciphertext = EncryptNpEntry(entry, plaintext);
    std::vector<u8> package(static_cast<size_t>(package_size));
    std::memcpy(package.data(), &header, sizeof(header));
    std::memcpy(package.data() + table_offset, &entry, sizeof(entry));
    std::copy_n(
        ciphertext.begin(),
        static_cast<size_t>(available_ciphertext),
        package.begin() + static_cast<size_t>(data_offset));

    std::ofstream output(path, std::ios::binary);
    output.write(
        reinterpret_cast<const char*>(package.data()),
        static_cast<std::streamsize>(package.size()));
    if (!output) {
        throw std::runtime_error("failed to write synthetic PKG");
    }
    return plaintext;
}

static std::vector<u8> ReadFile(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("failed to open extracted fixture output");
    }
    return {
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>(),
    };
}

static void VerifyAlignedCiphertextIsReadAndTrimmed(const fs::path& root) {
    const fs::path source = root / "complete.pkg";
    const fs::path output = root / "complete-output";
    const auto expected = WriteSyntheticPkg(source, true);

    PKG package;
    std::string reason;
    if (!package.Extract(source, output, reason)) {
        throw std::runtime_error("synthetic aligned PKG was rejected: " + reason);
    }
    const auto extracted = ReadFile(output / "sce_sys" / "npbind.dat");
    if (extracted.size() != NpbindDeclaredSize || extracted != expected) {
        throw std::runtime_error(
            "NP metadata was not decrypted from 544 bytes and trimmed to 532 bytes");
    }
}

static void VerifyMissingAlignedCiphertextIsRejected(const fs::path& root) {
    const fs::path source = root / "truncated.pkg";
    const fs::path output = root / "truncated-output";
    WriteSyntheticPkg(source, false);

    PKG package;
    std::string reason;
    if (package.Extract(source, output, reason)) {
        throw std::runtime_error("truncated NP metadata ciphertext was accepted");
    }
    if (reason.find("bounds") == std::string::npos) {
        throw std::runtime_error(
            "truncated NP metadata failed for an unexpected reason: " + reason);
    }
}

int main() {
    TemporaryDirectory temporary;
    VerifyAlignedCiphertextIsReadAndTrimmed(temporary.path);
    VerifyMissingAlignedCiphertextIsRejected(temporary.path);
    return 0;
}

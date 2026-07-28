// SPDX-FileCopyrightText: Copyright 2026 ps4ffpsc contributors
// SPDX-License-Identifier: GPL-2.0-or-later

#include <algorithm>
#include <array>
#include <cstddef>
#include <stdexcept>
#include <vector>

#include <cryptopp/aes.h>
#include <cryptopp/modes.h>

#include "core/crypto/crypto.h"

static std::vector<CryptoPP::byte> EncryptAligned(
    std::span<const CryptoPP::byte, 32> ivkey, std::span<const CryptoPP::byte> plaintext) {
    constexpr size_t block_size = CryptoPP::AES::BLOCKSIZE;
    if (plaintext.size() % block_size != 0) {
        throw std::invalid_argument("test plaintext must be AES-block aligned");
    }
    std::vector<CryptoPP::byte> ciphertext(plaintext.size());

    std::array<CryptoPP::byte, CryptoPP::AES::DEFAULT_KEYLENGTH> key;
    std::array<CryptoPP::byte, CryptoPP::AES::BLOCKSIZE> iv;
    std::copy_n(ivkey.data() + 16, key.size(), key.data());
    std::copy_n(ivkey.data(), iv.size(), iv.data());

    if (!plaintext.empty()) {
        CryptoPP::CBC_Mode<CryptoPP::AES>::Encryption encryptor(key.data(), key.size(), iv.data());
        encryptor.ProcessData(ciphertext.data(), plaintext.data(), plaintext.size());
    }
    return ciphertext;
}

static void VerifySize(size_t size) {
    constexpr size_t block_size = CryptoPP::AES::BLOCKSIZE;
    std::array<CryptoPP::byte, 32> ivkey;
    for (size_t i = 0; i < ivkey.size(); ++i) {
        ivkey[i] = static_cast<CryptoPP::byte>(i * 7 + 3);
    }
    const size_t stored_size = size == 0 ? 0 : ((size - 1) / block_size + 1) * block_size;
    std::vector<CryptoPP::byte> stored_plaintext(stored_size);
    for (size_t i = 0; i < stored_plaintext.size(); ++i) {
        stored_plaintext[i] = static_cast<CryptoPP::byte>(i * 11 + 5);
    }
    const auto ciphertext = EncryptAligned(ivkey, stored_plaintext);
    std::vector<CryptoPP::byte> decrypted(size);

    Crypto crypto;
    crypto.aesCbcCfb128DecryptEntry(ivkey, ciphertext, decrypted);
    if (!std::equal(decrypted.begin(), decrypted.end(), stored_plaintext.begin())) {
        throw std::runtime_error("PKG entry decryption result mismatch");
    }
}

static void VerifyNistPartialPlaintext() {
    const std::array<CryptoPP::byte, 32> ivkey = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6,
        0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf, 0x4f, 0x3c,
    };
    const std::array<CryptoPP::byte, 32> ciphertext = {
        0x76, 0x49, 0xab, 0xac, 0x81, 0x19, 0xb2, 0x46,
        0xce, 0xe9, 0x8e, 0x9b, 0x12, 0xe9, 0x19, 0x7d,
        0x50, 0x86, 0xcb, 0x9b, 0x50, 0x72, 0x19, 0xee,
        0x95, 0xdb, 0x11, 0x3a, 0x91, 0x76, 0x78, 0xb2,
    };
    const std::array<CryptoPP::byte, 20> expected = {
        0x6b, 0xc1, 0xbe, 0xe2, 0x2e, 0x40, 0x9f, 0x96, 0xe9, 0x3d,
        0x7e, 0x11, 0x73, 0x93, 0x17, 0x2a, 0xae, 0x2d, 0x8a, 0x57,
    };
    std::array<CryptoPP::byte, expected.size()> decrypted{};

    Crypto crypto;
    crypto.aesCbcCfb128DecryptEntry(ivkey, ciphertext, decrypted);
    if (decrypted != expected) {
        throw std::runtime_error("NIST AES-CBC partial plaintext mismatch");
    }
}

static void ExpectInvalidSizes(size_t ciphertext_size, size_t plaintext_size) {
    std::array<CryptoPP::byte, 32> ivkey{};
    std::vector<CryptoPP::byte> ciphertext(ciphertext_size);
    std::vector<CryptoPP::byte> plaintext(plaintext_size);
    Crypto crypto;
    try {
        crypto.aesCbcCfb128DecryptEntry(ivkey, ciphertext, plaintext);
    } catch (const std::invalid_argument&) {
        return;
    }
    throw std::runtime_error("invalid PKG AES buffer sizes were accepted");
}

int main() {
    VerifyNistPartialPlaintext();
    VerifySize(15);
    VerifySize(16);
    VerifySize(160);
    VerifySize(532);
    VerifySize(1300);
    VerifySize(1);
    VerifySize(0);

    ExpectInvalidSizes(15, 15);
    ExpectInvalidSizes(532, 532);
    ExpectInvalidSizes(543, 532);
    ExpectInvalidSizes(560, 532);
    return 0;
}

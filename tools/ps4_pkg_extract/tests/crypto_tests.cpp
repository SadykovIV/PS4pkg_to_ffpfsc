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

static std::vector<CryptoPP::byte> ReferenceDecrypt(
    std::span<const CryptoPP::byte, 32> ivkey, std::span<const CryptoPP::byte> ciphertext) {
    constexpr size_t block_size = CryptoPP::AES::BLOCKSIZE;
    const size_t padded_size =
        ((ciphertext.size() + block_size - 1) / block_size) * block_size;
    std::vector<CryptoPP::byte> padded_ciphertext(padded_size);
    std::copy(ciphertext.begin(), ciphertext.end(), padded_ciphertext.begin());
    std::vector<CryptoPP::byte> padded_decrypted(padded_size);

    std::array<CryptoPP::byte, CryptoPP::AES::DEFAULT_KEYLENGTH> key;
    std::array<CryptoPP::byte, CryptoPP::AES::BLOCKSIZE> iv;
    std::copy_n(ivkey.data() + 16, key.size(), key.data());
    std::copy_n(ivkey.data(), iv.size(), iv.data());

    if (padded_size != 0) {
        CryptoPP::CBC_Mode<CryptoPP::AES>::Decryption decryptor(key.data(), key.size(),
                                                                iv.data());
        decryptor.ProcessData(padded_decrypted.data(), padded_ciphertext.data(), padded_size);
    }
    padded_decrypted.resize(ciphertext.size());
    return padded_decrypted;
}

static void VerifySize(size_t size) {
    std::array<CryptoPP::byte, 32> ivkey;
    for (size_t i = 0; i < ivkey.size(); ++i) {
        ivkey[i] = static_cast<CryptoPP::byte>(i * 7 + 3);
    }
    std::vector<CryptoPP::byte> ciphertext(size);
    for (size_t i = 0; i < ciphertext.size(); ++i) {
        ciphertext[i] = static_cast<CryptoPP::byte>(i * 11 + 5);
    }
    std::vector<CryptoPP::byte> decrypted(size);
    const auto expected = ReferenceDecrypt(ivkey, ciphertext);

    Crypto crypto;
    crypto.aesCbcCfb128DecryptEntry(ivkey, ciphertext, decrypted);
    if (decrypted != expected) {
        throw std::runtime_error("PKG entry decryption result mismatch");
    }
}

int main() {
    VerifySize(160);
    VerifySize(532);
    VerifySize(1);
    VerifySize(0);

    std::array<CryptoPP::byte, 32> ivkey{};
    std::array<CryptoPP::byte, 16> ciphertext{};
    std::array<CryptoPP::byte, 15> decrypted{};
    Crypto crypto;
    try {
        crypto.aesCbcCfb128DecryptEntry(ivkey, ciphertext, decrypted);
    } catch (const std::invalid_argument&) {
        return 0;
    }
    return 1;
}

// SPDX-License-Identifier: GPL-2.0-or-later
// Minimal standalone-compatible subset of shadPS4 Common::FS::IOFile.
#pragma once

#include <cstdio>
#include <filesystem>
#include <span>
#include <type_traits>

#include "common/types.h"

namespace Common::FS {

enum class FileAccessMode {
    Read = 1,
    Write = 2,
    ReadWrite = 3,
    Append = 4,
    ReadAppend = 5,
};

enum class SeekOrigin : u32 {
    SetOrigin,
    CurrentPosition,
    End,
};

class IOFile final {
public:
    IOFile() = default;
    IOFile(const std::filesystem::path& path, FileAccessMode mode) {
        Open(path, mode);
    }
    ~IOFile() {
        Close();
    }
    IOFile(const IOFile&) = delete;
    IOFile& operator=(const IOFile&) = delete;

    int Open(const std::filesystem::path& path, FileAccessMode mode) {
        Close();
#ifdef _WIN32
        const wchar_t* open_mode = mode == FileAccessMode::Read     ? L"rb"
                                   : mode == FileAccessMode::Write  ? L"wb"
                                   : mode == FileAccessMode::Append ? L"ab"
                                                                    : L"r+b";
        file_ = ::_wfopen(path.c_str(), open_mode);
#else
        const char* open_mode = mode == FileAccessMode::Read     ? "rb"
                                : mode == FileAccessMode::Write  ? "wb"
                                : mode == FileAccessMode::Append ? "ab"
                                                                 : "r+b";
        file_ = std::fopen(path.c_str(), open_mode);
#endif
        return file_ ? 0 : -1;
    }
    void Close() {
        if (file_) {
            std::fclose(file_);
            file_ = nullptr;
        }
    }
    bool IsOpen() const {
        return file_ != nullptr;
    }
    bool SetBufferSize(size_t size) {
        return file_ && std::setvbuf(file_, nullptr, _IOFBF, size) == 0;
    }
    u64 GetSize() const {
        if (!file_) {
            return 0;
        }
        const auto current = Tell();
        if (current < 0 || !Seek(0, SeekOrigin::End)) {
            return 0;
        }
        const auto end = Tell();
        Seek(current, SeekOrigin::SetOrigin);
        return end < 0 ? 0 : static_cast<u64>(end);
    }
    bool Seek(s64 offset, SeekOrigin origin = SeekOrigin::SetOrigin) const {
        const int whence = origin == SeekOrigin::SetOrigin
                               ? SEEK_SET
                               : (origin == SeekOrigin::CurrentPosition ? SEEK_CUR : SEEK_END);
#ifdef _WIN32
        return file_ && ::_fseeki64(file_, offset, whence) == 0;
#else
        return file_ && ::fseeko(file_, static_cast<off_t>(offset), whence) == 0;
#endif
    }
    s64 Tell() const {
#ifdef _WIN32
        return file_ ? static_cast<s64>(::_ftelli64(file_)) : -1;
#else
        return file_ ? static_cast<s64>(::ftello(file_)) : -1;
#endif
    }

    template <typename T>
    size_t Read(T& value) const {
        if constexpr (requires { value.data(); value.size(); }) {
            return ReadRaw<typename T::value_type>(value.data(), value.size());
        } else {
            return ReadRaw<T>(&value, 1);
        }
    }
    template <typename T>
    size_t Write(const T& value) const {
        if constexpr (requires { value.data(); value.size(); }) {
            return WriteRaw<typename T::value_type>(value.data(), value.size());
        } else {
            return WriteRaw<T>(&value, 1);
        }
    }
    template <typename T>
    size_t ReadRaw(void* data, size_t size) const {
        return file_ ? std::fread(data, sizeof(T), size, file_) : 0;
    }
    template <typename T>
    size_t WriteRaw(const void* data, size_t size) const {
        return file_ ? std::fwrite(data, sizeof(T), size, file_) : 0;
    }

private:
    mutable std::FILE* file_ = nullptr;
};

} // namespace Common::FS

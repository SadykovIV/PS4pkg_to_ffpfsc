# Initial audit

**Languages:** **English** · [Русский](ru/INITIAL_AUDIT.md) ·
[Index](README.md)

Audit date: 2026-07-26.

## What was present

- `pkg/`: one Journey base PKG and one Journey patch PKG; both are user-owned and ignored by Git.
- `shadPS4-v.0.7.0.zip`: archive comment/identifier
  `3b2c01272383e1fcd0b82c7873e1ebf1a641aada`.
- No local ShadowMountPlus or MkPFS checkout.
- Git had no commits and contained untracked user data. Work moved to
  `feature/ps4-pkg-to-ffpfsc` without deleting or resetting anything.

The supplied archive was expanded as `shadPS4-v.0.7.0/`. The tag name, changelog,
source layout and archive identifier are consistent with v0.7.0. The original
archive remains untouched.

## Audited shadPS4 path and dependency graph

The standalone target compiles these supplied GPL-2.0-or-later sources directly:

- `src/core/file_format/pkg.cpp` / `pkg.h`: `PKG::Open`, `PKG::Extract`,
  `PKG::ExtractFiles`, title ID, content flags, PFS/PFSC traversal.
- `src/core/file_format/pkg_type.cpp`: `GetEntryNameByType`.
- `src/core/file_format/psf.cpp` / `psf.h`: `PSF::Open`, typed SFO getters.
- `src/core/crypto/crypto.cpp` / `crypto.h` / `keys.h`: existing FPKG RSA/AES/PFS logic.
- headers `pfs.h`, `common/endian.h`, and `common/types.h`.

Link dependencies are Crypto++ and zlib. A small compatibility `IOFile` and
logging/assert shim replaces emulator-wide common infrastructure. Qt, SDL, GPU,
Vulkan, CPU emulation, audio, and game launch code are neither compiled nor linked.
The shadPS4 `TRP` member is excluded only for the standalone target. No
cryptographic implementation was copied or rewritten.

Two necessary standalone hardening changes were made in the supplied source:
the caller-owned extraction root is retained, and file/directory dirent names
reject absolute separators, controls, `.`, and `..`. Service dirents remain valid.

## Findings and risks

- `PKG::Open` exposes embedded `param.sfo` without decrypting the full PFS.
- `PKG::Extract` supports the provided FPKG/PFSC flow. It does not make unsupported
  retail PKGs supported; failures become `unsupported_or_encrypted_pkg`.
- The v0.7.0 GUI compares versions through `double` and indexes a split DLC
  `CONTENT_ID` without checking length. Neither pattern is used.
- v0.7.0 has no proven tombstone application. The merger never invents deletions.
- `DELTA_PATCH` prerequisites cannot be proved from the exposed metadata, so an
  explicit warning is retained.
- Filesystem entries are streamed in 64 KiB blocks, but shadPS4's initial PFS
  cache phase can still be memory/CPU expensive.

## Reference audits

- ShadowMountPlus commit `8566c0294cbf37b55375602e950a0e6b6bb928d7`:
  `.ffpfsc` is an outer nested-image container; current discovery reads
  `sce_sys/param.json`; no verified PS4 addcont workflow was found.
- MkPFS 1.0.0 commit `ce62fdc63dca02175dbb5bce45c4d7c75df6ec01`:
  `pack folder` defaults to a streamed inner exFAT plus compressed outer PFS;
  `verify`, `tree --deep`, and `unpack --deep` provide the required checks.

Licenses and attribution are recorded in `THIRD_PARTY_NOTICES.md` and `LICENSES/`.

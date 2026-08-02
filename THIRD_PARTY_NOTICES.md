# Third-party notices

The application itself is distributed under GPL-3.0-or-later; see `LICENSE`.
The application, release bundle, and reproducible build process use the
components below. Entries marked build-only are not distributed as toolchain
binaries in the release archive.

## shadPS4 v0.7.0

Copyright 2024 shadPS4 Emulator Project and listed contributors.
Licensed under GPL-2.0-or-later. The standalone helper compiles the vendored,
minimal PKG, PFS/PFSC, PSF and crypto source subset. Local
compatibility/hardening changes retain the upstream SPDX headers. See
`LICENSES/shadPS4-GPL-2.0-or-later.txt` and
`third_party/shadps4_pkg/LICENSE`.

## MkPFS 1.0.0

Copyright PSBrew and listed contributors. Licensed under GPL-3.0.
Vendored from official commit
`ce62fdc63dca02175dbb5bce45c4d7c75df6ec01` as the command-line/core source
needed by this project; the upstream GUI and release assets are not included.
See `LICENSES/MkPFS-GPL-3.0.txt` and `third_party/mkpfs/LICENSE`.

## ps4-eboot-dlc-patcher patch core

Copyright idlesauce and listed upstream contributors. Licensed under
GPL-3.0. A reduced source adaptation of upstream commit
`d1d1e0f0dbd5e06da45b7d8f8ca1827d34546692` is vendored under
`third_party/ps4_dlc_patch`. It retains the ELF/module-loader, Iced code-scanner,
strict PRX patch core, and companion PRX source. Interactive UI, LibOrbisPkg
package parsing, unsafe fallbacks, generated objects, and the compiled PRX
template are not included. See `LICENSES/ps4-eboot-dlc-patcher-GPL-3.0.txt`,
`third_party/ps4_dlc_patch/LICENSE`, and
`third_party/ps4_dlc_patch/UPSTREAM.md`.

Iced 1.21.0, copyright 2018-present iced project and contributors, is restored
as a managed build dependency for this helper under the MIT license. See
`LICENSES/Iced-MIT.txt` and the Iced source at <https://github.com/icedland/iced>.

The companion PRX source includes the tiny printf implementation, copyright
2014-2019 Marco Paland, PALANDesign Hannover, Germany, under the MIT license.
See `LICENSES/mpaland-printf-MIT.txt`; the original notices also remain in
`third_party/ps4_dlc_patch/prx_src/printf.c` and `printf.h`.

## .NET Runtime 8.0.26

Copyright .NET Foundation and contributors. Licensed under the MIT license.
The self-contained NativeAOT DLC helper pins
`Microsoft.NETCore.App.Runtime` 8.0.26 through `RuntimeFrameworkVersion` and
therefore includes selected runtime implementation code in the native
executable. See `LICENSES/dotnet-runtime-8.0.26-LICENSE.txt` and the complete
upstream third-party attribution file
`LICENSES/dotnet-runtime-8.0.26-THIRD-PARTY-NOTICES.txt`.

## OpenOrbis PS4 Toolchain v0.5.4 (build-only)

Copyright OpenOrbis contributors. Licensed under GPL-3.0. The release build
downloads the official `toolchain-llvm-18.tar.gz` archive, verifies SHA-256
`3c7cd5bb593ca74fa1c13fd59f3938dc0fc07985167f7275063019e63abe4526`,
and uses its headers, libraries, linker script, and `create-fself` utility to
produce the DLC module template. The OpenOrbis toolchain archive itself is not
vendored in this repository or copied into the application bundle. See
`LICENSES/OpenOrbis-PS4-Toolchain-v0.5.4-GPL-3.0.txt`.

## Crypto++

Crypto++ 8.9.0 is statically linked into the release helper. The macOS release
build downloads the official `cryptopp890.zip` asset from the upstream release,
verifies SHA-256
`4cc0ccc324625b80b695fcd3dee63a66f1a460d3e51b71640cdbfc4cd1a3779c`,
and compiles the static library from source for arm64 with a macOS 13.0
deployment target. No prebuilt Homebrew Crypto++ object is used or included.
See `LICENSES/CryptoPP.txt`.

## Python and Qt for Python

The release embeds the official Python 3.13.14 macOS framework under the PSF
license; see `LICENSES/Python-3.13.14.txt`. The bootstrap verifies the official
`python-3.13.14-macos11.pkg` SHA-256
`8e58affb218c155a1dfdc27b291f817129669f8760e7a297adb2e4439ba5d2e8`
before extracting its framework into the isolated build cache. The bootstrap
does not install Python system-wide.

PySide6 Essentials and shiboken6 6.9.3, including the required Qt libraries,
are distributed under their GPL-3.0-only licensing option in this GPL-3.0
application. The GPL-3.0 text is provided in `LICENSE`.
Project sources are available from <https://code.qt.io/cgit/pyside/pyside-setup.git/>
and <https://code.qt.io/cgit/qt/qtbase.git/>.

## Python runtime libraries and freezer

- cryptography 49.0.0: Apache-2.0 OR BSD-3-Clause; the release selects the
  BSD-3-Clause terms. See `LICENSES/cryptography.txt` and
  `LICENSES/cryptography-BSD.txt`.
- python-isal 1.8.0 and python-zlib-ng 1.0.0: PSF-2.0; see
  `LICENSES/python-isal.txt` and `LICENSES/python-zlib-ng.txt`.
- ISA-L and zlib-ng native libraries: see `LICENSES/ISA-L.txt` and
  `LICENSES/zlib-ng.txt`.
- PyInstaller 6.21.0 bootloader: GPL-2.0-or-later with the PyInstaller
  bootloader exception. See `LICENSES/PyInstaller.txt`.

## Reference-only projects

ShadowMountPlus commit `8566c0294cbf37b55375602e950a0e6b6bb928d7`
was audited for layout and metadata behavior. Its code is not linked into the
converter. A separately attributed patch set is provided for review.

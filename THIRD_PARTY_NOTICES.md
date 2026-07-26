# Third-party notices

The application itself is distributed under GPL-3.0-or-later; see `LICENSE`.
The release bundle contains the components below.

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

## Crypto++

Crypto++ 8.9.0 is statically linked into the release helper. Homebrew supplies
it only on the build Mac; it is not required by the resulting application.
See `LICENSES/CryptoPP.txt`.

## Python and Qt for Python

The release embeds Python 3.14 under the PSF license; see
`LICENSES/Python-3.14.txt`.

PySide6 Essentials and shiboken6 6.11.1, including the required Qt libraries,
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

# Desktop GUI

**Languages:** **English** · [Русский](ru/GUI.md) ·
[Index](README.md)

`PS4 FFPFSC` is a self-contained macOS arm64 and Windows x64 application
implemented with PySide6 Essentials. It embeds Python, Qt, MkPFS and the native
PKG helper, but calls the same `ps4ffpsc` worker used by automated tests, so the
GUI and command-line path do not have separate conversion implementations.

## Input modes

- **Selected files** passes every chosen `.pkg`/`.PKG` explicitly. The default
  `pkg/` directory is not mixed into this mode.
- **Recursive folder** scans the selected directory and every descendant
  directory. Files with other extensions are ignored.
- **Unpacked game** accepts either a flat root containing `eboot.bin` and
  `sce_sys/param.sfo`, or a dumper-style root with `app/` and an optional
  `patch/`. The source remains read-only; merge never consumes its files.

Switching modes clears the previous inventory. The source PKGs remain in place
and are opened read-only by the extractor.

The header language selector switches the complete interface between Russian
and English without restarting the application. The selection is persisted for
the next launch.

The scan path intentionally avoids reading every byte of every package. It
reads package headers/metadata and records a cheap path/size/mtime scan identity.
At build time the worker refreshes that cheap identity and starts extraction
immediately. It does not perform a full source-file hash pass.

## Workflow

1. Select PKG files, a recursive PKG folder, or an unpacked game tree.
2. Select the output folder.
3. Keep the system temporary directory (`%TEMP%` on Windows or `/tmp` on
   macOS), or choose a different directory/volume. The GUI shows its currently
   available space and remembers the choice.
4. Scan. The tree groups BASE, PATCH and DLC packages by TITLE_ID and shows
   conflicts or unsupported packages without selecting them for a build. A
   dedicated size column shows every PKG, the approximate total source size of
   each game, and the summary shows the total size of checked packages.
5. Keep or clear the check mark beside each individual PKG. All supported
   packages are checked by default. Exact copies identified by the PKG's
   embedded package digest are shown as duplicates and unchecked by default;
   split `part1`/`part2` packages with different digests remain checked.
   Unsupported entries are listed separately and do not block a checked
   supported game. An explicit `backport`, `back-port`, or `Fix5.05` entry is
   shown as a backport layer and ordered after the ordinary update with the
   same APP_VER. In unpacked-game mode, the top-level game row selects the
   complete source container; its TREE/PATCH TREE/DLC child rows are
   informational because those components cannot be independently omitted
   without changing the selected source layout.
6. Choose the output format, then build. Compressed `FFPFSC` is the default;
   uncompressed raw `exFAT` is also available. Raw exFAT is written directly to
   the final artifact, and selective verification reads the filesystem
   structure and byte-compares only required game files instead of creating a
   second full-size image.
7. For FFPFSC, choose a compression level from 0 through 9 and a worker count
   from 1 through the detected logical CPU count. Level 7 is the default; level
   0 disables deflate inside the FFPFSC container. The worker default is half
   of the logical CPUs, with a minimum of one, so conversion does not occupy
   every available thread. Both selections are persisted. Compression controls
   do not apply to raw exFAT.
8. Experimental single-image DLC is disabled by default. Enable it only for a
   deliberate compatibility test. `PSAC` carries game data; `PSAL` is
   license-only. The mode may modify staged copies of game executables and
   place selected DLC support data in the main game image; it never writes to
   source PKGs or the selected unpacked tree. A completed and verified image
   is not proof that DLC will be registered, detected, or usable on a PS5.
   `runtime_verified=false` remains until a hardware test.

When packages were found but no game is buildable, the primary action remains
enabled as **Check readiness** / **Проверить готовность**. It lists the actual
block reason. In particular, a large patch with `CATEGORY=gp` is still a patch;
base `CATEGORY=gd` is required before it can be built with its DLC.

The progress area shows the overall percentage for all selected games, the
current stage and substage, exact elapsed time, and an estimated remaining time.
During extraction, the native helper reports actual bytes written from inside
the decrypt/write loop. Each package's extraction ratio is weighted by its
source PKG size, so a small base and a large patch no longer receive equal
weight. The displayed extraction ETA uses this byte rate. MkPFS
compression/verification continues to stream its own structured progress.
Before enough work has completed for a useful estimate, the remaining-time
field explicitly says that it is still being calculated.
Builds run one TITLE_ID at a time, and the GUI continues with the next selected
game if one build fails.

**Cancel** clears the remaining game queue and terminates the complete process
tree on both macOS and Windows—not only the GUI worker, but also the native PKG
extractor and MkPFS. This prevents detached children from continuing to write
after cancellation. A later run can reuse verified extraction state when
**Resume interrupted work** is enabled.

Before extracting, resume performs a metadata-only check of each previously
completed package tree (relative paths, sizes and modification times). Matching
trees are reused without opening their payload files, and only missing,
changed, or previously failed PKGs are extracted. The per-package state is
saved after every successful extraction and can also be recovered from the
current manifest.

Extractor revisions are part of the resume identity. Version 0.2.6 advances
that revision, so trees produced by the older NP-metadata extraction logic are
treated as stale and extracted again rather than accepted as valid cache.

The merge prefers same-filesystem hardlinks over full copies and falls back
automatically on filesystems that do not support them. Extracted package trees
are removed after the merged tree is verified. A successful build removes its
entire per-game temporary workspace; a failed or cancelled build keeps the
verified state required for resume. Neither cleanup path changes source PKGs or
completed output artifacts.
For an unpacked source the same hardlink/copy policy is used with source
consumption disabled, and cleanup remains confined to the temporary workspace.

The PKG helper keeps one read handle open for the complete extraction and uses
a bounded 8 MiB read-ahead cache instead of thousands of tiny 64 KiB
operations. This reduces SMB/NAS overhead, especially on macOS. Progress
reporting is throttled and does not recursively measure the temporary
directory, so the indicator does not introduce extra payload reads or copies.

Encrypted NP entries `0x400`–`0x403` require two sizes: the declared plaintext
size and the stored ciphertext size rounded up to the 16-byte AES-CBC boundary.
For the regression case, a declared 532-byte `npbind.dat` occupies 544 bytes in
the PKG. The helper now reads and decrypts all 544 bytes, then writes exactly
532 bytes. This preserves the internal 20-byte SHA-1 footer instead of
corrupting its final bytes.

Separately, for a **selected unpacked game**, version 0.2.8 automatically
inspects `sce_sys/npbind.dat` after copying or linking it into the temporary
`merged` tree. If its magic, version, declared size, and entry layout are valid
but only the SHA-1 footer differs, the application atomically replaces the
final 20 bytes in the temporary copy. It performs no write when the footer is
already valid, and fails the build instead of hiding a structural error. The
selected source tree remains unchanged in every case.

## Launch and packaging

Download and completely extract
`PS4-FFPFSC-v0.2.8-windows-x64.zip`, then launch `PS4 FFPFSC.exe`. The
accompanying `_internal` directory and `ps4ffpsc-worker.exe` are required parts
of the self-contained application.

To build the Windows archive on a native Windows x64 host, install Python
3.13.14, .NET SDK 8, CMake/Ninja, and the required static vcpkg packages. Build
the DLC module template first on macOS or Linux with OpenOrbis PS4 Toolchain
v0.5.4, then provide its absolute path:

```powershell
$env:PS4FFPSC_DLC_TEMPLATE = "C:\path\to\dlcldr.prx"
.\scripts\build_release_windows_x64.ps1
```

The GitHub Actions workflow `.github/workflows/build-windows-x64.yml` provisions
the Linux-built template and remaining Windows build dependencies, runs the
test suite, builds the application, audits all bundled PE files as x64, and
uploads the ZIP/checksum/notes artifact.

The NativeAOT helper targets .NET 8 and pins
`Microsoft.NETCore.App.Runtime` 8.0.26.

For macOS arm64:

```bash
./scripts/bootstrap_macos.sh
./scripts/build_release_macos_arm64.sh
open "build-release/dist/PS4 FFPFSC.app"
```

The bootstrap downloads the official Python 3.13.14 macOS package and verifies
its pinned SHA-256 before extracting the framework into an isolated build
cache; it does not modify `/Library`. It installs PySide6 Essentials and
shiboken6 6.9.3 into the project virtual environment. Crypto++ 8.9.0 is downloaded as a pinned upstream source
archive and compiled locally for arm64 with a macOS 13.0 deployment target;
the Homebrew Crypto++ bottle is deliberately not used.

The release script builds the C++ helper with that static Crypto++ library,
freezes the Python and Qt runtime, signs the application, and audits every
Mach-O architecture, dependency, and deployment target. Any component that
requires a macOS version above 13.0 fails the release gate. Frozen
doctor/MkPFS/GUI smoke tests then run before the ZIP and SHA-256 sidecar are
created under `release/`.

The release script uses ad-hoc signing unless
`PS4FFPSC_CODESIGN_IDENTITY` contains an installed Developer ID identity.
An ad-hoc-signed public ZIP normally requires **Control-click → Open** once.
For source-tree development, use `./ps4ffpsc-gui.command`.

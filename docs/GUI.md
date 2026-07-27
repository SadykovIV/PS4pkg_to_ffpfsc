# Desktop GUI

`PS4 FFPFSC` is a self-contained macOS arm64 and Windows x64 application
implemented with PySide6 Essentials. It embeds Python, Qt, MkPFS and the native
PKG helper, but calls the same `ps4ffpsc` worker used by automated tests, so the
GUI and command-line path do not have separate conversion implementations.

## Input modes

- **Selected files** passes every chosen `.pkg`/`.PKG` explicitly. The default
  `pkg/` directory is not mixed into this mode.
- **Recursive folder** scans the selected directory and every descendant
  directory. Files with other extensions are ignored.

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

1. Select PKG files or a source folder.
2. Select the output folder.
3. Keep the system temporary directory (`%TEMP%` on Windows or `/tmp` on
   macOS), or choose a different directory/volume. The GUI shows its currently
   available space and remembers the choice.
4. Scan. The tree groups BASE, PATCH and DLC packages by TITLE_ID and shows
   conflicts or unsupported packages without selecting them for a build. A
   dedicated size column shows every PKG, the approximate total source size of
   each game, and the summary shows the total size of checked games.
5. Keep or clear the check mark beside every buildable game.
6. Choose compatibility and DLC policy, then build.

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

**Cancel** first requests a graceful process termination and then forces it
after three seconds. A later run can reuse verified extraction state when
**Resume interrupted work** is enabled.

The merge prefers same-filesystem hardlinks over full copies and falls back
automatically on filesystems that do not support them. Extracted package trees
are removed after the merged tree is verified. A successful build removes its
entire per-game temporary workspace; a failed or cancelled build keeps the
verified state required for resume. Neither cleanup path changes source PKGs or
completed output artifacts.

The PKG helper keeps one read handle open for the complete extraction and uses
a bounded 8 MiB read-ahead cache instead of thousands of tiny 64 KiB
operations. This reduces SMB/NAS overhead, especially on macOS. Progress
reporting is throttled and does not recursively measure the temporary
directory, so the indicator does not introduce extra payload reads or copies.

## Launch and packaging

Download and completely extract
`PS4-FFPFSC-v0.2.3-windows-x64.zip`, then launch `PS4 FFPFSC.exe`. The
accompanying `_internal` directory and `ps4ffpsc-worker.exe` are required parts
of the self-contained application.

To build the Windows archive on a native Windows x64 host with Python and
vcpkg already available:

```powershell
.\scripts\build_release_windows_x64.ps1
```

The GitHub Actions workflow `.github/workflows/build-windows-x64.yml` provisions
the remaining build dependencies, runs the test suite, builds the application,
audits all bundled PE files as x64, and uploads the ZIP/checksum/notes artifact.

For macOS arm64:

```bash
./scripts/bootstrap_macos.sh
./scripts/build_release_macos_arm64.sh
open "build-release/dist/PS4 FFPFSC.app"
```

The script builds the helper with static Crypto++ linkage, freezes the Python
and Qt runtime, signs the application, audits every Mach-O architecture and
dependency, runs frozen doctor/MkPFS/GUI smoke tests, then creates a ZIP and
SHA-256 sidecar under `release/`.

The release script uses ad-hoc signing unless
`PS4FFPSC_CODESIGN_IDENTITY` contains an installed Developer ID identity.
An ad-hoc-signed public ZIP normally requires **Control-click → Open** once.
For source-tree development, use `./ps4ffpsc-gui.command`.

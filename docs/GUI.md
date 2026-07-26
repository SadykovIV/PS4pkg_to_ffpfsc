# Desktop GUI

`PS4 FFPFSC.app` is a self-contained macOS arm64 application implemented with
PySide6 Essentials. It embeds Python, Qt, MkPFS and the native PKG helper, but
calls the same `ps4ffpsc` worker used by automated tests, so the GUI and
command-line path do not have separate conversion implementations.

## Input modes

- **Selected files** passes every chosen `.pkg`/`.PKG` explicitly. The default
  `pkg/` directory is not mixed into this mode.
- **Recursive folder** scans the selected directory and every descendant
  directory. Files with other extensions are ignored.

Switching modes clears the previous inventory. The source PKGs remain in place
and are opened read-only by the extractor.

The scan path intentionally avoids reading every byte of every package. It
reads package headers/metadata and records a cheap path/size/mtime scan identity.
The worker computes and records the full SHA-256 only after the user starts a
build, immediately before extracting that package.

## Workflow

1. Select PKG files or a source folder.
2. Select the output folder.
3. Keep `/tmp` for temporary files or choose a different directory/volume. The
   GUI shows its currently available space and remembers the choice.
4. Scan. The tree groups BASE, PATCH and DLC packages by TITLE_ID and shows
   conflicts or unsupported packages without selecting them for a build.
5. Keep or clear the check mark beside every buildable game.
6. Choose compatibility and DLC policy, then build.

When packages were found but no game is buildable, the primary action remains
enabled as **Check readiness** / **Проверить готовность**. It lists the actual
block reason. In particular, a large patch with `CATEGORY=gp` is still a patch;
base `CATEGORY=gd` is required before it can be built with its DLC.

The progress bar is indeterminate while a worker process is active. Detailed
stage messages are streamed to the journal. Builds run one TITLE_ID at a time,
and the GUI continues with the next selected game if one build fails.

**Cancel** first requests a graceful process termination and then forces it
after three seconds. A later run can reuse verified extraction state when
**Resume interrupted work** is enabled.

## Launch and packaging

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

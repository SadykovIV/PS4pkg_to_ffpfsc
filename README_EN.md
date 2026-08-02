# PS4 FFPFSC

**Languages:** [Русский](README.md) · **English**

PS4 FFPFSC converts supported PS4 PKGs or an already unpacked PS4 game into
images for **ShadowMountPlus**:

- `.ffpfsc` — compressed image;
- `.exfat` — uncompressed raw exFAT image.

The application combines a base game, updates, and DLC, validates the resulting
layout, and never modifies the source PKGs or the selected unpacked tree.

> [!WARNING]
> This project is under active development. Compatibility with every game is not guaranteed. Even a successfully built image may still fail to start on a PS5.

## Known issues

- **Trophy registration failure:**
  `Trophy registration failed. errcode=0x80551618`.
  This error can prevent some games from launching, including **Metro 2033**.
- **Beyond: Two Souls:** the Russian voice-over currently does not play.
- Version 0.2.7 creates separate verified DLC images, but their registration,
  mounting, and runtime behavior still depend on the mounting environment.
- Compressed FFPFSC images may perform worse in games that continuously stream large amounts of data.

## Features

- graphical interface in Russian and English;
- selection of individual PKGs, an entire folder, or an unpacked game;
- automatic grouping of base, patch, explicit backport layers, and DLC;
- duplicate detection; unchecked rejected PKGs do not block a selected game;
- FFPFSC and raw exFAT output;
- byte-for-byte preservation of the final `param.sfo`, with non-zero
  `USER_DEFINED_PARAM_1…4` mirrored into `param.json`;
- Windows Unicode paths, including Cyrillic and `™`;
- separate verified DLC images in `auto` mode;
- configurable compression level and worker thread count;
- progress, elapsed time, and ETA;
- safe cancellation;
- resume support for interrupted builds;
- self-contained releases for Windows x64 and macOS ARM64.

## Installation

Download the latest archive from the **Releases** section. Both archives are
self-contained and require neither Python nor external applications.

### Windows x64

1. Fully extract `PS4-FFPFSC-v0.2.7-windows-x64.zip`.
2. Run `PS4 FFPFSC.exe`.
3. Keep the remaining files next to the executable.

Microsoft Defender SmartScreen may require manual confirmation on first launch because the build is not signed with a commercial certificate.

### macOS ARM64

1. Extract `PS4-FFPFSC-v0.2.7-macos-arm64.zip`.
2. Move `PS4 FFPFSC.app` to `/Applications`.
3. On first launch, use **Control-click → Open**.

The current build uses ad-hoc signing.

## How to use

1. Select individual PKGs, a folder containing games, or an unpacked game. An
   unpacked source can be a root with `eboot.bin` and `sce_sys/param.sfo`, or
   an `app/` container with an optional `patch/` directory.
2. Choose the output folder.
3. Click **Scan** and review the detected base, patch, backport, and DLC items.
   An unchecked rejected PKG does not block the selected game; exact duplicates
   are disabled by default, and an explicit `backport`/`Fix5.05` layer follows
   the ordinary update with the same version.
4. Select **FFPFSC** or **raw exFAT**. For FFPFSC, also choose the compression
   level and worker count.
5. Click **Build selected**.
6. Copy the resulting image to a USB drive and add its path to ShadowMountPlus.

PKG mode requires a base package with `CATEGORY=gd`. If only updates or DLC are
found, the application reports that the base game is missing.

## Sources and temporary files

Source PKGs and unpacked trees are read-only. When merging an unpacked tree,
the application uses hardlinks or ordinary copies and never moves source
files. The per-game temporary directory is removed only after a fully
successful build; verified state remains available for resume after a failure.

## Output

For each game, the application creates:

```text
<name>.ffpfsc or <name>.exfat
<name>.<format>.manifest.json
<name>.<format>.shadowmount.txt
```

Add the image using `scanpath=` or place its full path in:

```text
/data/shadowmount/manual.lst
```

The ShadowMountPlus log is located at:

```text
/data/shadowmount/debug.log
```

`static_shadowmount_compatible=true` means that the image layout passed static validation. It does not guarantee that the game will start on a PS5.

## What the application does not do

The application does not search for keys, bypass DRM, download games, or convert unsupported or encrypted retail PKG files.

Such files are marked as `unsupported_or_encrypted_pkg`, and processing continues with the remaining PKG files.

## Verified launch

A **Journey v01.01** image created by this application was successfully launched and tested on a PS5 on **July 26, 2026**.

This confirms that the pipeline works for that specific image, but it does not guarantee compatibility with other games.

## Building from source on macOS ARM64

```bash
./scripts/bootstrap_macos.sh
./scripts/build_release_macos_arm64.sh
open "build-release/dist/PS4 FFPFSC.app"
```

To run the development version:

```bash
./ps4ffpsc-gui.command
```

To view the available CLI commands:

```bash
./ps4ffpsc --help
```

An unpacked game uses the same validation and build flow without the extractor:

```bash
./ps4ffpsc scan --dump-dir "/games/CUSA12345"
./ps4ffpsc build CUSA12345 --dump-dir "/games/CUSA12345"
```

## Reporting an issue

When opening an Issue, include the game name, `TITLE_ID`, version, package types, selected format, and exact error message. Also attach `manifest.json`, `shadowmount.txt`, and the relevant section of `/data/shadowmount/debug.log`.

Full change history: [CHANGELOG.md](CHANGELOG.md).

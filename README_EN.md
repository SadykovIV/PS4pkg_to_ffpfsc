# ps4ffpsc

**Languages:** **English** · [Русский](README.md)

> Self-contained GUI converter from supported PS4 PKGs to verified FFPFSC or
> raw exFAT images for ShadowMountPlus. Ready-made macOS arm64 and Windows x64
> builds do not require Python or external applications.

## Ready-made desktop applications

Both release archives are self-contained and include Python, Qt, MkPFS and the
native PKG helper:

- **Windows x64:** extract
  `PS4-FFPFSC-v0.2.6-windows-x64.zip` completely, then run
  `PS4 FFPFSC.exe`. Keep the accompanying files in the extracted directory.
  An unsigned build may require explicit approval in Microsoft Defender
  SmartScreen on first launch.
- **macOS arm64:** extract `PS4-FFPFSC-v0.2.6-macos-arm64.zip`, move
  `PS4 FFPFSC.app` to `/Applications`, then use
  **Control-click → Open** for the first launch of the current ad-hoc-signed
  build.

Version 0.2.6 adds FFPFSC/raw exFAT output selection, configurable MkPFS worker
count, and reliable cancellation of the complete process tree. It also fixes
encrypted NP metadata extraction when the final AES-CBC block is partial;
temporary trees produced before this extractor fix are automatically treated
as stale.

See the complete release history in [CHANGELOG.md](CHANGELOG.md).

To reproduce the macOS release from source:

```bash
./scripts/bootstrap_macos.sh
./scripts/build_release_macos_arm64.sh
open "build-release/dist/PS4 FFPFSC.app"
```

The ZIP, checksum, and release notes are written to `release/`.
`./ps4ffpsc-gui.command` remains a direct development launcher. The GUI groups packages by
TITLE_ID, exposes buildable/conflicted states, supports selecting multiple
games, streams the operation log, remains responsive during conversion, and
supports cancellation/resume. Source PKGs are never modified.
The **Русский / English** selector in the header switches the complete GUI
localization immediately and remembers the selected language.
The discovered-games table lets each PKG be selected independently and shows
its size, the approximate total source size per game, and the total size of
checked packages. All supported packages are checked by default. Exact copies
identified by the embedded package digest are marked as duplicates and
unchecked without a full-file hash pass; different `part1`/`part2` packages
remain selected. During extraction, progress and the stage ETA follow bytes
actually written, weighted by the source sizes of base, patch and DLC packages.
Before building, select compressed FFPFSC (the default) or an uncompressed raw
exFAT image. Raw exFAT is created as the single partial image, then atomically
published under its final name after verification. Selective verification reads
the filesystem structure, extracts and byte-compares the required game files
and metadata, without creating a second full-size image.

For FFPFSC, compression levels 0 through 9 are available and remembered. Level
0 disables deflate inside FFPFSC, level 1 favors speed, level 9 favors size, and
level 7 remains the default. The compression worker selector ranges from 1 to
the number of logical CPUs visible to the application. It defaults to half of
that count, with a minimum of one, so MkPFS does not monopolize the host.
Compression controls do not apply to raw exFAT output.

**Cancel** terminates the complete worker process tree on macOS and Windows,
including the native extractor and MkPFS, and clears the remaining game queue.
Previously verified state remains reusable; incomplete partial data is
discarded on the next attempt, and no detached child is left writing in the
background.

The Windows x64 release is reproducibly built and smoke-tested by
`.github/workflows/build-windows-x64.yml` on a native Windows runner. The
workflow calls `scripts/build_release_windows_x64.ps1`; it verifies the frozen
GUI, CLI worker, MkPFS, bundled PKG helper, and every PE binary architecture.

Scanning reads only package headers and metadata. It neither copies each PKG nor
hashes an entire multi-gigabyte file. When a build starts, it checks only the
path, size, and modification time, then begins extraction immediately. A patch
(`CATEGORY=gp`) and DLC cannot replace the required base package
(`CATEGORY=gd`); the GUI keeps the readiness action available and displays this
exact reason.

Extracted PKGs, merge trees and MkPFS scratch files are stored under
`PS4 FFPFSC` inside the temporary directory selected in the GUI (`%TEMP%` on
Windows or `/tmp` on macOS by default), not under `Application Support`.
The merge uses same-volume hardlinks when available, with an automatic copy
fallback. Extracted package trees are discarded after a verified merge, and the
per-game temporary workspace is removed after a fully successful build. Failed
or cancelled builds keep verified resumable state. Source PKGs and completed
artifacts are never removed.

On a later run, the application quickly compares each previously extracted tree
using file metadata only—relative paths, sizes, and modification times—without
opening payload contents. Matching PKGs are reused, and extraction continues
only for new, changed, or previously failed packages. State is saved after each
successful PKG extraction.

The native extractor keeps the source PKG open for the complete extraction and
uses a bounded 8 MiB read-ahead cache instead of thousands of tiny 64 KiB
operations. This reduces SMB/NAS overhead. Byte progress comes directly from
the decrypt/write loop; the GUI does not repeatedly scan the temporary tree or
create progress-only copies.

For encrypted NP entries `0x400`–`0x403`, the extractor now distinguishes the
declared plaintext size from the physical ciphertext size. A 532-byte
`npbind.dat`, for example, is read from 544 bytes aligned to the 16-byte
AES-CBC boundary: the complete final block is decrypted, while exactly 532
declared bytes are written. Advancing the extractor revision prevents temporary
cache produced by the old truncating logic from being reused.

`ps4ffpsc` converts legally owned, shadPS4-supported PS4 PKGs into verified
ShadowMountPlus `.ffpfsc` or raw `.exfat` artifacts. The default path is:

`base + ordered patches + preserved DLC → merged app → nested exFAT → compressed PFS`.

It does not download keys or games, bypass licenses, convert encrypted retail
PKGs, or launch an emulator. A package rejected by the vendored, audited
shadPS4 0.7.0 PKG subset
extractor is reported as `unsupported_or_encrypted_pkg`; other packages continue.

## macOS ARM64 quick start

```bash
./scripts/bootstrap_macos.sh
./scripts/build_macos.sh
./ps4ffpsc doctor
./ps4ffpsc scan
./ps4ffpsc list
./ps4ffpsc build --all --compat current-smp --include-dlc auto
```

Put `.pkg` or `.PKG` files anywhere under `pkg/`. Input files are never renamed,
modified, or removed. Outputs are published only after MkPFS container
verification and extraction/validation of the required metadata paths.

Run `./ps4ffpsc --help` for commands and per-command options. The defaults are in
`ps4ffpsc.toml`; CLI arguments win.

## Compatibility truth

`current-smp` preserves `sce_sys/param.sfo` and adds a deterministic
`sce_sys/param.json` because audited unmodified ShadowMountPlus currently scans
that JSON. `static_shadowmount_compatible=true` is a source-level result only.
Every generated manifest remains `ps5_runtime_verified=false` until the artifact
is actually tested on a PS5.

See [Русский README](README.md), [GUI guide](docs/GUI.md),
[architecture](docs/ARCHITECTURE.md), and
[format compatibility](docs/FORMAT_COMPATIBILITY.md).

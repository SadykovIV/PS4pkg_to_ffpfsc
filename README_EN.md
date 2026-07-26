# ps4ffpsc

**Languages:** **English** · [Русский](README.md)

## Desktop GUI

The ready-made Apple Silicon release is self-contained: it does not require
Homebrew, Python, Qt, MkPFS, or this repository on the destination Mac. Extract
`PS4-FFPFSC-v0.2.1-macos-arm64.zip`, move `PS4 FFPFSC.app` to
`/Applications`, then use **Control-click → Open** for the first launch of the
current ad-hoc-signed build.

To reproduce the same release from source:

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

Scanning reads only package headers and metadata. It neither copies each PKG nor
hashes an entire multi-gigabyte file; the full SHA-256 is computed only when a
build starts, before extraction. A patch (`CATEGORY=gp`) and DLC cannot replace
the required base package (`CATEGORY=gd`); the GUI keeps the readiness action
available and displays this exact reason.

`ps4ffpsc` converts legally owned, shadPS4-supported PS4 PKGs into verified
ShadowMountPlus `.ffpfsc` artifacts:

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
modified, or removed. Outputs are published only after outer PFS verification,
deep tree inspection, exact-path metadata extraction, and SHA-256 comparison.

Run `./ps4ffpsc --help` for commands and per-command options. The defaults are in
`ps4ffpsc.toml`; CLI arguments win.

## Compatibility truth

`current-smp` preserves `sce_sys/param.sfo` and adds a deterministic
`sce_sys/param.json` because audited unmodified ShadowMountPlus currently scans
that JSON. `static_shadowmount_compatible=true` is a source-level result only.
Every generated manifest remains `ps5_runtime_verified=false` until the artifact
is actually tested on a PS5.

See [README_RU.md](README_RU.md), [GUI guide](docs/GUI.md),
[architecture](docs/ARCHITECTURE.md), and
[format compatibility](docs/FORMAT_COMPATIBILITY.md).

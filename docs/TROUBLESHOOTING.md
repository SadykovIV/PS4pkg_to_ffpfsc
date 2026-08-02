# Troubleshooting

**Languages:** **English** · [Русский](ru/TROUBLESHOOTING.md) ·
[Index](README.md)

- `unsupported_or_encrypted_pkg`: the vendored shadPS4 0.7.0 PKG path could not open
  or extract it. No online key lookup or DRM bypass is attempted.
- `extractor is not built`: run `scripts/bootstrap_macos.sh`, then
  `scripts/build_macos.sh`.
- `insufficient disk space`: choose a larger `--temp-dir`; nothing is
  automatically deleted.
- Existing merged/output path: inspect it, then explicitly use `--force`.
- Interrupted extraction: rerun with `--resume`; verified package trees are reused.
- Partial output: `.partial` is never a finished artifact. Use `status` to locate it.
- ShadowMount misses an image: verify USB path/`scanpath`/`manual.lst`, then read
  `/data/shadowmount/debug.log` for nested-image and param.json errors.
- `npbind.dat` error for a selected unpacked game: version 0.2.8 automatically
  repairs only a mismatched 20-byte SHA-1 footer, and only in the temporary
  merged copy. The selected source tree is unchanged. If the magic, version,
  declared size, or entry layout is invalid, the file is not repaired; use an
  undamaged unpacked source.
- DLC type error: experimental mode accepts `PSAC` as data-bearing DLC and
  `PSAL` as license-only DLC; the PKG header, `license.dat`, and `CONTENT_ID`
  must agree. The ordinary build runs with DLC mode disabled.

> [!WARNING]
> Successful static verification does not guarantee PS5 launch. An
> experimental image with DLC remains `runtime_verified=false` until it is
> tested on a console.

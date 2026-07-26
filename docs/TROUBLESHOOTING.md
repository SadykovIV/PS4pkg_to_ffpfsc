# Troubleshooting

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

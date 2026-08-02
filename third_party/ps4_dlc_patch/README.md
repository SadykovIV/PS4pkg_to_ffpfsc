# ps4-dlc-patch batch helper

This directory contains a reduced, non-interactive adaptation of
`idlesauce/ps4-eboot-dlc-patcher`. It accepts an unsigned ELF and an explicit
JSON entitlement list, applies only the audited PRX method, and emits a patched
ELF plus `dlcldr.prx` into a caller-selected output directory.

The helper does **not** parse PKG files, extract DLC data, convert SELF files to
ELF, edit source files in place, or use the upstream in-executable fallback.
The input ELF is opened read-only. Existing output files are never overwritten.

## Input

```text
ps4-dlc-patch --input game.elf --output-dir OUTPUT --dlc-json dlc.json
```

For callers that already hold the metadata in memory, `--dlc-json -` reads the
same JSON document from standard input. This avoids creating a plaintext JSON
key file; the file form remains available for standalone use.

`dlc.json` is a JSON array. Every item must contain exactly `label`, `type`, and
`key`:

```json
[
  {
    "label": "EXAMPLE_DLC_0001",
    "type": "PSAC",
    "key": "00000000000000000000000000000000"
  },
  {
    "label": "EXAMPLE_DLC_0002",
    "type": "PSAL",
    "key": "00000000000000000000000000000000"
  }
]
```

- `label` must match `[A-Z0-9_]{16}`.
- `type` accepts `PSAC`, `4`, or `04` for content with a data directory and
  `PSAL`, `0`, or `00` for entitlement-only content.
- `key` is exactly 16 bytes encoded as 32 hexadecimal characters.
- duplicate labels and more than 2,500 entries are rejected.
- JSON input is limited to 4 MiB.
- PSAC entries are ordered first, preserving input order within each type, so
  their indices deterministically match `/app0/dlc00`, `/app0/dlc01`, and so
  on.

Progress and errors are written to stderr. The final machine-readable status is
one JSON object on stdout. Entitlement keys are never written to logs or status
JSON. The raw input byte buffer and decoded key byte buffers are cleared before
exit; immutable strings created by the .NET JSON parser cannot be explicitly
zeroed, so standard input is preferred over a plaintext file.

## Strict method

Only the PRX method is enabled. The helper rejects an ELF unless the required
DLC imports, module/library rewrites, code-segment space, and direct
`sceSysmoduleLoadModule` call sites are all available. It never asks an
interactive question and never falls back to injecting limited handlers into
the executable.

The PRX template layout is validated before any output is published. Host-side
success proves only that patching completed consistently. It does not guarantee
runtime behavior on PS5.

Release builds can validate the embedded template without processing an ELF:

```text
ps4-dlc-patch --check-template
```

This emits one JSON object containing `template_compatible: true` and the
embedded template's SHA-256, or exits with an error if the audited layout does
not match.

## Build-time template

No compiled PRX is stored in Git. An upstream-compatible PRX template must be
supplied at build time through the MSBuild property `DlcPrxTemplatePath`; the
project embeds it under a stable resource name. The template must correspond to
the audited offsets described in `UPSTREAM.md`.

Use the supplied NativeAOT publish wrapper from a native target host:

```bash
./publish-native.sh /absolute/path/dlcldr.prx osx-arm64 /absolute/output/path
```

The output directory must be outside this vendored source directory. NativeAOT
does not support arbitrary cross-compilation, so Windows x64 publishing must run
on Windows x64 and macOS arm64 publishing must run on macOS arm64. The wrapper
also keeps all MSBuild intermediate and regular output paths in a disposable
external build directory, so publishing does not create `bin/` or `obj/` here.

## License

This adaptation and the retained upstream sources are licensed under GPL-3.0.
See `LICENSE` and `UPSTREAM.md`. Iced is restored as a NuGet dependency and is
not vendored here.

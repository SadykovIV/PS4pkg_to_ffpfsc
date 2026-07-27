# Architecture

`ps4_pkg_extract` is a narrow C++ boundary around the vendored, audited
shadPS4 0.7.0 PKG source subset. Its
`inspect --fast` command validates PKG/SFO table bounds, calls `PKG::Open` and
`PSF::Open`, and emits one JSON object without hashing the full file. `extract` calls
`PKG::Extract`/`ExtractFiles` into a dedicated `.partial` tree.

The Python `ps4ffpsc` layer owns policy:

1. Recursively scan case-insensitive `.pkg` extensions.
2. Classify from SFO `CATEGORY` and header patch flags.
3. Group by validated `CUSA` TITLE_ID; detect conflicts, orphans and region mismatches.
4. Extract each package into an isolated, resumable staging directory.
5. Copy base to `merged/app.partial`; apply integer-sorted patch overlays.
6. Preserve DLC separately under `merged/addcont/<ENTITLEMENT_LABEL>`.
7. Add/validate ShadowMount metadata without replacing `param.sfo`.
8. Stream an inner exFAT into outer PFSC with official pinned MkPFS.
9. Verify the PFSC container, extract and validate only required metadata paths,
   and then atomically publish.

The normal build path never computes content hashes for source PKGs, extracted
trees, merge trees, or the completed image. Resume identities use path, size,
and modification time; tree state uses paths, sizes, and mtimes. The explicit
`verify` command may still calculate an artifact SHA-256 on request.

All subprocesses receive argument arrays and use `shell=False`. A single game
failure is isolated during `--all`. Exit-code precedence is: insufficient space
`5`, verification `4`, general pipeline error `1`, skipped conflict `2`,
unsupported package `3`; the most severe reached stage wins.

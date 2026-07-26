# Architecture

`ps4_pkg_extract` is a narrow C++ boundary around the vendored, audited
shadPS4 0.7.0 PKG source subset. Its
`inspect` command validates PKG/SFO table bounds, hashes the file, calls
`PKG::Open` and `PSF::Open`, and emits one JSON object. `extract` calls
`PKG::Extract`/`ExtractFiles` into a dedicated `.partial` tree.

The Python `ps4ffpsc` layer owns policy:

1. Recursively scan case-insensitive `.pkg` extensions.
2. Classify from SFO `CATEGORY` and header patch flags.
3. Group by validated `CUSA` TITLE_ID; detect hashes, conflicts, orphans and region mismatches.
4. Extract each package into an isolated, resumable staging directory.
5. Copy base to `merged/app.partial`; apply integer-sorted patch overlays.
6. Preserve DLC separately under `merged/addcont/<ENTITLEMENT_LABEL>`.
7. Add/validate ShadowMount metadata without replacing `param.sfo`.
8. Stream an inner exFAT into outer PFSC with official pinned MkPFS.
9. Verify PFSC checksums, inspect the deep tree, deep-extract exact metadata paths,
   compare SHA-256, and only then atomically publish.

All subprocesses receive argument arrays and use `shell=False`. A single game
failure is isolated during `--all`. Exit-code precedence is: insufficient space
`5`, verification `4`, general pipeline error `1`, skipped conflict `2`,
unsupported package `3`; the most severe reached stage wins.

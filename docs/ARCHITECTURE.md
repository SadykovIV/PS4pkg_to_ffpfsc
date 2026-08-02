# Architecture

`ps4_pkg_extract` is a narrow C++ boundary around the vendored, audited
shadPS4 0.7.0 PKG source subset. Its
`inspect --fast` command validates PKG/SFO table bounds, calls `PKG::Open` and
`PSF::Open`, and emits one JSON object without hashing the full file. `extract` calls
`PKG::Extract`/`ExtractFiles` into a dedicated `.partial` tree. The standalone
extractor keeps one PKG read descriptor open for the full sequential operation
and uses a bounded 8 MiB read-ahead cache so a PKG on SMB/NAS is not fetched in
thousands of tiny 64 KiB round trips. It emits throttled byte counts directly
after successful output writes.

The Python `ps4ffpsc` layer owns policy. It accepts either PKGs or a read-only
unpacked source. A flat unpacked source is a consolidated application; a
dumper-style container contributes `app/` as base and optional `patch/` as an
overlay.

1. Recursively scan case-insensitive `.pkg` extensions, or validate the chosen
   unpacked tree (`eboot.bin` plus `sce_sys/param.sfo`).
2. Classify from SFO `CATEGORY` and header patch flags.
3. Group by validated `CUSA` TITLE_ID; detect conflicts, orphans and region mismatches.
4. Extract each package into an isolated, resumable staging directory, or use
   an unpacked tree in place without invoking the extractor.
5. Copy/link base to `merged/app.partial`; apply integer-sorted ordinary patch
   overlays followed by any explicitly named same-version backport layer.
6. Preserve DLC separately under `merged/addcont/<ENTITLEMENT_LABEL>`.
7. Add/validate ShadowMount metadata without replacing `param.sfo`; mirror
   non-zero `USER_DEFINED_PARAM_1…4` into the JSON compatibility projection.
8. Stream an inner exFAT into outer PFSC with official pinned MkPFS.
9. Verify the PFSC container, extract and validate only required metadata paths,
   and then atomically publish.

The normal build path never computes content hashes for source PKGs, extracted
trees, merge trees, or the completed image. Resume identities use path, size,
and modification time; tree state uses paths, sizes, and mtimes. The explicit
`verify` command may still calculate an artifact SHA-256 on request.

Files from an unpacked source are staged with `consume_source=false`. A
same-filesystem hardlink is preferred; otherwise the file is copied. Cleanup is
restricted to the application's temporary game root, so the selected dump can
never be moved or deleted by a successful or failed build.

Extraction UI progress is derived without scanning the staging tree. The native
helper reports actual output bytes and its expected decompressed payload size;
Python converts that per-package ratio into source-size-weighted progress across
base, patches and DLC.

All subprocesses receive argument arrays and use `shell=False`. A single game
failure is isolated during `--all`. Exit-code precedence is: insufficient space
`5`, verification `4`, general pipeline error `1`, skipped conflict `2`,
unsupported package `3`; the most severe reached stage wins.

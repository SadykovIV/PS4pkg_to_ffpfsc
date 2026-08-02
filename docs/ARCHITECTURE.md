# Architecture

**Languages:** **English** · [Русский](ru/ARCHITECTURE.md) ·
[Index](README.md)

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
2. Classify base and patch layers from SFO `CATEGORY` and header patch flags.
   Classify DLC PKGs from the `PSAC`/`PSAL` content type in the package
   header; use SFO `CATEGORY=ac`/`al` only as a fallback for unpacked addcont
   trees.
3. Group by validated `CUSA` TITLE_ID; detect conflicts, orphans and region mismatches.
4. Extract each package into an isolated, resumable staging directory, or use
   an unpacked tree in place without invoking the extractor.
5. Copy/link base to `merged/app.partial`; apply integer-sorted ordinary patch
   overlays followed by any explicitly named same-version backport layer.
6. For a selected unpacked source, automatically inspect
   `sce_sys/npbind.dat` in the temporary merged copy. If its structure is valid
   and only the 20-byte SHA-1 footer is wrong, replace that footer alone. The
   source tree and every byte before the footer remain unchanged; structural
   corruption is not hidden by this repair.
7. Keep ordinary DLC handling disabled by default. When the experimental
   single-image mode is explicitly enabled, preserve each selected add-on in
   isolated staging, reject exact duplicates, never overlay DLC `sce_sys`
   metadata onto the game, and prepare only staged copies for the game-specific
   `/app0` compatibility layout. `PSAC` carries game data; `PSAL` is
   license-only.
8. Add/validate ShadowMount metadata without replacing `param.sfo`; project
   every available localized `TITLE_00…29` and non-zero user parameter into
   `param.json` while preserving unrelated existing JSON fields.
9. Stream an inner exFAT into outer PFSC with official pinned MkPFS.
10. Verify the PFSC container, extract and validate only required metadata paths,
   and then atomically publish.

The experimental DLC branch may alter staged copies of game executables and
add support files to the consolidated tree. It never writes to source PKGs or
to a selected unpacked source. Host verification proves only that the resulting
container and expected files are internally consistent; entitlement discovery
and game behavior on PS5 remain `runtime_verified=false` until hardware-tested.

The normal build path never computes content hashes for source PKGs, extracted
trees, merge trees, or the completed image. Resume identities use path, size,
and modification time; tree state uses paths, sizes, and mtimes. The explicit
`verify` command may still calculate an artifact SHA-256 on request.

Files from an unpacked source are staged with `consume_source=false`. A
same-filesystem hardlink is preferred; otherwise the file is copied. Cleanup is
restricted to the application's temporary game root, so the selected dump can
never be moved or deleted by a successful or failed build. Atomic replacement
of a corrected `npbind.dat` footer also occurs only inside that temporary root.

Extraction UI progress is derived without scanning the staging tree. The native
helper reports actual output bytes and its expected decompressed payload size;
Python converts that per-package ratio into source-size-weighted progress across
base, patches and DLC.

All subprocesses receive argument arrays and use `shell=False`. A single game
failure is isolated during `--all`. Exit-code precedence is: insufficient space
`5`, verification `4`, general pipeline error `1`, skipped conflict `2`,
unsupported package `3`; the most severe reached stage wins.

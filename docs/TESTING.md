# Testing

**Languages:** **English** · [Русский](ru/TESTING.md) ·
[Index](README.md)

## Experimental DLC build inputs

The NativeAOT DLC helper requires a **.NET SDK 8** and pins
`Microsoft.NETCore.App.Runtime` to **8.0.26**. Its module template must be built
on macOS or Linux with the pinned OpenOrbis PS4 Toolchain **v0.5.4** archive;
the fetch script verifies SHA-256
`3c7cd5bb593ca74fa1c13fd59f3938dc0fc07985167f7275063019e63abe4526`.

The macOS arm64 release is pinned to the official **Python 3.13.14** installer,
PySide6 Essentials/shiboken6 **6.9.3**, and a source build of Crypto++ **8.9.0**.
The bootstrap verifies the Python package SHA-256
`8e58affb218c155a1dfdc27b291f817129669f8760e7a297adb2e4439ba5d2e8`.
It extracts the framework into the isolated build cache and does not write to
`/Library` or require administrator privileges.
The Crypto++ preparation script verifies SHA-256
`4cc0ccc324625b80b695fcd3dee63a66f1a460d3e51b71640cdbfc4cd1a3779c`,
then compiles every arm64 object for macOS 13.0 instead of using the local
Homebrew bottle. The final app audit rejects any non-arm64 Mach-O, external
non-system dependency, missing deployment target, or minimum macOS above 13.0.

For a manual native Windows x64 release, use Python 3.13.14, .NET SDK 8,
CMake/Ninja, and the vcpkg static dependencies. Set
`PS4FFPSC_DLC_TEMPLATE` to the absolute path of the template prepared on macOS
or Linux before running `scripts/build_release_windows_x64.ps1`. GitHub Actions
performs the two host-specific stages automatically.

Run:

```bash
./scripts/build_macos.sh
.venv/bin/pytest -q
./ps4ffpsc doctor
./ps4ffpsc scan
./ps4ffpsc build --all --compat current-smp --dlc-mode off
./ps4ffpsc verify output/<artifact>.ffpfsc
```

The ordinary release gate keeps experimental DLC disabled. A dedicated
single-image DLC test must opt in explicitly with
`--dlc-mode single-experimental`, use
only disposable staging/output paths, and confirm afterwards that the source
PKG metadata and sizes are unchanged.

The suite uses synthetic SFO and directory fixtures only. It covers corrupted
SFO, classification helpers, version ordering, IDs/content labels, Unicode,
path traversal, symlinks, duplicates, conflicting bases, orphan patches,
overlay reports, deterministic JSON, sparse files above 4 GiB, stat-based resume,
and a real MkPFS nested-exFAT integration.

Version 0.2.8 regression tests separately enforce the `npbind.dat` repair
boundary. For a selected unpacked game, an incorrect 20-byte SHA-1 footer is
repaired only in the temporary merged copy; bytes before the footer and the
source file remain exact copies of their previous values. A structurally
invalid file is rejected without writing. DLC tests distinguish data-bearing
`PSAC` from license-only `PSAL`, validate agreement between the PKG header and
`license.dat`, and keep `runtime_verified=false` without a hardware result.

The release gate on Apple Silicon requires CMake/CTest, the complete pytest
suite, and the frozen GUI smoke test to pass. Regression tests explicitly fail
if normal scan, unpack,
resume, or build code attempts to call the full-file SHA-256 helper. A prior
Journey artifact passed outer MkPFS verification with zero errors and exact
deep-unpack SHA comparison. `host_tests_passed=true`,
`static_shadowmount_checks_passed=true`. The user confirmed that this exact
Journey artifact launches and works on PS5 on 2026-07-26, therefore its
sidecar and local reports contain `ps5_runtime_verified=true`. New artifacts
remain unverified by default until they are tested on hardware.

The frozen arm64 app additionally passes native architecture/dependency audit,
doctor, embedded MkPFS, an offscreen Qt launch smoke test, synthetic
multi-process FFPFSC packing/verification, and exact verification of the
hardware-tested Journey image.

The reported Beat Saber directory was also scanned through the frozen worker:
247 PKGs (4.9 GB) were classified in 3.6–11 seconds across warm/cold runs,
without full-file SHA-256 reads. Its inventory correctly reports one patch and
246 DLC packages, but no `CATEGORY=gd` base package, so readiness is blocked
with an explicit GUI explanation rather than a disabled button.

The 243 MiB Beat Saber base PKG was extracted with both the v0.2.2 helper and
the optimized helper on the same Apple Silicon Mac. Diagnostics found that
64 KiB random reads over SMB were the main cold-cache bottleneck, so the helper
now combines a persistent descriptor with a bounded 8 MiB read-ahead cache.
Full per-file SHA-256 manifests from the old and new helpers were identical
(138 files, 306,326,961 bytes). A real end-to-end build completed extraction,
merge, FFPFSC packing, container verification and temporary-workspace cleanup
in 20.6 seconds on the test Mac. The byte progress stream reported the expected
decompressed payload without recursively walking the output directory.

For the 0.2.8 single-image DLC experiment, the complete Beat Saber CUSA12878
set was inventoried again with base and patch present. Of 246 DLC PKGs, one
byte-identical duplicate was excluded and 245 unique entitlement entries were
used. The resulting host-side FFPFSC passed MkPFS verification, deep extraction,
and an exact comparison of all 2,032 files and 277 directories against the
prepared tree. These checks validate construction and container integrity, not
PS5 runtime behavior. The feature remains disabled by default and is documented
as experimental until per-game hardware tests confirm DLC discovery and use.

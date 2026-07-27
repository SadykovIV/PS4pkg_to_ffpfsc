# Testing

Run:

```bash
./scripts/build_macos.sh
.venv/bin/pytest -q
./ps4ffpsc doctor
./ps4ffpsc scan
./ps4ffpsc build --all --compat current-smp --include-dlc auto
./ps4ffpsc verify output/<artifact>.ffpfsc
```

The suite uses synthetic SFO and directory fixtures only. It covers corrupted
SFO, classification helpers, version ordering, IDs/content labels, Unicode,
path traversal, symlinks, duplicates, conflicting bases, orphan patches,
overlay reports, deterministic JSON, sparse files above 4 GiB, stat-based resume,
and a real MkPFS nested-exFAT integration.

Latest local result on Apple Silicon: CMake/CTest passed; pytest `62 passed`;
GUI smoke passed. Regression tests explicitly fail if normal scan, unpack,
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

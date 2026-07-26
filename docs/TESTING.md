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
overlay reports, deterministic JSON, sparse files above 4 GiB, resume hashing,
and a real MkPFS nested-exFAT integration.

Latest local result on Apple Silicon: CMake/CTest passed; pytest `31 passed`;
doctor passed; two real user packages scanned/extracted; the produced Journey
artifact passed outer MkPFS verification with zero errors and exact deep-unpack
SHA comparison. `host_tests_passed=true`,
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

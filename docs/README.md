# Documentation

**Languages:** **English** · [Русский](ru/README.md)

This index covers the current PS4 FFPFSC documentation. Research notes and
historical artifacts are intentionally kept outside this list.

- [Architecture](ARCHITECTURE.md) — extraction, merge, verification, resume,
  and publication boundaries.
- [Experimental single-image DLC support](DLC_SUPPORT.md) — the opt-in DLC
  mode, safety guarantees, and runtime limitations.
- [Format compatibility](FORMAT_COMPATIBILITY.md) — FFPFSC/raw exFAT layout
  and ShadowMountPlus metadata.
- [Desktop GUI](GUI.md) — input modes, build workflow, progress, cancellation,
  and release packaging.
- [Initial audit](INITIAL_AUDIT.md) — audited source set, dependencies, and
  identified risks.
- [ShadowMountPlus PS4 support](SHADOWMOUNTPLUS_PS4_SUPPORT.md) — compatibility
  assumptions and static/runtime status.
- [Testing](TESTING.md) — local commands, release gates, and reference results.
- [Troubleshooting](TROUBLESHOOTING.md) — common errors and recovery steps.

Version 0.2.8 keeps experimental single-image DLC (`PSAC` data add-ons and
`PSAL` license-only add-ons) disabled by default. Source PKGs remain unchanged,
and successful host-side verification does not guarantee PS5 runtime behavior.
For a selected unpacked game, only an incorrect 20-byte SHA-1 footer in an
otherwise valid `sce_sys/npbind.dat` is repaired, and only in the temporary
merged copy; the selected source remains unchanged.

# ShadowMountPlus PS4 support

**Languages:** **English** ·
[Русский](ru/SHADOWMOUNTPLUS_PS4_SUPPORT.md) · [Index](README.md)

Audited upstream commit: `8566c0294cbf37b55375602e950a0e6b6bb928d7`.
No ShadowMountPlus source or PS5 SDK was present in the original workspace.

Current code discovers `sce_sys/param.json`, extracts `titleId`, then prefers an
`en-US` `titleName`. It stages `param.json` to appmeta and checks mounted state
through the JSON path. The `current-smp` converter mode mirrors those exact reads:

- valid UTF-8 JSON, no BOM;
- exact nine-character CUSA title ID;
- top-level `titleName` and localized `en-US.titleName`;
- original `param.sfo` remains alongside it.

A native-SFO patch set is provided at
`patches/shadowmountplus-ps4-support.patch` when applying it to the audited
upstream snapshot. It is not built because the required PS5 SDK is absent. It
must preserve existing PPSA/PS5 JSON behavior and pass host tests before payload use.

Static status is not runtime status. A PS5 test is still required.
This is especially important for version 0.2.8 experimental DLC: the mode is
disabled by default, and a successfully built single image with `PSAC` or
`PSAL` content does not guarantee game launch or add-on discovery.
`runtime_verified=false` must remain until hardware testing.

When a selected unpacked game's `npbind.dat` SHA-1 footer is repaired
automatically, the change affects only the temporary merged copy and does not
turn static verification into a runtime guarantee. The selected unpacked tree
remains unchanged.

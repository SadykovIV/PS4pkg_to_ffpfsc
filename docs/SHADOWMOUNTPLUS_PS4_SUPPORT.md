# ShadowMountPlus PS4 support

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


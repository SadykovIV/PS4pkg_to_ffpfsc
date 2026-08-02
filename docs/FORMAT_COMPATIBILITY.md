# Format compatibility

**Languages:** **English** · [Русский](ru/FORMAT_COMPATIBILITY.md) ·
[Index](README.md)

The output is not a renamed PKG and is not direct raw PFSC game content.

```text
game.ffpfsc (compressed outer PFS)
└── CUSAxxxxx.exfat
    ├── eboot.bin
    ├── sce_sys/param.sfo
    ├── sce_sys/param.json   # current-smp compatibility projection
    └── remaining game files
```

There is no `CUSAxxxxx/` folder inside exFAT. The outer PFS contains one nested
image, which matches the audited ShadowMountPlus `.ffpfsc` scanner.

MkPFS runs with the PS5 PFS profile, 32-bit inodes, 64 KiB PFSC blocks and
case-insensitive mode. Verification covers outer structure/checksums and the
inner exFAT through targeted `unpack --deep`. The required `eboot.bin`,
`param.sfo`, and (for current-smp) `param.json` paths are extracted; their
structure, sizes, TITLE_ID, and ShadowMount metadata are validated without a
second full-tree content-hash pass.

When the source is a selected unpacked game and `sce_sys/npbind.dat` is
present, version 0.2.8 validates its structure and SHA-1 footer. A mismatched
20-byte footer is repaired only in the temporary merged copy; the remaining
file bytes and the selected source tree are unchanged. The corrected
`npbind.dat` is then selectively validated inside the finished image.

Host verification does not validate PS5 kernel mount behavior. PFSC performance
is expected to be below direct exFAT/UFS because decompression throughput is
limited.

The final `param.sfo` is the exact SFO from the last selected overlay; patch
`CATEGORY=gp`, version, localized titles, and user-defined values are not
rewritten from the base package. `param.json` remains a compatibility
projection: every non-empty `TITLE_00…29` is mapped to the corresponding system
locale, existing unrelated JSON fields are preserved, and an `en-US` fallback
remains available to ShadowMountPlus. Non-zero `USER_DEFINED_PARAM_1…4` values
are mirrored as `userDefinedParam1…4` because some image-launched PS4 titles use
those selectors for language/region state. These projections preserve metadata;
they cannot guarantee that every title's audio-selection logic will use it.

Experimental single-image DLC is disabled by default. When it is explicitly
enabled, `PSAC` identifies data-bearing DLC and `PSAL` identifies license-only
DLC. The resulting container may pass every static check described here, but
that does not guarantee game launch or DLC discovery on a PS5;
`runtime_verified=false` remains until hardware testing.

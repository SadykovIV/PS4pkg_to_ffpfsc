# Format compatibility

The output is not a renamed PKG and is not direct raw PFSC game content.

```text
game.ffpfsc (compressed outer PFS)
└── CUSAxxxxx.exfat
    ├── eboot.bin
    ├── sce_sys/param.sfo
    ├── sce_sys/param.json   # current-smp
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

Host verification does not validate PS5 kernel mount behavior. PFSC performance
is expected to be below direct exFAT/UFS because decompression throughput is
limited.

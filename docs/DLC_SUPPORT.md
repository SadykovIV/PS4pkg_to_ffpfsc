# Experimental single-image DLC support

**Languages:** **English** · [Русский](ru/DLC_SUPPORT.md) ·
[Index](README.md)

Version 0.2.8 introduces an **experimental** way to place selected PS4 DLC in
the same FFPFSC or raw exFAT image as the base game and patches. It is disabled
by default. Separate DLC images remain unsuitable for the intended one-image
workflow because PS4 add-on content normally has independent entitlement,
registration, and mount semantics.

DLC PKGs are classified by the content type in the package header:

- `PSAC` (`0x1B`) — DLC with its own game data;
- `PSAL` (`0x1C`) — license-only DLC with no separate game data.

When a selected unpacked addcont tree has no PKG header, SFO `CATEGORY` is the
fallback: `ac` maps to `PSAC` and `al` maps to `PSAL`. Experimental preparation
validates `license.dat`, its `CONTENT_ID`, and the package type; a `PSAL` entry
with unexpected game data is rejected.

The entitlement label is accepted only from a three-part `CONTENT_ID` whose
final component is exactly 16 characters from `[A-Z0-9_]`. Exact duplicate
packages are excluded before the experimental layout is prepared.

## Why this is experimental

A direct overlay of a DLC package onto the application root is unsafe. An
add-on package can contain its own `sce_sys/param.sfo`, license metadata, and
other package-envelope files; replacing the game's copies would damage the
identity of the main application. The converter therefore keeps base/patch
metadata authoritative and never overlays DLC `sce_sys` metadata onto it.

For compatible games, the experimental mode instead prepares DLC data inside
the consolidated game tree and may modify **staged copies** of game executables
so the game can discover that data from its existing `/app0` image. Some DLC
contains no independent data and acts only as an entitlement; other DLC needs
a dedicated data directory. Games also differ in which executable and API path
they use. Consequently, one generic transformation cannot be guaranteed to
work for every title or add-on type.

## Safety and result status

- Source PKGs and a selected unpacked source are always read-only and remain
  byte-for-byte unchanged.
- All transformations take place below the selected temporary workspace.
- Ordinary base+patch conversion remains the default path.
- Experimental DLC must be explicitly enabled.
- Static container verification checks structure and files, not PS5 runtime
  entitlement or mount behavior.
- Until a particular image is tested on hardware, its result must remain
  `runtime_verified=false` and must not claim working DLC support.

The mode does not edit PS5 databases and does not require direct `app.db` or
`addcont.db` changes. ShadowMountPlus still receives one game image. Successful
creation of that image does **not** guarantee that the game will launch, that
the platform will register the add-ons, or that the game will expose them.

## Reference experiment

The Beat Saber CUSA12878 reference set was used to validate the proposed
single-image layout. The scan found 246 DLC PKGs; one byte-identical duplicate
was removed, leaving 245 unique entitlements. A host-side test image containing
base, patch, and the unique DLC set passed MkPFS verification and an exact deep
unpack comparison. This proves deterministic construction and container
integrity only. PS5 runtime behavior remains unverified and is not presented as
general compatibility.

> [!WARNING]
> DLC support in version 0.2.8 remains experimental and disabled by default.
> Even successful static verification does not guarantee that the game will
> start or discover `PSAC`/`PSAL` content on a PS5.

# Upstream provenance and local modifications

- Project: `idlesauce/ps4-eboot-dlc-patcher`
- Repository: <https://github.com/idlesauce/ps4-eboot-dlc-patcher>
- Audited commit: `d1d1e0f0dbd5e06da45b7d8f8ca1827d34546692`
- Upstream license: GNU GPL version 3
- Vendored/adapted: 2026-08-02

## Retained source

- the PS4 module loader classes used to read ELF dynamic metadata, symbols,
  libraries, and relocations;
- the Iced-based code scanner and PRX loader patch core;
- the complete C/assembly source of the companion PRX under `prx_src/`;
- strict entitlement validation and the `DlcInfo.FromEncodedString` format.

The `Ps4ModuleLoader` and `prx_src` files are retained from the pinned upstream
commit. `PrxLoaderStuff.cs` is modified as described below. Two loader files
also contain fail-closed nullable checks so malformed symbol tables are rejected
instead of being dereferenced.

## Removed or replaced

- all LibOrbisPkg sources and PKG/license parsing;
- Spectre.Console and all menus, prompts, confirmations, drag-and-drop behavior,
  and interactive fallbacks;
- the limited in-executable fallback implementation;
- upstream `obj/`, `bin/`, release files, and the compiled `dlcldr.prx`;
- logging or printing of raw entitlement keys.

The new `Program.cs`, `ExecutablePatcher.cs`, `DlcInfo.cs`, and `ConsoleUi.cs`
provide a deterministic JSON batch boundary. The strict path requires direct
system-module call sites and fails closed when the PRX method is not applicable.
The system-module ID is accepted only from an immediately adjacent full EDI or
RDI immediate assignment; partial-register and scan-back heuristics are rejected.
The loader and its path must fit entirely in a contiguous zero-filled code
region without crossing the next file or memory segment.

## External PRX template

The repository intentionally contains no compiled PRX. `ps4-dlc-patch.csproj`
requires `DlcPrxTemplatePath` at build time and embeds that external file as
`ps4_dlc_patch.template.prx`.

The pinned patch core expects the following fields in the corresponding signed
template:

- debug mode at file offset `0x148D0`;
- entitlement count at `0x148D4`;
- entitlement table at `0x148E0`;
- table capacity of 2,500 entries, 34 bytes per entry.

Before producing output, the helper checks template size and the upstream
sentinel values at those offsets. A differently linked PRX must not be used
without updating and re-auditing the offsets.

The retained `prx_src/build.bat` documents the upstream OpenOrbis build flow but
is not invoked by this .NET project. Generated PRX/ELF/object files are ignored
and must remain outside Git.

The retained `prx_src/printf.c` and `printf.h` include Marco Paland's tiny
printf implementation under the MIT license. Its original headers are retained
and the binary-distribution notice is copied to
`../../LICENSES/mpaland-printf-MIT.txt`.

## Dependency changes

The only managed package dependency retained from upstream is Iced 1.21.0.
Spectre.Console was replaced by a plain deterministic stderr logger. No
LibOrbisPkg package parsing code or dependency is included.

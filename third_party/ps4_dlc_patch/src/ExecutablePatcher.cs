// Modified adaptation for PS4 FFPFSC, 2026-08-02; GPL-3.0.
// Strict PRX method only; see ../UPSTREAM.md.
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;

namespace ps4_eboot_dlc_patcher;

internal sealed record PatchResult(string PatchedElf, string Prx);

internal static class ExecutablePatcher
{
    private static readonly string[] ImportantAppContentSymbols =
    [
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceAppContentGetAddcontInfoList"),
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceAppContentGetAddcontInfo"),
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceAppContentGetEntitlementKey"),
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceAppContentAddcontMount"),
    ];

    private static readonly string[] ImportantEntitlementAccessSymbols =
    [
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceNpEntitlementAccessGetAddcontEntitlementInfo"),
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceNpEntitlementAccessGetAddcontEntitlementInfoList"),
        Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceNpEntitlementAccessGetEntitlementKey"),
    ];

    public static async Task<PatchResult> PatchAsync(
        string inputPath,
        string outputDirectory,
        List<DlcInfo> dlcList)
    {
        Directory.CreateDirectory(outputDirectory);
        var outputElf = Path.Combine(outputDirectory, Path.GetFileName(inputPath));
        var outputPrx = Path.Combine(outputDirectory, "dlcldr.prx");
        if (Path.GetFullPath(outputElf).Equals(Path.GetFullPath(inputPath),
                StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Output ELF must not replace the input ELF.");
        if (File.Exists(outputElf) || File.Exists(outputPrx))
            throw new IOException("Output already exists; strict batch mode does not overwrite files.");

        var unique = Guid.NewGuid().ToString("N");
        var temporaryElf = Path.Combine(outputDirectory, $".{Path.GetFileName(inputPath)}.{unique}.partial");
        var temporaryPrx = Path.Combine(outputDirectory, $".dlcldr.prx.{unique}.partial");
        var publishedElf = false;
        var publishedPrx = false;
        var ownsTemporaryElf = false;
        var ownsTemporaryPrx = false;
        FileStream? temporaryElfStream = null;
        byte[]? prxBytes = null;

        try
        {
            List<(ulong offset, byte[] newBytes, string description)> patches;
            using (var stream = new FileStream(
                       inputPath, FileMode.Open, FileAccess.Read, FileShare.Read,
                       1024 * 1024, FileOptions.SequentialScan))
            {
                ValidateElfHeader(stream);
                using var reader = new BinaryReader(stream, Encoding.UTF8, leaveOpen: true);
                var binary = new Ps4ModuleLoader.Ps4Binary(reader);
                binary.Process(reader);

                patches = await CreateExecutablePatches(binary, stream);
                AddProgramHeaderSizePatches(binary, patches);

                prxBytes = PrxLoaderStuff.LoadUnpatchedSignedDlcldrPrx();
                foreach (var patch in PrxLoaderStuff.GetAllPatchesForSignedDlcldrPrx(dlcList))
                {
                    try
                    {
                        ApplyPatch(prxBytes, patch.offset, patch.newBytes, "PRX template");
                        ConsoleUi.LogInfo($"Prepared PRX field: {patch.description}.");
                    }
                    finally
                    {
                        CryptographicOperations.ZeroMemory(patch.newBytes);
                    }
                }

                stream.Position = 0;
                temporaryElfStream = new FileStream(
                    temporaryElf, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None);
                ownsTemporaryElf = true;
                stream.CopyTo(temporaryElfStream);
                temporaryElfStream.Flush(flushToDisk: true);
            }

            foreach (var patch in patches.OrderBy(item => item.offset))
            {
                if (patch.offset > (ulong)temporaryElfStream.Length ||
                    (ulong)patch.newBytes.Length >
                    (ulong)temporaryElfStream.Length - patch.offset)
                    throw new InvalidDataException(
                        $"ELF patch is outside file bounds: {patch.description}.");
                temporaryElfStream.Position = checked((long)patch.offset);
                temporaryElfStream.Write(patch.newBytes);
                ConsoleUi.LogInfo(
                    $"Applied ELF patch: {patch.description} at 0x{patch.offset:X}.");
            }
            temporaryElfStream.Flush(flushToDisk: true);
            temporaryElfStream.Dispose();
            temporaryElfStream = null;

            using (var output = new FileStream(
                       temporaryPrx, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                ownsTemporaryPrx = true;
                output.Write(prxBytes);
                output.Flush(flushToDisk: true);
            }

            File.Move(temporaryPrx, outputPrx, overwrite: false);
            ownsTemporaryPrx = false;
            publishedPrx = true;
            File.Move(temporaryElf, outputElf, overwrite: false);
            ownsTemporaryElf = false;
            publishedElf = true;

            ConsoleUi.LogSuccess("Strict PRX patch completed.");
            return new PatchResult(outputElf, outputPrx);
        }
        catch
        {
            temporaryElfStream?.Dispose();
            temporaryElfStream = null;
            if (ownsTemporaryElf) DeleteIfPresent(temporaryElf);
            if (ownsTemporaryPrx) DeleteIfPresent(temporaryPrx);
            if (publishedElf) DeleteIfPresent(outputElf);
            if (publishedPrx) DeleteIfPresent(outputPrx);
            throw;
        }
        finally
        {
            temporaryElfStream?.Dispose();
            if (prxBytes is not null)
                CryptographicOperations.ZeroMemory(prxBytes);
        }
    }

    private static async Task<List<(ulong offset, byte[] newBytes, string description)>>
        CreateExecutablePatches(Ps4ModuleLoader.Ps4Binary binary, FileStream stream)
    {
        var patches = new List<(ulong offset, byte[] newBytes, string description)>();
        var patchAppContent = binary.Relocations.Any(relocation =>
            relocation.SYMBOL is not null &&
            ImportantAppContentSymbols.Any(nid => relocation.SYMBOL.StartsWith(nid)));
        var patchEntitlementAccess = binary.Relocations.Any(relocation =>
            relocation.SYMBOL is not null &&
            ImportantEntitlementAccessSymbols.Any(nid => relocation.SYMBOL.StartsWith(nid)));

        if (!patchAppContent && !patchEntitlementAccess)
            throw new InvalidDataException(
                "The ELF does not import supported DLC APIs; another executable may own DLC access.");

        var loadStartNid = Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceKernelLoadStartModule");
        var loadStartRelocation = binary.Relocations.FirstOrDefault(relocation =>
            relocation.SYMBOL is not null && relocation.SYMBOL.StartsWith(loadStartNid));
        ulong? loadStartMemoryAddress = loadStartRelocation?.REAL_FUNCTION_ADDRESS;

        if (loadStartMemoryAddress is null)
        {
            var kernelRelocation = binary.Relocations.FirstOrDefault(relocation =>
                relocation.SYMBOL is not null &&
                ((relocation.LIBRARY_NAME?.Contains("kernel", StringComparison.OrdinalIgnoreCase) ?? false) ||
                 (relocation.MODULE_NAME?.Contains("kernel", StringComparison.OrdinalIgnoreCase) ?? false)));
            if (kernelRelocation?.SYMBOL is null)
                throw new InvalidDataException("No suitable libkernel import is available for strict PRX loading.");

            if (patchAppContent)
            {
                loadStartMemoryAddress = ReplaceInitializerImport(
                    binary,
                    kernelRelocation,
                    "sceAppContentInitialize",
                    loadStartNid,
                    patches);
            }
            if (loadStartMemoryAddress is null && patchEntitlementAccess)
            {
                loadStartMemoryAddress = ReplaceInitializerImport(
                    binary,
                    kernelRelocation,
                    "sceNpEntitlementAccessInitialize",
                    loadStartNid,
                    patches);
            }
        }

        if (loadStartMemoryAddress is null)
            throw new InvalidDataException("sceKernelLoadStartModule cannot be resolved safely.");

        var free = GetFreeSpaceAtEndOfCodeSegment(binary, stream);
        var code = binary.E_SEGMENTS.First(segment => segment.GetName() == "CODE");
        if (loadStartMemoryAddress.Value < code.MEM_ADDR)
            throw new InvalidDataException(
                "sceKernelLoadStartModule resolves before the code segment.");
        var loadStartFileOffset = checked(
            code.OFFSET + loadStartMemoryAddress.Value - code.MEM_ADDR);
        var loaderPatches = await PrxLoaderStuff.GetAllPatchesForExec(
            binary,
            stream,
            free.freeSpaceLength,
            free.fileStartAddressOfZeroes,
            loadStartFileOffset,
            patchAppContent,
            patchEntitlementAccess);
        patches.AddRange(loaderPatches);
        return patches;
    }

    private static ulong? ReplaceInitializerImport(
        Ps4ModuleLoader.Ps4Binary binary,
        Ps4ModuleLoader.Relocation kernelRelocation,
        string initializer,
        string loadStartNid,
        List<(ulong offset, byte[] newBytes, string description)> patches)
    {
        var initializerNid = Ps4ModuleLoader.Utils.CalculateNidForSymbol(initializer);
        var relocation = binary.Relocations.FirstOrDefault(item =>
            item.SYMBOL is not null && item.SYMBOL.StartsWith(initializerNid));
        if (relocation?.SYMBOL is null || relocation.REAL_FUNCTION_ADDRESS is null ||
            kernelRelocation.SYMBOL is null ||
            relocation.SYMBOL.Length < kernelRelocation.SYMBOL.Length)
            return null;

        var symbol = binary.Symbols.FirstOrDefault(item => item.Value?.NID == relocation.SYMBOL).Value;
        if (symbol is null || symbol.NID_FILE_ADDRESS == 0)
            return null;

        var suffixIndex = kernelRelocation.SYMBOL.IndexOf('#');
        if (suffixIndex < 0) return null;
        var suffix = kernelRelocation.SYMBOL[suffixIndex..];
        var replacement = new byte[relocation.SYMBOL.Length];
        Encoding.ASCII.GetBytes(loadStartNid, replacement);
        Encoding.ASCII.GetBytes(suffix.AsSpan(), replacement.AsSpan(loadStartNid.Length));
        patches.Add((symbol.NID_FILE_ADDRESS, replacement,
            $"{initializer} import redirected to sceKernelLoadStartModule"));
        return relocation.REAL_FUNCTION_ADDRESS;
    }

    private static void AddProgramHeaderSizePatches(
        Ps4ModuleLoader.Ps4Binary binary,
        List<(ulong offset, byte[] newBytes, string description)> patches)
    {
        foreach (var segment in binary.E_SEGMENTS.Where(item => item.GetName() == "CODE"))
        {
            var segmentMemoryEnd = checked(segment.MEM_ADDR + segment.MEM_SIZE);
            var next = binary.E_SEGMENTS
                .OrderBy(item => item.OFFSET)
                .First(item => item.MEM_ADDR >= segmentMemoryEnd);
            if (next.OFFSET <= segment.OFFSET || next.MEM_ADDR <= segment.MEM_ADDR)
                throw new InvalidDataException("Invalid code-segment ordering in ELF program headers.");

            var inSegment = patches
                .Where(item => item.offset >= segment.OFFSET && item.offset < next.OFFSET)
                .ToList();
            if (inSegment.Count == 0) continue;

            if (inSegment.Any(item =>
                    (ulong)item.newBytes.Length > next.OFFSET - item.offset))
            {
                throw new InvalidDataException(
                    "An ELF patch would cross into the next file segment.");
            }

            var newSize = inSegment.Max(item =>
                item.offset + (ulong)item.newBytes.Length - segment.OFFSET);
            var maximumFileSize = next.OFFSET - segment.OFFSET;
            var maximumMemorySize = next.MEM_ADDR - segment.MEM_ADDR;
            if (newSize > maximumFileSize || newSize > maximumMemorySize)
            {
                throw new InvalidDataException(
                    "An ELF patch would overlap the next mapped segment.");
            }
            if (newSize > segment.FILE_SIZE)
            {
                var bytes = new byte[8];
                BinaryPrimitives.WriteUInt64LittleEndian(bytes, newSize);
                patches.Add(((ulong)segment.PHT_FILE_SIZE_FIELD_FILE_OFFSET, bytes,
                    $"Increase {segment.GetName()} FILE_SIZE to 0x{newSize:X}"));
            }
            if (newSize > segment.MEM_SIZE)
            {
                var bytes = new byte[8];
                BinaryPrimitives.WriteUInt64LittleEndian(bytes, newSize);
                patches.Add(((ulong)segment.PHT_MEM_SIZE_FIELD_FILE_OFFSET, bytes,
                    $"Increase {segment.GetName()} MEM_SIZE to 0x{newSize:X}"));
            }
        }
    }

    private static (int fileStartAddressOfZeroes, int freeSpaceLength)
        GetFreeSpaceAtEndOfCodeSegment(Ps4ModuleLoader.Ps4Binary binary, Stream stream)
    {
        var code = binary.E_SEGMENTS.First(segment => segment.GetName() == "CODE");
        var codeMemoryEnd = checked(code.MEM_ADDR + code.MEM_SIZE);
        var next = binary.E_SEGMENTS
            .OrderBy(segment => segment.OFFSET)
            .First(segment => segment.MEM_ADDR >= codeMemoryEnd);
        if (next.OFFSET <= code.OFFSET ||
            code.FILE_SIZE > next.OFFSET - code.OFFSET ||
            next.OFFSET > (ulong)stream.Length)
            throw new InvalidDataException("Invalid overlapping ELF code segments.");

        var scanEnd = next.OFFSET - 1;
        ulong zeroCount = 0;
        var cursor = scanEnd;
        while (true)
        {
            stream.Position = checked((long)cursor);
            if (stream.ReadByte() != 0) break;
            zeroCount++;
            if (cursor == code.OFFSET) break;
            cursor--;
        }
        if (zeroCount == 0)
            throw new InvalidDataException("No free space is available at the end of the code segment.");

        var start = scanEnd - zeroCount + 1;
        return (checked((int)start), checked((int)zeroCount));
    }

    private static void ValidateElfHeader(Stream stream)
    {
        Span<byte> header = stackalloc byte[6];
        stream.ReadExactly(header);
        if (!header[..4].SequenceEqual(new byte[] { 0x7f, (byte)'E', (byte)'L', (byte)'F' }) ||
            header[4] != 2 || header[5] != 1)
            throw new InvalidDataException("Input is not a little-endian 64-bit ELF.");
        stream.Position = 0;
    }

    private static void ApplyPatch(byte[] target, ulong offset, byte[] bytes, string name)
    {
        if (offset > (ulong)target.Length || (ulong)bytes.Length > (ulong)target.Length - offset)
            throw new InvalidDataException($"{name} is incompatible with the expected patch offsets.");
        bytes.CopyTo(target.AsSpan(checked((int)offset), bytes.Length));
    }

    private static void DeleteIfPresent(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch
        {
            // Preserve the original failure; partial paths remain visibly suffixed.
        }
    }
}

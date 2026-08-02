// Modified for PS4 FFPFSC on 2026-08-02: strict non-interactive PRX path only.
// Based on idlesauce/ps4-eboot-dlc-patcher; GPL-3.0. See ../UPSTREAM.md.
using Iced.Intel;
using System.Buffers.Binary;
using System.Diagnostics;
using System.Text;

namespace ps4_eboot_dlc_patcher;
internal static class PrxLoaderStuff
{
    private const string PRX_PATH = "/app0/dlcldr.prx";

    private static readonly string[] libSceAppContentSymbols = [
        // "sceAppContentInitialize", // this is handled explicitly
        "sceAppContentGetAddcontInfo",
        "sceAppContentGetAddcontInfoList",
        "sceAppContentGetEntitlementKey",
        "sceAppContentAddcontMount",
        "sceAppContentAddcontUnmount",
        "sceAppContentAddcontDelete",
        "sceAppContentAppParamGetInt",
        "sceAppContentAddcontEnqueueDownload",
        "sceAppContentTemporaryDataMount2",
        "sceAppContentTemporaryDataUnmount",
        "sceAppContentTemporaryDataFormat",
        "sceAppContentTemporaryDataGetAvailableSpaceKb",
        "sceAppContentDownloadDataFormat",
        "sceAppContentDownloadDataGetAvailableSpaceKb",
        "sceAppContentGetAddcontDownloadProgress",
        "sceAppContentAddcontEnqueueDownloadByEntitlemetId",
        "sceAppContentAddcontEnqueueDownloadSp",
        "sceAppContentAddcontMountByEntitlemetId",
        "sceAppContentAddcontShrink",
        "sceAppContentAppParamGetString",
        "sceAppContentDownload0Expand",
        "sceAppContentDownload0Shrink",
        "sceAppContentDownload1Expand",
        "sceAppContentDownload1Shrink",
        "sceAppContentGetAddcontInfoByEntitlementId",
        "sceAppContentGetAddcontInfoListByIroTag",
        "sceAppContentGetDownloadedStoreCountry",
        "sceAppContentGetPftFlag",
        "sceAppContentGetRegion",
        "sceAppContentRequestPatchInstall",
        "sceAppContentSmallSharedDataFormat",
        "sceAppContentSmallSharedDataGetAvailableSpaceKb",
        "sceAppContentSmallSharedDataMount",
        "sceAppContentSmallSharedDataUnmount",
    ];

    private const string newModuleAndLibraryName = "dlcldr";
    private const string fakeAppContentFunctionPrefix = "dlcldr_";
    internal static async Task<List<(ulong offset, byte[] newBytes, string description)>>
        GetAllPatchesForExec(
            Ps4ModuleLoader.Ps4Binary binary,
            FileStream fs,
            int freeSpaceAtEnd,
            int fileOffsetOfFreeSpaceStart,
            ulong sceKernelLoadStartModuleFunctionEntryFileOffset,
            bool patchAppContent,
            bool patchEntitlementAcces)
    {
        if (!patchAppContent && !patchEntitlementAcces)
        { throw new UnreachableException("No patches selected"); }

        List<(ulong offset, byte[] newBytes, string description)> patches = new();

        // since in the prx loader we're using relative addressing, it doesnt matter that these addresses are relative to file start not mem start
        // all that matters is the addresses passed are relative to the same start
        uint prxLoaderEntryFileAddr = checked((uint)fileOffsetOfFreeSpaceStart);
        uint prxPathStrAddr = checked(prxLoaderEntryFileAddr + (uint)PrxLoaderLength);
        byte[] prxLoaderBytes = GetPrxLoaderAsmBytes(
            prxLoaderEntryFileAddr,
            checked((uint)sceKernelLoadStartModuleFunctionEntryFileOffset),
            prxPathStrAddr);
        byte[] prxPathBytes = Encoding.ASCII.GetBytes(PRX_PATH + "\0");
        var requiredFreeSpace = checked(prxLoaderBytes.Length + prxPathBytes.Length);
        if (freeSpaceAtEnd < requiredFreeSpace)
        {
            throw new InvalidDataException(
                $"Strict PRX method requires {requiredFreeSpace} contiguous zero bytes " +
                $"at the end of the code segment; only {freeSpaceAtEnd} are available.");
        }

        patches.Add((prxLoaderEntryFileAddr, prxLoaderBytes, "PRX Loader"));

        var codeSegment = binary.E_SEGMENTS.First(x => x.GetName() == "CODE"); // throws if not found

        if ((ulong)prxLoaderEntryFileAddr < codeSegment.OFFSET)
            throw new InvalidDataException("PRX loader location is before the code segment.");
        uint prxLoaderEntryMemAddr = checked((uint)(
            codeSegment.MEM_ADDR + (ulong)prxLoaderEntryFileAddr - codeSegment.OFFSET));

        patches.Add((prxPathStrAddr, prxPathBytes, "PRX Path"));

        // here we have everything needed for the prx loader done
        // but we're still not calling it, so do that next

        // we need xrefs to sceAppContentInitialize bc we'll patch calls to it out (or redirect to the prx loader if sceSysmoduleLoadModule(0xB4) isnt found),
        // so we can use the function entry for other stuff (like replacing it with sceKernelLoadStartModule)
        // also find xrefs to sceSysmoduleLoadModule (to find 0xb4, which loads libSceAppContent) so we can load the prx instead

        // first im trying to load prx at sceSysmoduleLoadModule(0xB4) just in case the game calls another function from libSceAppContent before initialize
        // in which case the game would crash, tho this is unlikely. Normally if a function is called without init first it returns an
        // SCE_APP_CONTENT_ERROR_NOT_INITIALIZED error, so its feasable the game would call init only after this error code is seen ig

        List<(string symbol, ulong? funcPtr, List<Instruction> xrefs)> symbolsWithXrefs = new();

        if (patchAppContent)
        {
            symbolsWithXrefs.Add(("sceAppContentInitialize", binary.Relocations.SingleOrDefault(x => x.SYMBOL is not null && x.SYMBOL.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceAppContentInitialize")))?.REAL_FUNCTION_ADDRESS, new()));
        }
        if (patchEntitlementAcces)
        {
            symbolsWithXrefs.Add(("sceNpEntitlementAccessInitialize", binary.Relocations.SingleOrDefault(x => x.SYMBOL is not null && x.SYMBOL.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceNpEntitlementAccessInitialize")))?.REAL_FUNCTION_ADDRESS, new()));
        }

        // Handle this separately because strict mode must prove the immediate
        // argument at the direct call site.
        // we only care about sceSysmoduleLoadModule(0xB4) and sceSysmoduleLoadModule(0x113) (entitlementaccess)
        // https://www.psdevwiki.com/ps5/Libraries
        (string symbol, ulong? funcPtr, List<(Instruction instruction, uint rdiImm)> xrefs) sceSysmoduleLoadModuleXRefs = ("sceSysmoduleLoadModule", binary.Relocations.SingleOrDefault(x => x.SYMBOL is not null && x.SYMBOL.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("sceSysmoduleLoadModule")))?.REAL_FUNCTION_ADDRESS, new());

        var reader = new StreamCodeReader(fs);
        fs.Seek((long)codeSegment.OFFSET, SeekOrigin.Begin);

        var decoder = Iced.Intel.Decoder.Create(64, reader);
        decoder.IP = codeSegment.MEM_ADDR;
        Instruction? previousInstruction = null;

        var progress = new ConsoleUi.PercentProgressBar("Analyzing code segment");

        ulong memAddrPlusFileSize = checked(codeSegment.MEM_ADDR + codeSegment.FILE_SIZE);
        while (decoder.IP < memAddrPlusFileSize)
        {
            await progress.Update((double)((double)(decoder.IP - codeSegment.MEM_ADDR) / (double)codeSegment.FILE_SIZE) * 100);

            decoder.Decode(out var instr);

            if (instr.Code == Code.Call_rel32_64 || instr.Code == Code.Jmp_rel32_64)
            {
                foreach (var (symbol, funcPtr, xrefs) in symbolsWithXrefs)
                {
                    if (instr.NearBranchTarget != funcPtr)
                    { continue; }

                    ConsoleUi.LogInfo($"Found call to {symbol} at 0x{instr.IP:X}");

                    xrefs.Add(instr);
                }


                // handle sceSysmoduleLoadModule(0xB4) explicitly
                if (instr.NearBranchTarget == sceSysmoduleLoadModuleXRefs.funcPtr)
                {
                    if (TryGetDirectSysmoduleId(previousInstruction, out var moduleId) &&
                        moduleId is 0xb4 or 0x113)
                    {
                        ConsoleUi.LogInfo(
                            $"Verified direct sceSysmoduleLoadModule(0x{moduleId:X}) call " +
                            $"at 0x{instr.IP:X}.");
                        sceSysmoduleLoadModuleXRefs.xrefs.Add((instr, moduleId));
                    }
                }
            }

            previousInstruction = instr;
        }

        await progress.Update(100);

        // here we have all calls to sceAppContentInitialize
        // and hopefully also sceSysmoduleLoadModule(0xB4)

        // first lets check if we need to patch out calls to sceAppContentInitialize
        // or redirect them to the prx loader if sceSysmoduleLoadModule(0xB4) isnt found

        // if sceSysmoduleLoadModule(0xB4) isnt found it means that sceSysmoduleLoadModule takes a variable (likely loops through a static list)
        // its okay if the game loads sceSysmoduleLoadModule(0xB4) since we need it in the prx anyway

        // im guessing sceSysmoduleLoadModule would return an error status code if the module is already loaded
        // since in this scenario we're loading the prx at sceAppContentInitialize, only we would get this error inside the prx not the game
        // TODO: make sure the dlcldr prx ignores this error 

        // A game could exist where this binary calls functions from libSceAppContent but loads and initializes in another binary
        // this is such an edge case that ill just ignore it until i know of a game that does this

        // if (symbolsWithXrefs.First(x => x.symbol == "sceAppContentInitialize").xrefs.Count == 0)
        // { throw new Exception("No references found for sceAppContentInitialize."); }

        if (patchAppContent)
        {
            if (sceSysmoduleLoadModuleXRefs.xrefs.Count(x => x.rdiImm == 0xb4) == 0)
            {
                throw new InvalidDataException(
                    "Strict PRX method requires a direct sceSysmoduleLoadModule(0xB4) call; unsafe initializer fallback is disabled.");
            }
            else
            {
                // we found sceSysmoduleLoadModule(0xB4) so we can load the prx there
                foreach (var xref in sceSysmoduleLoadModuleXRefs.xrefs.Where(x => x.rdiImm == 0xb4))
                {
                    // before, while searching for xrefs we only added E8 and E9 opcodes
                    // so we're always dealing with 5 bytes, and we can skip the first one, we only need to change the offset
                    byte[] newBytes = new byte[4];
                    BinaryPrimitives.WriteInt32LittleEndian(
                        newBytes,
                        GetRelativeBranchDisplacement(
                            prxLoaderEntryMemAddr,
                            xref.instruction.IP + (ulong)xref.instruction.Length));
                    patches.Add(((xref.instruction.IP - codeSegment.MEM_ADDR) + 1 + codeSegment.OFFSET, newBytes, "sceSysmoduleLoadModule(0xB4) to prx loader"));
                }

                // patch out sceAppContentInitialize calls
                foreach (var xref in symbolsWithXrefs.First(x => x.symbol == "sceAppContentInitialize").xrefs)
                {
                    // we know its always 5 bytes
                    byte[] newBytes = new byte[5];
                    if (xref.Code == Code.Call_rel32_64)
                    {
                        newBytes = [0xB8, 0x00, 0x00, 0x00, 0x00];
                    }
                    else if (xref.Code == Code.Jmp_rel32_64)
                    {
                        newBytes = [0x31, 0xC0, 0x90, 0x90, 0xC3];
                    }
                    else
                    {
                        throw new UnreachableException("Unknown opcode");
                    }
                    patches.Add(((xref.IP - codeSegment.MEM_ADDR) + codeSegment.OFFSET, newBytes, "patch out call to sceAppContentInitialize"));
                }

            }
        }

        if (patchEntitlementAcces)
        {
            if (sceSysmoduleLoadModuleXRefs.xrefs.Count(x => x.rdiImm == 0x113) == 0)
            {
                throw new InvalidDataException(
                    "Strict PRX method requires a direct sceSysmoduleLoadModule(0x113) call; unsafe initializer fallback is disabled.");
            }
            else
            {
                // we found sceSysmoduleLoadModule(0x113) so we can load the prx there
                foreach (var xref in sceSysmoduleLoadModuleXRefs.xrefs.Where(x => x.rdiImm == 0x113))
                {
                    // before, while searching for xrefs we only added E8 and E9 opcodes
                    // so we're always dealing with 5 bytes, and we can skip the first one, we only need to change the offset
                    byte[] newBytes = new byte[4];
                    BinaryPrimitives.WriteInt32LittleEndian(
                        newBytes,
                        GetRelativeBranchDisplacement(
                            prxLoaderEntryMemAddr,
                            xref.instruction.IP + (ulong)xref.instruction.Length));
                    patches.Add(((xref.instruction.IP - codeSegment.MEM_ADDR) + 1 + codeSegment.OFFSET, newBytes, "sceSysmoduleLoadModule(0x113) to prx loader"));
                }

                // patch out sceNpEntitlementAccessInitialize calls
                foreach (var xref in symbolsWithXrefs.First(x => x.symbol == "sceNpEntitlementAccessInitialize").xrefs)
                {
                    // we know its always 5 bytes
                    byte[] newBytes = new byte[5];
                    if (xref.Code == Code.Call_rel32_64)
                    {
                        newBytes = [0xB8, 0x00, 0x00, 0x00, 0x00];
                    }
                    else if (xref.Code == Code.Jmp_rel32_64)
                    {
                        newBytes = [0x31, 0xC0, 0x90, 0x90, 0xC3];
                    }
                    else
                    {
                        throw new UnreachableException("Unknown opcode");
                    }
                    patches.Add(((xref.IP - codeSegment.MEM_ADDR) + codeSegment.OFFSET, newBytes, "patch out call to sceNpEntitlementAccessInitialize"));
                }

            }
        }

        List<string> moduleNamesToReplaceWithDlcldr = new();

        if (patchAppContent)
        {
            moduleNamesToReplaceWithDlcldr.Add("libSceAppContentUtil");
        }
        if (patchEntitlementAcces)
        {
            moduleNamesToReplaceWithDlcldr.Add("libSceNpEntitlementAccess");
        }

        // https://github.com/OpenOrbis/create-fself/blob/9b72c778eeafddfc00a6c443debed925dd2af605/pkg/oelf/OELFStrangeLibs.go#L119
        List<string> libraryNamesToReplaceWithDlcldr = new();

        if (patchAppContent)
        {
            libraryNamesToReplaceWithDlcldr.AddRange(
            [
                "libSceAppContent",
                "libSceAppContentBundle",
                "libSceAppContentIro",
                "libSceAppContentPft",
                "libSceAppContentSc",
            ]);
        }
        if (patchEntitlementAcces)
        {
            libraryNamesToReplaceWithDlcldr.AddRange(
            [
                "libSceNpEntitlementAccess",
                "libSceNpEntitlementAccessPft",
            ]);
        }


        // at this point we have everything done for loading the prx
        // next patch the module and library symbols from libSceAppContent to dlcldr
        // also patch the nids (since for now the prx uses dynamic linking to resolve the real functions from libSceAppContent, and the fake functions would conflict with the real ones)

        // throws error if any module/library not found
        foreach (var moduleName in moduleNamesToReplaceWithDlcldr)
        {
            // have to do it like this bc firstordefault doesnt return null if not found since the result is a value type
            bool moduleFound = binary.Modules.Any(x => x.Value.name is not null && x.Value.name.Equals(moduleName, StringComparison.InvariantCultureIgnoreCase));
            if (!moduleFound)
            { throw new Exception($"Module {moduleName} not found"); }

            var module = binary.Modules.First(x => x.Value.name is not null && x.Value.name.Equals(moduleName, StringComparison.InvariantCultureIgnoreCase));
            if (module.Value.stringFileOffset is null)
            { throw new Exception($"Module {moduleName} stringFileOffset is null"); }

            byte[] newModuleNameString = new byte[module.Value.name!.Length]; // ! = cannot be null bc we used name to find this item
            // the bytes after moduleName are already zeroes
            Encoding.UTF8.GetBytes(newModuleAndLibraryName, newModuleNameString);

            patches.Add((module.Value.stringFileOffset.Value, newModuleNameString, $"Module {moduleName} name patch"));
        }

        int patchedLibrariesCount = 0;
        foreach (var libraryName in libraryNamesToReplaceWithDlcldr)
        {
            bool libraryFound = binary.Libraries.Any(x => x.Value.name is not null && x.Value.name.Equals(libraryName, StringComparison.InvariantCultureIgnoreCase));
            if (!libraryFound)
            { continue; }

            var library = binary.Libraries.First(x => x.Value.name is not null && x.Value.name.Equals(libraryName, StringComparison.InvariantCultureIgnoreCase));
            if (library.Value.stringFileOffset is null)
            { throw new Exception($"Library {libraryName} stringFileOffset is null"); }

            byte[] newLibraryNameString = new byte[library.Value.name!.Length]; // ! = cannot be null bc we used name to find this item
            // the bytes after libraryName are already zeroes
            Encoding.UTF8.GetBytes(newModuleAndLibraryName, newLibraryNameString);

            patches.Add((library.Value.stringFileOffset.Value, newLibraryNameString, $"Library {libraryName} name patch"));
            patchedLibrariesCount++;
        }

        if (patchedLibrariesCount == 0)
        { throw new Exception("No libraries patched"); }

        // fake handlers in prx for libSceNpEntitlementAccess have the original nids so no need for these patches
        if (patchAppContent)
        {
            int patchedNidsCount = 0;
            foreach (var symbol in libSceAppContentSymbols)
            {
                string realNid = Ps4ModuleLoader.Utils.CalculateNidForSymbol(symbol);
                string fakeNid = Ps4ModuleLoader.Utils.CalculateNidForSymbol(fakeAppContentFunctionPrefix + symbol);

                bool symbolFound = binary.Symbols.Any(x => x.Value?.NID is not null && x.Value.NID.StartsWith(realNid));
                if (!symbolFound)
                { continue; }

                var realSymbol = binary.Symbols.First(x => x.Value?.NID is not null && x.Value.NID.StartsWith(realNid));

                if (realSymbol.Value?.NID_FILE_ADDRESS is null || realSymbol.Value?.NID_FILE_ADDRESS == default(ulong))
                { throw new Exception($"Symbol {symbol} nidFileAddress is null"); }

                byte[] newNidBytes = Encoding.UTF8.GetBytes(fakeNid);
                patches.Add((realSymbol.Value!.NID_FILE_ADDRESS, newNidBytes, $"Symbol {symbol} nid patch"));

                patchedNidsCount++;
            }

            if (patchedNidsCount == 0)
            { throw new Exception("No nids patched"); }

            ConsoleUi.LogInfo($"Patched {patchedNidsCount} nids");
        }

        return patches;
    }

    private const string TemplateResourceName = "ps4_dlc_patch.template.prx";

    internal static byte[] LoadUnpatchedSignedDlcldrPrx()
    {
        var assembly = System.Reflection.Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream(TemplateResourceName)
            ?? throw new InvalidDataException(
                "The build does not contain the externally supplied PRX template.");
        using var memory = new MemoryStream();
        stream.CopyTo(memory);
        var template = memory.ToArray();
        ValidateTemplate(template);
        return template;
    }

    // these are offsets in the SIGNED prx
    private const int DLCLDR_PRX_DEBUG_MODE_OFFSET = 0x148D0;
    private const int DLCLDR_PRX_ADDCONT_COUNT_OFFSET = 0x148D4;
    private const int DLCLDR_PRX_ADDCONT_LIST_OFFSET = 0x148E0;
    internal static List<(ulong offset, byte[] newBytes, string description)> GetAllPatchesForSignedDlcldrPrx(List<DlcInfo> dlcList, int debugMode = 0)
    {
        if (dlcList.Count is < 1 or > DlcInfo.MaximumCount)
            throw new InvalidDataException(
                $"DLC count must be between 1 and {DlcInfo.MaximumCount}.");

        var patches = new List<(ulong offset, byte[] newBytes, string description)>();

        byte[] debugModeBytes = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(debugModeBytes, debugMode);
        patches.Add((DLCLDR_PRX_DEBUG_MODE_OFFSET, debugModeBytes, $"Debug Mode: {(debugMode != 0 ? "Enabled" : "Disabled")}"));

        byte[] addcontCountBytes = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(addcontCountBytes, dlcList.Count);
        patches.Add((DLCLDR_PRX_ADDCONT_COUNT_OFFSET, addcontCountBytes, $"DLC Count: {dlcList.Count}"));

        int dlcListItemSize = 17 + 1 + 16;
        byte[] addcontListBytes = new byte[dlcList.Count * dlcListItemSize];

        for (int i = 0; i < dlcList.Count; i++)
        {
            // first 16 bytes are the entitlement label, since the byte array is already zeroed itll implicitly be null terminated
            Array.Copy(Encoding.ASCII.GetBytes(dlcList[i].EntitlementLabel), 0, addcontListBytes, i * dlcListItemSize, 16);

            // status byte
            addcontListBytes[i * dlcListItemSize + 17] = (byte)dlcList[i].Type;

            dlcList[i].EntitlementKey.AsSpan().CopyTo(addcontListBytes.AsSpan(i * dlcListItemSize + 18, 16));
        }

        patches.Add((DLCLDR_PRX_ADDCONT_LIST_OFFSET, addcontListBytes, "DLC List"));

        return patches;
    }

    private static void ValidateTemplate(byte[] template)
    {
        const int itemSize = 34;
        var requiredSize = DLCLDR_PRX_ADDCONT_LIST_OFFSET +
            DlcInfo.MaximumCount * itemSize;
        if (template.Length < requiredSize)
            throw new InvalidDataException(
                "PRX template is too small for the expected entitlement table.");

        if (!template.AsSpan(DLCLDR_PRX_DEBUG_MODE_OFFSET, 8)
                .SequenceEqual(new byte[] { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff }) ||
            !template.AsSpan(DLCLDR_PRX_ADDCONT_LIST_OFFSET, 16)
                .SequenceEqual(Encoding.ASCII.GetBytes("0000000000000000")) ||
            template[DLCLDR_PRX_ADDCONT_LIST_OFFSET + 17] != 4)
        {
            throw new InvalidDataException(
                "PRX template does not match the audited upstream patch layout.");
        }
    }




#if DEBUG
    public static void PrintRequiredOffsetsForDlcldrPrx(string unsignedPrxPath)
    {
        using var fs = new FileStream(unsignedPrxPath, FileMode.Open, FileAccess.Read, FileShare.Read);

        var binary = new Ps4ModuleLoader.Ps4Binary(fs);
        using var br = new BinaryReader(fs);
        binary.Process(br);

        Console.WriteLine($"DEBUG_MODE: {binary.Symbols.First(x => x.Value?.NID is not null && x.Value.NID.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("DEBUG_MODE"))).Value!.GetFileAddressOfValue(binary):X}");
        Console.WriteLine($"addcont_count: {binary.Symbols.First(x => x.Value?.NID is not null && x.Value.NID.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("addcont_count"))).Value!.GetFileAddressOfValue(binary):X}");
        Console.WriteLine($"addcontInfo: {binary.Symbols.First(x => x.Value?.NID is not null && x.Value.NID.StartsWith(Ps4ModuleLoader.Utils.CalculateNidForSymbol("addcontInfo"))).Value!.GetFileAddressOfValue(binary):X}");

    }
#endif

    private static int PrxLoaderLength => GetPrxLoaderAsmBytes(0, 0, 0).Length;

    private static bool TryGetDirectSysmoduleId(
        Instruction? previousInstruction,
        out uint moduleId)
    {
        moduleId = 0;
        if (previousInstruction is not { } instruction)
            return false;

        // Writing EDI defines the complete 32-bit argument and zero-extends RDI.
        // DI/DIL writes are intentionally rejected because the upper bits would
        // retain an unknown value. Requiring adjacency also rejects intervening
        // register writes, calls, branches, and indirect argument setup.
        if (instruction.Code == Code.Mov_r32_imm32 &&
            instruction.Op0Register == Register.EDI)
        {
            moduleId = instruction.Immediate32;
            return true;
        }

        if (instruction.Code == Code.Mov_r64_imm64 &&
            instruction.Op0Register == Register.RDI &&
            instruction.Immediate64 <= uint.MaxValue)
        {
            moduleId = (uint)instruction.Immediate64;
            return true;
        }

        return false;
    }

    private static int GetRelativeBranchDisplacement(ulong target, ulong nextInstruction)
    {
        if (target > long.MaxValue || nextInstruction > long.MaxValue)
            throw new InvalidDataException("Branch address is outside the supported range.");
        var displacement = (long)target - (long)nextInstruction;
        if (displacement is < int.MinValue or > int.MaxValue)
            throw new InvalidDataException("PRX loader branch exceeds the rel32 range.");
        return (int)displacement;
    }

    private static byte[] GetPrxLoaderAsmBytes(uint rip, uint sceKernelLoadStartModuleAddr, uint prxPathStrAddr)
    {
        // lea rdi, [rip+prxPathStrAddr]
        // xor rsi, rsi
        // xor rdx, rdx
        // xor rcx, rcx
        // xor r8, r8
        // xor r9, r9
        // call sceKernelLoadStartModule
        // xor eax, eax
        // ret
        byte[] prxPathStrAddrOffsetLittleEndian = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(
            prxPathStrAddrOffsetLittleEndian,
            GetRelativeBranchDisplacement(prxPathStrAddr, checked(rip + 7u)));
        byte[] sceKernelLoadStartModuleCallOffsetLittleEndian = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(
            sceKernelLoadStartModuleCallOffsetLittleEndian,
            GetRelativeBranchDisplacement(
                sceKernelLoadStartModuleAddr,
                checked(rip + 27u)));
        return new byte[] { 0x48, 0x8D, 0x3D }.Concat(prxPathStrAddrOffsetLittleEndian).Concat(new byte[] { 0x48, 0x31, 0xF6, 0x48, 0x31, 0xD2, 0x48, 0x31, 0xC9, 0x4D, 0x31, 0xC0, 0x4D, 0x31, 0xC9, 0xE8 }).Concat(sceKernelLoadStartModuleCallOffsetLittleEndian).Concat(new byte[] { 0x31, 0xC0, 0xC3 }).ToArray();
    }

}

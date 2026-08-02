// Locally hardened for strict nullable validation; GPL-3.0. See ../../UPSTREAM.md.

namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
public class Relocation
{
    public enum RelocationCode
    {
        R_X86_64_NONE = 0x0,
        R_X86_64_64 = 0x1,
        R_X86_64_PC32 = 0x2,
        R_X86_64_GOT32 = 0x3,
        R_X86_64_PLT32 = 0x4,
        R_X86_64_COPY = 0x5,
        R_X86_64_GLOB_DAT = 0x6,
        R_X86_64_JUMP_SLOT = 0x7,
        R_X86_64_RELATIVE = 0x8,
        R_X86_64_GOTPCREL = 0x9,
        R_X86_64_32 = 0xA,
        R_X86_64_32S = 0xB,
        R_X86_64_16 = 0xC,
        R_X86_64_PC16 = 0xD,
        R_X86_64_8 = 0xE,
        R_X86_64_PC8 = 0xF,
        R_X86_64_DTPMOD64 = 0x10,
        R_X86_64_DTPOFF64 = 0x11,
        R_X86_64_TPOFF64 = 0x12,
        R_X86_64_TLSGD = 0x13,
        R_X86_64_TLSLD = 0x14,
        R_X86_64_DTPOFF32 = 0x15,
        R_X86_64_GOTTPOFF = 0x16,
        R_X86_64_TPOFF32 = 0x17,
        R_X86_64_PC64 = 0x18,
        R_X86_64_GOTOFF64 = 0x19,
        R_X86_64_GOTPC32 = 0x1A,
        R_X86_64_GOT64 = 0x1B,
        R_X86_64_GOTPCREL64 = 0x1C,
        R_X86_64_GOTPC64 = 0x1D,
        R_X86_64_GOTPLT64 = 0x1E,
        R_X86_64_PLTOFF64 = 0x1F,
        R_X86_64_SIZE32 = 0x20,
        R_X86_64_SIZE64 = 0x21,
        R_X86_64_GOTPC32_TLSDESC = 0x22,
        R_X86_64_TLSDESC_CALL = 0x23,
        R_X86_64_TLSDESC = 0x24,
        R_X86_64_IRELATIVE = 0x25,
        R_X86_64_RELATIVE64 = 0x26,
        R_X86_64_ORBIS_GOTPCREL_LOAD = 0x28
    }

    public ulong OFFSET { get; private set; }
    public ulong INFO { get; private set; }
    public ulong ADDEND { get; private set; }
    public string? SYMBOL { get; private set; }
    public ulong? REAL_FUNCTION_ADDRESS { get; private set; }
    public ulong REAL_FUNCTION_ADDRESS_FILE(Ps4Binary bin)
    {
        if (REAL_FUNCTION_ADDRESS == null) { throw new Exception("REAL_FUNCTION_ADDRESS is null"); }
        var segmentContainingRealFunction = bin.E_SEGMENTS.First(x => x.MEM_ADDR <= REAL_FUNCTION_ADDRESS && x.MEM_ADDR + x.MEM_SIZE > REAL_FUNCTION_ADDRESS);
        return segmentContainingRealFunction.OFFSET + (REAL_FUNCTION_ADDRESS.Value - segmentContainingRealFunction.MEM_ADDR);
    }
    public string? LIBRARY_NAME { get; private set; }
    public string? MODULE_NAME { get; private set; }

    /// <summary>
    /// REQUIRES READER TO BE AT THE START OF THE ENTRY FOR THE RELOCATION
    /// </summary>
    /// <param name="reader"></param>
    public Relocation(BinaryReader reader)
    {
        OFFSET = reader.ReadUInt64();
        INFO = reader.ReadUInt64();
        ADDEND = reader.ReadUInt64();
    }

    public string GetRelocationTypeString()
    {
        return Enum.GetName(typeof(RelocationCode), (int)INFO) ?? "Missing PS4 Relocation Type!!!";
    }

    // TODO: !!
    public void Process(Ps4ModuleLoader.Ps4Binary binary, IReadOnlyDictionary<string, string>? nids = null)
    {
        //string symbol = string.Empty;
        if (INFO > (ulong)RelocationCode.R_X86_64_ORBIS_GOTPCREL_LOAD)
        {
            //var index = INFO >> 32;
            INFO &= 0xFF;
            //if ((RelocationCode)INFO == RelocationCode.R_X86_64_64)
            //{
            //    index += ADDEND;
            //}
            //if ((RelocationCode)INFO != RelocationCode.R_X86_64_DTPMOD64)
            //{
            //    symbol = binary.Symbols.ElementAt((int)index - 2).Value.NID;
            //}
        }

        //if (GetRelocationTypeString() == "R_X86_64_RELATIVE")
        //{

        //}
        //else if (GetRelocationTypeString() == "R_X86_64_DTPMOD64" || GetRelocationTypeString() == "R_X86_64_DTPOFF64")
        //{

        //}
        //else
        //{

        //}


    }

    // This isnt a complete list but from what ive seen so far only need 0x68
    private static readonly byte[][] PUSH_OPCODES =
    [
        [0x6A], // push imm8
        [0x68], // push imm16/32
        [0x50], // push rax
        [0x51], // push rcx
        [0x52], // push rdx
        [0x53], // push rbx
        [0x54], // push rsp
        [0x55], // push rbp
        [0x56], // push rsi
        [0x57], // push rdi
        [0x41, 0x50], // push r8
        [0x41, 0x51], // push r9
        [0x41, 0x52], // push r10
        [0x41, 0x53], // push r11
        [0x41, 0x54], // push r12
        [0x41, 0x55], // push r13
        [0x41, 0x56], // push r14
        [0x41, 0x57], // push r15
        [0xFF, 0x30], // push qword ptr [rax]
        [0xFF, 0x31], // push qword ptr [rcx]
        [0xFF, 0x32], // push qword ptr [rdx]
        [0xFF, 0x33], // push qword ptr [rbx]
        [0xFF, 0x34, 0x24], // push qword ptr [rsp]
        [0xFF, 0x75, 0x00], // push qword ptr [rbp]
        [0xFF, 0x36], // push qword ptr [rsi]
        [0xFF, 0x37], // push qword ptr [rdi]
        [0x41, 0xFF, 0x30], // push qword ptr [r8]
        [0x41, 0xFF, 0x31], // push qword ptr [r9]
        [0x41, 0xFF, 0x32], // push qword ptr [r10]
        [0x41, 0xFF, 0x33], // push qword ptr [r11]
        [0x41, 0xFF, 0x34, 0x24], // push qword ptr [r12]
        [0x41, 0xFF, 0x35, 0x00], // push qword ptr [r13]
        [0x41, 0xFF, 0x36], // push qword ptr [r14]
        [0x41, 0xFF, 0x37], // push qword ptr [r15]
    ];

    //# PS4 Base64 Alphabet
    private const string base64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-";
    private static readonly Dictionary<char, int> alphabet = base64.Select((c, i) => (c, i)).ToDictionary(t => t.c, t => t.i);


    public void Resolve(BinaryReader reader, Ps4ModuleLoader.Ps4Binary binary, Dictionary<string, string>? nids = null)
    {
        var symbol = string.Empty;
        if (INFO > (ulong)RelocationCode.R_X86_64_ORBIS_GOTPCREL_LOAD)
        {
            var index = INFO >> 32;
            INFO &= 0xFF;
            symbol = binary.Symbols.ElementAt((int)index - 2).Value?.NID
                ?? throw new InvalidDataException("Relocation symbol is missing.");
        }
        SYMBOL = symbol;

        {
            // bzQExy189ZI#q#q
            var nidParts = symbol.Split('#');
            if (nidParts.Length != 3)
            { throw new Exception("Invalid NID format"); }

            var libraryIdEncoded = nidParts[1];
            int libraryId = 0;
            foreach (char c in libraryIdEncoded)
            {
                libraryId = libraryId * 64 + alphabet[c];
            }

            bool libraryFound = binary.Libraries.Any(x => x.Value.id == libraryId);
            if (!libraryFound)
            {
                throw new Exception("Library not found");
            }

            LIBRARY_NAME = binary.Libraries.First(x => x.Value.id == libraryId).Value.name;


            var moduleIdEncoded = nidParts[2];
            int moduleId = 0;
            foreach (char c in moduleIdEncoded)
            {
                moduleId = moduleId * 64 + alphabet[c];
            }

            bool moduleFound = binary.Modules.Any(x => x.Value.id == moduleId);
            if (!moduleFound)
            {
                throw new Exception("Module not found");
            }

            MODULE_NAME = binary.Modules.First(x => x.Value.id == moduleId).Value.name;
        }





        // Function Name (Offset) == Symbol Value + AddEnd (S + A)
        // Library Name  (Offset) == Symbol Value (S)

        // Resolve the NID...
        var t_pos = reader.BaseStream.Position;

        // get segment that contains the relocation
        var relocSegment = binary.E_SEGMENTS.First(x => x.MEM_ADDR <= OFFSET && x.MEM_ADDR + x.MEM_SIZE > OFFSET);
        // get the real file offset of this segment
        var fileOffset = OFFSET - (relocSegment.MEM_ADDR - relocSegment.OFFSET);
        // seek to the file offset, and read the real address
        reader.BaseStream.Seek((long)fileOffset, SeekOrigin.Begin);
        var real = reader.ReadUInt64();
        // get the segment that contains the real address
        var realSegment = binary.E_SEGMENTS.First(x => x.MEM_ADDR <= real && x.MEM_ADDR + x.MEM_SIZE > real);
        // get the real file offset
        var realFileOffset = real - (realSegment.MEM_ADDR - realSegment.OFFSET);
        // seek to the real file offset, and read the real bytes
        reader.BaseStream.Seek((long)realFileOffset, SeekOrigin.Begin);
        var real_bytes = reader.ReadBytes(8);
        // reset the reader position
        reader.BaseStream.Seek(t_pos, SeekOrigin.Begin);


        // Hacky way to determine if this is the real function...
        real -= PUSH_OPCODES.Any(x => real_bytes.Take(x.Length).SequenceEqual(x)) ? 0x6UL : 0x0UL;

        REAL_FUNCTION_ADDRESS = real;
    }

}

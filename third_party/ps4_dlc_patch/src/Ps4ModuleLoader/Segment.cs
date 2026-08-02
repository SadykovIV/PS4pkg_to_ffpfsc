namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
public class Segment
{
    public uint TYPE { get; private set; }
    private uint _flags;
    public uint FLAGS
    {
        get => _flags & 0xF;
        private set => _flags = value;
    }
    public ulong OFFSET { get; private set; }
    public ulong MEM_ADDR { get; private set; }
    public ulong FILE_ADDR { get; private set; }
    public ulong FILE_SIZE { get; private set; }
    public long PHT_FILE_SIZE_FIELD_FILE_OFFSET { get; private set; }
    public ulong MEM_SIZE { get; private set; }
    public long PHT_MEM_SIZE_FIELD_FILE_OFFSET { get; private set; }
    public ulong ALIGNMENT { get; private set; }

    /// <summary>
    /// REQUIRES READER TO BE AT THE START OF THE ENTRY FOR THE SEGMENT
    /// </summary>
    /// <param name="reader"></param>
    public Segment(BinaryReader reader)
    {
        TYPE = reader.ReadUInt32();
        FLAGS = reader.ReadUInt32();
        OFFSET = reader.ReadUInt64();
        MEM_ADDR = reader.ReadUInt64();
        FILE_ADDR = reader.ReadUInt64();
        PHT_FILE_SIZE_FIELD_FILE_OFFSET = reader.BaseStream.Position;
        FILE_SIZE = reader.ReadUInt64();
        PHT_MEM_SIZE_FIELD_FILE_OFFSET = reader.BaseStream.Position;
        MEM_SIZE = reader.ReadUInt64();
        ALIGNMENT = reader.ReadUInt64();
    }

    public enum SegmentType
    {
        PT_NULL = 0x0,
        PT_LOAD = 0x1,
        PT_DYNAMIC = 0x2,
        PT_INTERP = 0x3,
        PT_NOTE = 0x4,
        PT_SHLIB = 0x5,
        PT_PHDR = 0x6,
        PT_TLS = 0x7,
        PT_NUM = 0x8,
        PT_SCE_DYNLIBDATA = 0x61000000,
        PT_SCE_PROCPARAM = 0x61000001,
        PT_SCE_MODULEPARAM = 0x61000002,
        PT_SCE_RELRO = 0x61000010,
        PT_GNU_EH_FRAME = 0x6474E550,
        PT_GNU_STACK = 0x6474E551,
        PT_SCE_COMMENT = 0x6FFFFF00,
        PT_SCE_LIBVERSION = 0x6FFFFF01,
        PT_HIOS = 0x6FFFFFFF,
        PT_LOPROC = 0x70000000,
        PT_SCE_SEGSYM = 0x700000A8,
        PT_HIPROC = 0x7FFFFFFF
    }

    public enum SegmentAlignment
    {
        AL_NONE = 0x0,
        AL_BYTE = 0x1,
        AL_WORD = 0x2,
        AL_DWORD = 0x4,
        AL_QWORD = 0x8,
        AL_PARA = 0x10,
        AL_4K = 0x4000
    }

    private const byte SEGPERM_EXEC = 1;
    private const byte SEGPERM_WRITE = 2;
    private const byte SEGPERM_READ = 4;
    
    public string GetName()
    {
        return TYPE switch
        {
            (uint)SegmentType.PT_NULL => "NULL",
            (uint)SegmentType.PT_LOAD => (FLAGS == (SEGPERM_EXEC | SEGPERM_READ)) ? "CODE" : "DATA",
            (uint)SegmentType.PT_DYNAMIC => "DYNAMIC",
            (uint)SegmentType.PT_INTERP => "INTERP",
            (uint)SegmentType.PT_NOTE => "NOTE",
            (uint)SegmentType.PT_SHLIB => "SHLIB",
            (uint)SegmentType.PT_PHDR => "PHDR",
            (uint)SegmentType.PT_TLS => "TLS",
            (uint)SegmentType.PT_NUM => "NUM",
            (uint)SegmentType.PT_SCE_DYNLIBDATA => "SCE_DYNLIBDATA",
            (uint)SegmentType.PT_SCE_PROCPARAM => "SCE_PROCPARAM",
            (uint)SegmentType.PT_SCE_MODULEPARAM => "SCE_MODULEPARAM",
            (uint)SegmentType.PT_SCE_RELRO => "SCE_RELRO",
            (uint)SegmentType.PT_GNU_EH_FRAME => "GNU_EH_FRAME",
            (uint)SegmentType.PT_GNU_STACK => "GNU_STACK",
            (uint)SegmentType.PT_SCE_COMMENT => "SCE_COMMENT",
            (uint)SegmentType.PT_SCE_LIBVERSION => "SCE_LIBVERSION",
            _ => "UNK"
        };
    }

    public string GetTypeString()
    {
        return TYPE switch
        {
            (uint)SegmentType.PT_LOAD => (FLAGS == (SEGPERM_EXEC | SEGPERM_READ)) ? "CODE" : "DATA",
            (uint)SegmentType.PT_DYNAMIC => "DATA",
            (uint)SegmentType.PT_INTERP => "CONST",
            (uint)SegmentType.PT_NOTE => "CONST",
            (uint)SegmentType.PT_PHDR => "CODE",
            (uint)SegmentType.PT_TLS => "BSS",
            (uint)SegmentType.PT_SCE_DYNLIBDATA => "CONST",
            (uint)SegmentType.PT_SCE_PROCPARAM => "CONST",
            (uint)SegmentType.PT_SCE_MODULEPARAM => "CONST",
            (uint)SegmentType.PT_SCE_RELRO => "DATA",
            (uint)SegmentType.PT_GNU_EH_FRAME => "CONST",
            (uint)SegmentType.PT_GNU_STACK => "DATA",
            _ => "UNK"
        };
    }


}

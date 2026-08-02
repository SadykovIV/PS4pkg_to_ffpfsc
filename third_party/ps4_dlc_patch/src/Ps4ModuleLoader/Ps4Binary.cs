// Locally hardened for strict nullable validation; GPL-3.0. See ../../UPSTREAM.md.
using System.Text;

namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
public class Ps4Binary
{
    public const ushort EM_X86_64 = 0x3E;

    public byte[] EI_MAGIC { get; private set; }
    public byte EI_CLASS { get; private set; }
    public byte EI_DATA { get; private set; }
    public byte EI_VERSION { get; private set; }
    public byte EI_OSABI { get; private set; }
    public byte EI_ABIVERSION { get; private set; }
    public byte[] EI_PADDING { get; private set; }
    public byte EI_SIZE { get; private set; }
    public ushort E_TYPE { get; private set; }
    public ushort E_MACHINE { get; private set; }
    public uint E_VERSION { get; private set; }
    public ulong E_START_ADDR { get; private set; }
    public long ELF_HEADER_E_START_ADDR_FIELD_FILE_OFFSET { get; private set; }
    public ulong E_PHT_OFFSET { get; private set; }
    public ulong E_SHT_OFFSET { get; private set; }
    public uint E_FLAGS { get; private set; }
    public ushort E_SIZE { get; private set; }
    public ushort E_PHT_SIZE { get; private set; }
    public ushort E_PHT_COUNT { get; private set; }
    public ushort E_SHT_SIZE { get; private set; }
    public ushort E_SHT_COUNT { get; private set; }
    public ushort E_SHT_INDEX { get; private set; }

    public List<Segment> E_SEGMENTS { get; private set; }
    public List<Section> E_SECTIONS { get; private set; } = new();
    public Dictionary<string, ulong> Dynamic { get; private set; } = new();
    public Dictionary<int, object> Stubs { get; private set; } = new();
    public Dictionary<int, (int id, string? name, ulong? stringFileOffset)> Modules { get; private set; } = new();
    public Dictionary<int, (int id, string? name, ulong? stringFileOffset)> Libraries { get; private set; } = new();
    public List<(uint Key, Symbol? Value)> Symbols { get; private set; } = new();
    public List<Relocation> Relocations { get; internal set; } = new();

    public byte[]? FINGERPRINT { get; private set; }


    public Ps4Binary(FileStream f) : this(new BinaryReader(f))
    { }

    public Ps4Binary(BinaryReader reader)
    {
        reader.BaseStream.Seek(0, SeekOrigin.Begin);

        EI_MAGIC = reader.ReadBytes(4);
        EI_CLASS = reader.ReadByte();
        EI_DATA = reader.ReadByte();
        EI_VERSION = reader.ReadByte();
        EI_OSABI = reader.ReadByte();
        EI_ABIVERSION = reader.ReadByte();
        EI_PADDING = reader.ReadBytes(6);
        EI_SIZE = reader.ReadByte();

        E_TYPE = reader.ReadUInt16();
        E_MACHINE = reader.ReadUInt16();
        E_VERSION = reader.ReadUInt32();
        ELF_HEADER_E_START_ADDR_FIELD_FILE_OFFSET = reader.BaseStream.Position;
        E_START_ADDR = reader.ReadUInt64();
        E_PHT_OFFSET = reader.ReadUInt64();
        E_SHT_OFFSET = reader.ReadUInt64();
        E_FLAGS = reader.ReadUInt32();
        E_SIZE = reader.ReadUInt16();
        E_PHT_SIZE = reader.ReadUInt16();
        E_PHT_COUNT = reader.ReadUInt16();
        E_SHT_SIZE = reader.ReadUInt16();
        E_SHT_COUNT = reader.ReadUInt16();
        E_SHT_INDEX = reader.ReadUInt16();

        if (E_MACHINE != EM_X86_64)
        {
            throw new Exception("Unsupported format");
        }

        reader.BaseStream.Seek((long)E_PHT_OFFSET, SeekOrigin.Begin);
        E_SEGMENTS = new List<Segment>();
        for (int i = 0; i < E_PHT_COUNT; i++)
        {
            E_SEGMENTS.Add(new Segment(reader));
        }

        //reader.BaseStream.Seek((long)E_SHT_OFFSET, SeekOrigin.Begin);
        //E_SECTIONS = new List<Section>();
        //for (int i = 0; i < E_SHT_COUNT; i++)
        //{
        //    E_SECTIONS.Add(new Section(reader));
        //}

        if (E_MACHINE != EM_X86_64 || E_START_ADDR > 0xFFFFFFFF82200000)
        {
            throw new Exception("Unsupported format");
        }

    }


    public void Process(BinaryReader reader)
    {
        foreach (var segment in E_SEGMENTS)
        {
            ulong address = ulong.MaxValue;
            // Process Loadable Segments...
            string[] loadableSegmentNames = ["CODE", "DATA", "SCE_RELRO", "DYNAMIC", "GNU_EH_FRAME", "SCE_DYNLIBDATA"];
            if (loadableSegmentNames.Contains(segment.GetName()))
            {
                address = segment.GetName() switch
                {
                    "DYNAMIC" or "SCE_DYNLIBDATA" => segment.OFFSET + 0x1000000,
                    _ => segment.MEM_ADDR,
                };

                var size = segment.GetName() switch
                {
                    "DYNAMIC" or "SCE_DYNLIBDATA" => segment.FILE_SIZE,
                    _ => segment.MEM_SIZE,
                };

                // Process Dynamic Segment....
                if (segment.GetName() == "DYNAMIC")
                {
                    reader.BaseStream.Seek((long)segment.OFFSET, SeekOrigin.Begin);
                    var offset = segment.OFFSET;
                    var dynamicsize = size;

                    for (int entry = 0; entry < (int)(dynamicsize / 0x10); entry++)
                    {
                        new Dynamic(reader).Process(this);
                    }
                }


            }


            // Process SCE 'Special' Shared Object Segment...
            if (segment.GetName() == "SCE_DYNLIBDATA")
            {
                FINGERPRINT = new byte[0x14];
                reader.BaseStream.Seek((long)segment.OFFSET, SeekOrigin.Begin);
                reader.Read(FINGERPRINT, 0, 0x14);

                // Dynamic Symbol Table
                try
                {
                    reader.BaseStream.Seek((long)(segment.OFFSET + Dynamic["SYMTAB"]), SeekOrigin.Begin);
                    for (int entry = 0; entry < (int)(Dynamic["SYMTABSZ"] / 0x18); entry++)
                    {
                        var symbol = new Symbol(reader);
                        symbol.Process(this);
                        //Symbols[symbol.NAME] = symbol;
                        //Symbols.First(x=>x.Key == symbol.NAME).Value = symbol;
                        bool found = false;
                        for (int i = 0; i < Symbols.Count; i++)
                        {
                            if (Symbols[i].Key == symbol.NAME)
                            {
                                Symbols[i] = (symbol.NAME, symbol);
                                found = true;
                            }
                        }
                        if (!found && symbol.NAME != 0)
                        {
                            Symbols.Add((symbol.NAME, symbol));
                        }
                    }
                }
                catch (Exception)
                {
                    throw;
                }

                try
                {
                    var location = address + Dynamic["STRTAB"];
                    var location2 = segment.OFFSET + Dynamic["STRTAB"];
                    reader.BaseStream.Seek((long)(location2), SeekOrigin.Begin);

                    // Stubs
                    foreach (var key in Stubs.Keys)
                    {
                        var t_pos = reader.BaseStream.Position;
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        string stub = string.Empty;
                        int strLen = 0;
                        while (reader.ReadByte() != 0x0)
                        { strLen++; }
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        stub = Encoding.UTF8.GetString(reader.ReadBytes(strLen));
                        Stubs[(int)key] = stub;
                        reader.BaseStream.Seek(t_pos, SeekOrigin.Begin);
                    }

                    // Modules
                    foreach (var key in Modules.Keys)
                    {
                        var t_pos = reader.BaseStream.Position;
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        string module = string.Empty;
                        int strLen = 0;
                        while (reader.ReadByte() != 0x0)
                        { strLen++; }
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        module = Encoding.UTF8.GetString(reader.ReadBytes(strLen));
                        Modules[(int)key] = (Modules[(int)key].id, module, location2 + (ulong)key);
                        reader.BaseStream.Seek(t_pos, SeekOrigin.Begin);
                    }

                    // Libraries and LIDs
                    Dictionary<int, string> lids = new();
                    foreach (var key in Libraries.Keys)
                    {
                        var t_pos = reader.BaseStream.Position;
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        string lid = string.Empty;
                        int strLen = 0;
                        while (reader.ReadByte() != 0x0)
                        { strLen++; }
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        lid = Encoding.UTF8.GetString(reader.ReadBytes(strLen));
                        Libraries[(int)key] = (Libraries[(int)key].id, lid, location2 + (ulong)key);
                        lids[(int)key] = lid;
                        reader.BaseStream.Seek(t_pos, SeekOrigin.Begin);
                    }

                    // Symbols
                    foreach (var (key, value) in Symbols)
                    {
                        var t_pos = reader.BaseStream.Position;
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        string symbol = string.Empty;
                        int strLen = 0;
                        while (reader.ReadByte() != 0x0)
                        { strLen++; }
                        reader.BaseStream.Seek((long)(location2 + (ulong)key), SeekOrigin.Begin);
                        symbol = Encoding.UTF8.GetString(reader.ReadBytes(strLen));
                        for (int i = 0; i < Symbols.Count; i++)
                        {
                            if (Symbols[i].Key == key)
                            {
                                var resolvedSymbol = Symbols[i].Value ?? throw new InvalidDataException(
                                    "ELF symbol entry is missing while resolving names.");
                                resolvedSymbol.NID = symbol;
                                resolvedSymbol.NID_FILE_ADDRESS = location2 + (ulong)key;
                            }

                        }
                        reader.BaseStream.Seek(t_pos, SeekOrigin.Begin);
                    }
                }
                catch (Exception)
                {
                    throw;
                }

                // Resolve Export Symbols
                try
                {
                    var symbols = Symbols.OrderBy(x => x.Key).ToList();
                    var location = address + Dynamic["SYMTAB"] + 0x30;
                    reader.BaseStream.Seek((long)(segment.OFFSET + Dynamic["SYMTAB"] + 0x30), SeekOrigin.Begin);
                    var entryCount = (int)((Dynamic["SYMTABSZ"] - 0x30) / 0x18);
                    for (int entry = 0; entry < entryCount; entry++)
                    {
                        var value = symbols[entry].Value ?? throw new InvalidDataException(
                            "ELF symbol entry is missing while resolving exports.");
                        var nid = value.NID ?? throw new InvalidDataException(
                            "ELF symbol name is missing while resolving exports.");
                        new Symbol(reader).Resolve(location + (ulong)(entry * 0x18), nid);
                    }
                }
                catch (Exception)
                {
                    throw;
                }

                // Jump Table
                try
                {
                    var location = address + Dynamic["JMPTAB"];
                    reader.BaseStream.Seek((long)(segment.OFFSET + Dynamic["JMPTAB"]), SeekOrigin.Begin);
                    var count = (int)(Dynamic["JMPTABSZ"] / 0x18);
                    for (int entry = 0; entry < count; entry++)
                    {
                        var reloc = new Relocation(reader);
                        reloc.Resolve(reader, this);
                        Relocations.Add(reloc);
                    }
                }
                catch (Exception)
                {
                    throw;
                }

                // Relocation Table
                try
                {
                    var location = address + Dynamic["RELATAB"];
                    reader.BaseStream.Seek((long)(segment.OFFSET + Dynamic["RELATAB"]), SeekOrigin.Begin);
                    for (int entry = 0; entry < (int)(Dynamic["RELATABSZ"] / 0x18); entry++)
                    {
                        new Relocation(reader).Process(this);
                        //Relocation reloc = new Relocation(reader);
                        //reloc.Process(this);
                        //Relocations.Add(reloc);
                    }
                }
                catch (Exception)
                { }

            }



        }
    }

    public enum ProgramType
    {
        ET_NONE = 0x0,
        ET_REL = 0x1,
        ET_EXEC = 0x2,
        ET_DYN = 0x3,
        ET_CORE = 0x4,
        ET_SCE_EXEC = 0xFE00,
        ET_SCE_REPLAY_EXEC = 0xFE01,
        ET_SCE_RELEXEC = 0xFE04,
        ET_SCE_STUBLIB = 0xFE0C,
        ET_SCE_DYNEXEC = 0xFE10,
        ET_SCE_DYNAMIC = 0xFE18,
        ET_LOPROC = 0xFF00,
        ET_HIPROC = 0xFFFF,
    }

    public string GetBinaryTypeString()
    {
        return E_TYPE switch
        {
            (ushort)ProgramType.ET_NONE => "None",
            (ushort)ProgramType.ET_REL => "Relocatable",
            (ushort)ProgramType.ET_EXEC => "Executable",
            (ushort)ProgramType.ET_DYN => "Shared Object",
            (ushort)ProgramType.ET_CORE => "Core Dump",
            (ushort)ProgramType.ET_SCE_EXEC => "Main Module",
            (ushort)ProgramType.ET_SCE_REPLAY_EXEC => "Replay Module",
            (ushort)ProgramType.ET_SCE_RELEXEC => "Relocatable PRX",
            (ushort)ProgramType.ET_SCE_STUBLIB => "Stub Library",
            (ushort)ProgramType.ET_SCE_DYNEXEC => "Main Module - ASLR",
            (ushort)ProgramType.ET_SCE_DYNAMIC => "Shared Object PRX",
            _ => "Missing Program Type!!!",
        };
    }
}

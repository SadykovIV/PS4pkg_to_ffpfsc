using System.Text.Json.Serialization;

namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
//[JsonSerializable(typeof(Symbol))]
//public partial class SymbolJsonContext : JsonSerializerContext { }
public class Symbol
{
    public enum SymbolInfo
    {
        ST_LOCAL_NONE = 0x0,
        ST_LOCAL_OBJECT = 0x1,
        ST_LOCAL_FUNCTION = 0x2,
        ST_LOCAL_SECTION = 0x3,
        ST_LOCAL_FILE = 0x4,
        ST_LOCAL_COMMON = 0x5,
        ST_LOCAL_TLS = 0x6,
        ST_GLOBAL_NONE = 0x10,
        ST_GLOBAL_OBJECT = 0x11,
        ST_GLOBAL_FUNCTION = 0x12,
        ST_GLOBAL_SECTION = 0x13,
        ST_GLOBAL_FILE = 0x14,
        ST_GLOBAL_COMMON = 0x15,
        ST_GLOBAL_TLS = 0x16,
        ST_WEAK_NONE = 0x20,
        ST_WEAK_OBJECT = 0x21,
        ST_WEAK_FUNCTION = 0x22,
        ST_WEAK_SECTION = 0x23,
        ST_WEAK_FILE = 0x24,
        ST_WEAK_COMMON = 0x25,
        ST_WEAK_TLS = 0x26
    }

    public uint NAME { get; private set; }
    public byte INFO { get; private set; }
    public byte OTHER { get; private set; }
    public ushort SHINDEX { get; private set; }
    public ulong VALUE { get; private set; }
    public ulong SIZE { get; private set; }
    public ulong NID_FILE_ADDRESS { get; internal set; }
    public Relocation? RELOCATION { get; internal set; }
    public string? NID { get; internal set; }

    /// <summary>
    /// REQUIRES READER TO BE AT THE START OF THE ENTRY FOR THE SYMBOL
    /// </summary>
    /// <param name="reader"></param>
    public Symbol(BinaryReader reader)
    {
        NAME = reader.ReadUInt32();
        INFO = reader.ReadByte();
        OTHER = reader.ReadByte();
        SHINDEX = reader.ReadUInt16();
        VALUE = reader.ReadUInt64();
        SIZE = reader.ReadUInt64();
    }

    public string GetInfo()
    {
        return INFO switch
        {
            (byte)SymbolInfo.ST_LOCAL_NONE => "Local : None",
            (byte)SymbolInfo.ST_LOCAL_OBJECT => "Local : Object",
            (byte)SymbolInfo.ST_LOCAL_FUNCTION => "Local : Function",
            (byte)SymbolInfo.ST_LOCAL_SECTION => "Local : Section",
            (byte)SymbolInfo.ST_LOCAL_FILE => "Local : File",
            (byte)SymbolInfo.ST_LOCAL_COMMON => "Local : Common",
            (byte)SymbolInfo.ST_LOCAL_TLS => "Local : TLS",
            (byte)SymbolInfo.ST_GLOBAL_NONE => "Global : None",
            (byte)SymbolInfo.ST_GLOBAL_OBJECT => "Global : Object",
            (byte)SymbolInfo.ST_GLOBAL_FUNCTION => "Global : Function",
            (byte)SymbolInfo.ST_GLOBAL_SECTION => "Global : Section",
            (byte)SymbolInfo.ST_GLOBAL_FILE => "Global : File",
            (byte)SymbolInfo.ST_GLOBAL_COMMON => "Global : Common",
            (byte)SymbolInfo.ST_GLOBAL_TLS => "Global : TLS",
            (byte)SymbolInfo.ST_WEAK_NONE => "Weak : None",
            (byte)SymbolInfo.ST_WEAK_OBJECT => "Weak : Object",
            (byte)SymbolInfo.ST_WEAK_FUNCTION => "Weak : Function",
            (byte)SymbolInfo.ST_WEAK_SECTION => "Weak : Section",
            (byte)SymbolInfo.ST_WEAK_FILE => "Weak : File",
            (byte)SymbolInfo.ST_WEAK_COMMON => "Weak : Common",
            (byte)SymbolInfo.ST_WEAK_TLS => "Weak : TLS",
            _ => "Missing Symbol Information!!!",
        };
    }

    public string Process(Ps4ModuleLoader.Ps4Binary binary)
    {
        // theres originally stuff here
        // TODO: What is this for?

        return GetInfo();
    }

    public void Resolve(ulong address, string symbol, Dictionary<string, string>? nids = null)
    {   
    }

    public ulong GetFileAddressOfValue(Ps4Binary bin)
    {
        return bin.E_SEGMENTS.Min(x => x.OFFSET) + VALUE;
    }
}

namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
public class Section
{
    public uint NAME { get; private set; }
    public uint TYPE { get; private set; }
    public ulong FLAGS { get; private set; }
    public ulong MEM_ADDR { get; private set; }
    public ulong OFFSET { get; private set; }
    public ulong FILE_SIZE { get; private set; }
    public uint LINK { get; private set; }
    public uint INFO { get; private set; }
    public ulong ALIGNMENT { get; private set; }
    public ulong FSE_SIZE { get; private set; }

    /// <summary>
    /// REQUIRES READER TO BE AT THE START OF THE ENTRY FOR THE SECTION
    /// </summary>
    /// <param name="reader"></param>
    public Section(BinaryReader reader)
    {
        NAME = reader.ReadUInt32();
        TYPE = reader.ReadUInt32();
        FLAGS = reader.ReadUInt64();
        MEM_ADDR = reader.ReadUInt64();
        OFFSET = reader.ReadUInt64();
        FILE_SIZE = reader.ReadUInt64();
        LINK = reader.ReadUInt32();
        INFO = reader.ReadUInt32();
        ALIGNMENT = reader.ReadUInt64();
        FSE_SIZE = reader.ReadUInt64();
    }

}

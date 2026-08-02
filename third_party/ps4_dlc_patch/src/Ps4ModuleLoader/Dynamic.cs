namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
internal class Dynamic
{
    public enum DynamicTag
    {
        DT_NULL = 0x0,
        DT_NEEDED = 0x1,
        DT_PLTRELSZ = 0x2,
        DT_PLTGOT = 0x3,
        DT_HASH = 0x4,
        DT_STRTAB = 0x5,
        DT_SYMTAB = 0x6,
        DT_RELA = 0x7,
        DT_RELASZ = 0x8,
        DT_RELAENT = 0x9,
        DT_STRSZ = 0xA,
        DT_SYMENT = 0xB,
        DT_INIT = 0xC,
        DT_FINI = 0xD,
        DT_SONAME = 0xE,
        DT_RPATH = 0xF,
        DT_SYMBOLIC = 0x10,
        DT_REL = 0x11,
        DT_RELSZ = 0x12,
        DT_RELENT = 0x13,
        DT_PLTREL = 0x14,
        DT_DEBUG = 0x15,
        DT_TEXTREL = 0x16,
        DT_JMPREL = 0x17,
        DT_BIND_NOW = 0x18,
        DT_INIT_ARRAY = 0x19,
        DT_FINI_ARRAY = 0x1A,
        DT_INIT_ARRAYSZ = 0x1B,
        DT_FINI_ARRAYSZ = 0x1C,
        DT_RUNPATH = 0x1D,
        DT_FLAGS = 0x1E,
        DT_ENCODING = 0x1F,
        DT_PREINIT_ARRAY = 0x20,
        DT_PREINIT_ARRAYSZ = 0x21,
        DT_SCE_IDTABENTSZ = 0x61000005,
        DT_SCE_FINGERPRINT = 0x61000007,
        DT_SCE_ORIGINAL_FILENAME = 0x61000009,
        DT_SCE_MODULE_INFO = 0x6100000D,
        DT_SCE_NEEDED_MODULE = 0x6100000F,
        DT_SCE_MODULE_ATTR = 0x61000011,
        DT_SCE_EXPORT_LIB = 0x61000013,
        DT_SCE_IMPORT_LIB = 0x61000015,
        DT_SCE_EXPORT_LIB_ATTR = 0x61000017,
        DT_SCE_IMPORT_LIB_ATTR = 0x61000019,
        DT_SCE_STUB_MODULE_NAME = 0x6100001D,
        DT_SCE_STUB_MODULE_VERSION = 0x6100001F,
        DT_SCE_STUB_LIBRARY_NAME = 0x61000021,
        DT_SCE_STUB_LIBRARY_VERSION = 0x61000023,
        DT_SCE_HASH = 0x61000025,
        DT_SCE_PLTGOT = 0x61000027,
        DT_SCE_JMPREL = 0x61000029,
        DT_SCE_PLTREL = 0x6100002B,
        DT_SCE_PLTRELSZ = 0x6100002D,
        DT_SCE_RELA = 0x6100002F,
        DT_SCE_RELASZ = 0x61000031,
        DT_SCE_RELAENT = 0x61000033,
        DT_SCE_STRTAB = 0x61000035,
        DT_SCE_STRSZ = 0x61000037,
        DT_SCE_SYMTAB = 0x61000039,
        DT_SCE_SYMENT = 0x6100003B,
        DT_SCE_HASHSZ = 0x6100003D,
        DT_SCE_SYMTABSZ = 0x6100003F,
        DT_SCE_HIOS = 0x6FFFF000,
        DT_GNU_HASH = 0x6FFFFEF5,
        DT_VERSYM = 0x6FFFFFF0,
        DT_RELACOUNT = 0x6FFFFFF9,
        DT_RELCOUNT = 0x6FFFFFFA,
        DT_FLAGS_1 = 0x6FFFFFFB,
        DT_VERDEF = 0x6FFFFFFC,
        DT_VERDEFNUM = 0x6FFFFFFD,
    }

    public ulong TAG { get; private set; }
    public ulong VALUE { get; private set; }
    private ulong? INDEX;
    private ulong? ID;

    /// <summary>
    /// REQUIRES READER TO BE AT THE START OF THE ENTRY FOR THE DYNAMIC
    /// </summary>
    /// <param name="reader"></param>
    public Dynamic(BinaryReader reader)
    {
        TAG = reader.ReadUInt64();
        VALUE = reader.ReadUInt64();
    }

    public string GetTagString()
    {
        return Enum.GetName(typeof(DynamicTag), TAG) ?? "Missing Dynamic Tag!!!";
    }

    public string GetLibraryAttribute()
    {
        return INDEX switch
        {
            0x1 => "AUTO_EXPORT",
            0x2 => "WEAK_EXPORT",
            0x8 => "LOOSE_IMPORT",
            0x9 => "AUTO_EXPORT|LOOSE_IMPORT",
            0x10 => "WEAK_EXPORT|LOOSE_IMPORT",
            _ => "Missing Library Attribute!!!",
        };
    }
    public string GetModuleAttribute()
    {
        return INDEX switch
        {
            0x0 => "NONE",
            0x1 => "SCE_CANT_STOP",
            0x2 => "SCE_EXCLUSIVE_LOAD",
            0x4 => "SCE_EXCLUSIVE_START",
            0x8 => "SCE_CAN_RESTART",
            0x10 => "SCE_CAN_RELOCATE",
            0x20 => "SCE_CANT_SHARE",
            _ => "Missing Module Attribute!!!",
        };
    }
    public string Process(Ps4Binary ps4Binary)
    {
        if (TAG == (ulong)DynamicTag.DT_INIT)
        { ps4Binary.Dynamic["INIT"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_FINI)
        { ps4Binary.Dynamic["FINI"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_NEEDED || TAG == (ulong)DynamicTag.DT_SONAME)
        { ps4Binary.Stubs[(int)VALUE] = 0; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_STRTAB)
        { ps4Binary.Dynamic["STRTAB"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_STRSZ)
        { ps4Binary.Dynamic["STRTABSZ"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_SYMTAB)
        { ps4Binary.Dynamic["SYMTAB"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_SYMTABSZ)
        { ps4Binary.Dynamic["SYMTABSZ"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_JMPREL)
        { ps4Binary.Dynamic["JMPTAB"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_PLTRELSZ)
        { ps4Binary.Dynamic["JMPTABSZ"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_PLTREL)
        {
            if (VALUE == 0x7)
            { return $"{GetTagString()} | {VALUE} | DT_RELA"; }
        }
        else if (TAG == (ulong)DynamicTag.DT_SCE_RELA)
        { ps4Binary.Dynamic["RELATAB"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_RELASZ)
        { ps4Binary.Dynamic["RELATABSZ"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_HASH)
        { ps4Binary.Dynamic["HASHTAB"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_HASHSZ)
        { ps4Binary.Dynamic["HASHTABSZ"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_PLTGOT)
        { ps4Binary.Dynamic["GOT"] = VALUE; }
        else if (TAG == (ulong)DynamicTag.DT_SCE_NEEDED_MODULE || TAG == (ulong)DynamicTag.DT_SCE_IMPORT_LIB ||
                    TAG == (ulong)DynamicTag.DT_SCE_IMPORT_LIB_ATTR || TAG == (ulong)DynamicTag.DT_SCE_EXPORT_LIB ||
                    TAG == (ulong)DynamicTag.DT_SCE_EXPORT_LIB_ATTR || TAG == (ulong)DynamicTag.DT_SCE_MODULE_INFO ||
                    TAG == (ulong)DynamicTag.DT_SCE_MODULE_ATTR || TAG == (ulong)DynamicTag.DT_SCE_FINGERPRINT ||
                    TAG == (ulong)DynamicTag.DT_SCE_ORIGINAL_FILENAME)
        {
            ID = VALUE >> 48;
            var VERSION_MINOR = (VALUE >> 40) & 0xF;
            var VERSION_MAJOR = (VALUE >> 32) & 0xF;
            INDEX = VALUE & 0xFFF;

            if (TAG == (ulong)DynamicTag.DT_SCE_NEEDED_MODULE || TAG == (ulong)DynamicTag.DT_SCE_MODULE_INFO)
            {
                ps4Binary.Modules[(int)INDEX] = ((int)ID, null, null);
                //ps4Binary.Modules[(int)INDEX] = (null, null, null);
                return $"{GetTagString()} | MID:{ID:X} Version:{VERSION_MAJOR}.{VERSION_MINOR} | {INDEX}";
            }
            else if (TAG == (ulong)DynamicTag.DT_SCE_IMPORT_LIB || TAG == (ulong)DynamicTag.DT_SCE_EXPORT_LIB)
            {
                ps4Binary.Libraries[(int)INDEX] = ((int)ID, null, null);
                return $"{GetTagString()} | LID:{ID:X} Version:{VERSION_MAJOR} | {INDEX}";
            }
            else if (TAG == (ulong)DynamicTag.DT_SCE_MODULE_ATTR)
            { return $"{GetTagString()} | {GetModuleAttribute()}"; }
            else if (TAG == (ulong)DynamicTag.DT_SCE_IMPORT_LIB_ATTR || TAG == (ulong)DynamicTag.DT_SCE_EXPORT_LIB_ATTR)
            { return $"{GetTagString()} | LID:{INDEX:X} Attributes:{GetLibraryAttribute()}"; }
            else if (TAG == (ulong)DynamicTag.DT_SCE_FINGERPRINT)
            { ps4Binary.Dynamic["FINGERPRINT"] = VALUE; }
            else if (TAG == (ulong)DynamicTag.DT_SCE_ORIGINAL_FILENAME)
            { ps4Binary.Stubs[(int)INDEX] = 0; }
        }
        return $"{GetTagString()} | {VALUE}";
    }
}

using System.Buffers;
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;

namespace ps4_eboot_dlc_patcher.Ps4ModuleLoader;
public static class Utils
{
    // https://github.com/OpenOrbis/create-fself/blob/3dce1170125bf93ebca2b19236691359f8753d2f/pkg/oelf/OELFGenDynlibData.go#L626
    private static readonly byte[] _symbolSuffix = [0x51, 0x8D, 0x64, 0xA6, 0x35, 0xDE, 0xD8, 0xC1, 0xE6, 0xB0, 0x39, 0xB1, 0xC3, 0xE5, 0x52, 0x30];
    private static readonly SHA1 _sha1 = SHA1.Create();
    public static string CalculateNidForSymbol(ReadOnlySpan<char> symbol)
    {
        Span<byte> symbolBytes = stackalloc byte[symbol.Length + _symbolSuffix.Length];
        Encoding.ASCII.GetBytes(symbol, symbolBytes);
        _symbolSuffix.CopyTo(symbolBytes.Slice(symbol.Length));

        Span<byte> hash = stackalloc byte[20];
        if (!_sha1.TryComputeHash(symbolBytes, hash, out _))
        { throw new InvalidOperationException("Failed to compute hash"); }

        Span<byte> hashBytes = stackalloc byte[8];
        BinaryPrimitives.WriteUInt64BigEndian(hashBytes, BinaryPrimitives.ReadUInt64LittleEndian(hash));

        Span<char> nidHash = stackalloc char[20];
        Convert.TryToBase64Chars(hashBytes, nidHash, out _);
        for (int i = 0; i < nidHash.Length; i++)
        {
            if (nidHash[i] == '/')
            { nidHash[i] = '-'; }
            if (nidHash[i] == '=')
            {
                nidHash = nidHash.Slice(0, i);
                break;
            }
        }
        return new string(nidHash);
    }
}

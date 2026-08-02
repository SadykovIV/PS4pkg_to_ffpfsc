// Modified adaptation for PS4 FFPFSC, 2026-08-02; GPL-3.0.
// PKG parsing was removed; see ../UPSTREAM.md.
using System.Globalization;
using System.Security.Cryptography;

namespace ps4_eboot_dlc_patcher;

public sealed class DlcInfo
{
    public const int MaximumCount = 2500;

    public enum DlcType : byte
    {
        PSAL = 0,
        PSAC = 4,
    }

    public string EntitlementLabel { get; }
    public DlcType Type { get; }
    public byte[] EntitlementKey { get; }

    public DlcInfo(string entitlementLabel, DlcType type, byte[] entitlementKey)
    {
        if (entitlementLabel.Length != 16 ||
            entitlementLabel.Any(c => !(c is >= 'A' and <= 'Z') &&
                                      !(c is >= '0' and <= '9') && c != '_'))
        {
            throw new ArgumentException(
                "Entitlement label must match [A-Z0-9_]{16}.",
                nameof(entitlementLabel));
        }
        if (!Enum.IsDefined(type))
        {
            throw new ArgumentException("DLC type must be PSAL/0 or PSAC/4.", nameof(type));
        }
        if (entitlementKey.Length != 16)
        {
            throw new ArgumentException("Entitlement key must be exactly 16 bytes.", nameof(entitlementKey));
        }

        EntitlementLabel = entitlementLabel;
        Type = type;
        EntitlementKey = entitlementKey;
    }

    public static DlcInfo FromEncodedString(ReadOnlySpan<char> encodedString)
    {
        var text = encodedString.Trim();
        Span<Range> ranges = stackalloc Range[3];
        var count = text.Split(ranges, '-');
        if (count != 3)
        {
            throw new ArgumentException("Encoded DLC info must contain label, type, and key.");
        }

        var label = text[ranges[0]].ToString();
        if (!byte.TryParse(text[ranges[1]], NumberStyles.HexNumber,
                CultureInfo.InvariantCulture, out var typeByte) ||
            !Enum.IsDefined(typeof(DlcType), typeByte))
        {
            throw new ArgumentException("Encoded DLC info has an invalid type.");
        }

        var keyText = text[ranges[2]];
        if (keyText.Length != 32)
        {
            throw new ArgumentException("Encoded DLC info has an invalid key length.");
        }

        byte[] key;
        try
        {
            key = Convert.FromHexString(keyText);
        }
        catch (FormatException)
        {
            throw new ArgumentException("Encoded DLC info key is not hexadecimal.");
        }
        try
        {
            return new DlcInfo(label, (DlcType)typeByte, key);
        }
        catch
        {
            CryptographicOperations.ZeroMemory(key);
            throw;
        }
    }

    public void ClearKey()
    {
        CryptographicOperations.ZeroMemory(EntitlementKey);
    }
}

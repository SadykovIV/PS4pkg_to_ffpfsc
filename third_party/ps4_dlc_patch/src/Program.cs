// Modified adaptation for PS4 FFPFSC, 2026-08-02; GPL-3.0.
// Deterministic JSON batch boundary; see ../UPSTREAM.md.
using System.Text.Json;

namespace ps4_eboot_dlc_patcher;

internal static class Program
{
    private sealed record Options(string InputElf, string OutputDirectory, string DlcJson);

    private sealed class UsageException(string message) : Exception(message);

    public static async Task<int> Main(string[] args)
    {
        List<DlcInfo>? dlc = null;
        try
        {
            if (args.Length == 1 && args[0] is "--help" or "-h")
            {
                WriteUsage();
                return 0;
            }
            if (args.Length == 1 && args[0] == "--check-template")
            {
                CheckEmbeddedTemplate();
                return 0;
            }

            var options = ParseOptions(args);
            dlc = ReadDlcJson(options.DlcJson);
            ConsoleUi.LogInfo($"Validated {dlc.Count} DLC entries; key material is not logged.");

            var ordered = dlc
                .Where(item => item.Type == DlcInfo.DlcType.PSAC)
                .Concat(dlc.Where(item => item.Type == DlcInfo.DlcType.PSAL))
                .ToList();
            var result = await ExecutablePatcher.PatchAsync(
                options.InputElf,
                options.OutputDirectory,
                ordered);

            WriteResultJson(result, ordered);
            return 0;
        }
        catch (UsageException error)
        {
            ConsoleUi.LogError(error.Message);
            WriteErrorJson("usage", error.Message);
            return 2;
        }
        catch (Exception error)
        {
            var message = SanitizeError(error.Message);
            ConsoleUi.LogError(message);
            WriteErrorJson("patch_failed", message);
            return 1;
        }
        finally
        {
            if (dlc is not null)
            {
                foreach (var item in dlc)
                {
                    item.ClearKey();
                }
            }
        }
    }

    private static Options ParseOptions(string[] args)
    {
        string? input = null;
        string? output = null;
        string? json = null;

        for (var index = 0; index < args.Length; index++)
        {
            var option = args[index];
            if (option is not ("--input" or "--output-dir" or "--dlc-json"))
            {
                throw new UsageException($"Unknown option: {option}");
            }
            if (++index >= args.Length)
            {
                throw new UsageException($"Missing value for {option}.");
            }

            var value = args[index];
            switch (option)
            {
                case "--input":
                    if (input is not null) throw new UsageException("--input was specified more than once.");
                    input = value;
                    break;
                case "--output-dir":
                    if (output is not null) throw new UsageException("--output-dir was specified more than once.");
                    output = value;
                    break;
                case "--dlc-json":
                    if (json is not null) throw new UsageException("--dlc-json was specified more than once.");
                    json = value;
                    break;
            }
        }

        if (input is null || output is null || json is null)
        {
            throw new UsageException("Required options: --input, --output-dir, --dlc-json.");
        }
        if (!File.Exists(input)) throw new UsageException("Input ELF does not exist.");
        if (!Path.GetExtension(input).Equals(".elf", StringComparison.OrdinalIgnoreCase))
            throw new UsageException("--input must identify an unsigned .elf file.");
        if (json != "-" && !File.Exists(json))
            throw new UsageException("DLC JSON file does not exist.");

        return new Options(
            Path.GetFullPath(input),
            Path.GetFullPath(output),
            json == "-" ? "-" : Path.GetFullPath(json));
    }

    private const int MaximumJsonBytes = 4 * 1024 * 1024;

    private static List<DlcInfo> ReadDlcJson(string path)
    {
        var input = ReadDlcJsonBytes(path, out var inputLength);
        try
        {
            return ParseDlcJson(input.AsMemory(0, inputLength));
        }
        finally
        {
            System.Security.Cryptography.CryptographicOperations.ZeroMemory(input);
        }
    }

    private static byte[] ReadDlcJsonBytes(string path, out int inputLength)
    {
        var input = new byte[MaximumJsonBytes + 1];
        Stream stream;
        var ownsStream = path != "-";
        if (ownsStream)
        {
            stream = new FileStream(
                path, FileMode.Open, FileAccess.Read, FileShare.Read,
                64 * 1024, FileOptions.SequentialScan);
        }
        else
        {
            stream = Console.OpenStandardInput();
        }

        try
        {
            var length = 0;
            while (length < input.Length)
            {
                var read = stream.Read(input, length, input.Length - length);
                if (read == 0) break;
                length += read;
            }
            if (length > MaximumJsonBytes)
                throw new UsageException(
                    $"DLC JSON exceeds the {MaximumJsonBytes}-byte input limit.");

            inputLength = length;
            return input;
        }
        catch
        {
            System.Security.Cryptography.CryptographicOperations.ZeroMemory(input);
            throw;
        }
        finally
        {
            if (ownsStream) stream.Dispose();
        }
    }

    private static List<DlcInfo> ParseDlcJson(ReadOnlyMemory<byte> input)
    {
        using var document = JsonDocument.Parse(
            input,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 8,
            });
        if (document.RootElement.ValueKind != JsonValueKind.Array)
            throw new UsageException("DLC JSON root must be an array.");

        var result = new List<DlcInfo>();
        var labels = new HashSet<string>(StringComparer.Ordinal);
        try
        {
            foreach (var element in document.RootElement.EnumerateArray())
            {
                if (element.ValueKind != JsonValueKind.Object)
                    throw new UsageException("Every DLC JSON entry must be an object.");

                string? label = null;
                DlcInfo.DlcType? type = null;
                byte[]? key = null;
                try
                {
                    var fields = new HashSet<string>(StringComparer.Ordinal);
                    foreach (var property in element.EnumerateObject())
                    {
                        if (!fields.Add(property.Name))
                            throw new UsageException($"Duplicate DLC JSON field: {property.Name}");

                        switch (property.Name)
                        {
                            case "label":
                                label = property.Value.ValueKind == JsonValueKind.String
                                    ? property.Value.GetString()
                                    : throw new UsageException("DLC label must be a string.");
                                break;
                            case "type":
                                type = ParseType(property.Value);
                                break;
                            case "key":
                                key = ParseKey(property.Value);
                                break;
                            default:
                                throw new UsageException($"Unknown DLC JSON field: {property.Name}");
                        }
                    }

                    if (label is null || type is null || key is null)
                        throw new UsageException("Every DLC entry requires label, type, and key.");
                    if (!labels.Add(label))
                        throw new UsageException($"Duplicate DLC label: {label}");
                    if (result.Count >= DlcInfo.MaximumCount)
                        throw new UsageException(
                            $"DLC JSON exceeds the maximum of {DlcInfo.MaximumCount} entries.");

                    result.Add(new DlcInfo(label, type.Value, key));
                    key = null;
                }
                catch
                {
                    if (key is not null)
                        System.Security.Cryptography.CryptographicOperations.ZeroMemory(key);
                    throw;
                }
            }

            if (result.Count == 0) throw new UsageException("DLC JSON list must not be empty.");
            return result;
        }
        catch
        {
            foreach (var item in result)
                item.ClearKey();
            throw;
        }
    }

    private static DlcInfo.DlcType ParseType(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Number && value.TryGetByte(out var number) &&
            Enum.IsDefined(typeof(DlcInfo.DlcType), number))
            return (DlcInfo.DlcType)number;

        if (value.ValueKind == JsonValueKind.String)
        {
            return value.GetString()?.ToUpperInvariant() switch
            {
                "PSAL" or "0" or "00" => DlcInfo.DlcType.PSAL,
                "PSAC" or "4" or "04" => DlcInfo.DlcType.PSAC,
                _ => throw new UsageException("DLC type must be PSAL/0/00 or PSAC/4/04."),
            };
        }
        throw new UsageException("DLC type must be a supported string or integer.");
    }

    private static byte[] ParseKey(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.String)
            throw new UsageException("DLC key must be a 32-character hexadecimal string.");
        var encoded = value.GetString();
        if (encoded?.Length != 32)
            throw new UsageException("DLC key must contain exactly 32 hexadecimal characters.");
        try
        {
            return Convert.FromHexString(encoded);
        }
        catch (FormatException)
        {
            throw new UsageException("DLC key must contain only hexadecimal characters.");
        }
    }

    private static void WriteResultJson(PatchResult result, IReadOnlyCollection<DlcInfo> dlc)
    {
        using var writer = new Utf8JsonWriter(Console.OpenStandardOutput(), new JsonWriterOptions { Indented = false });
        writer.WriteStartObject();
        writer.WriteString("status", "ok");
        writer.WriteString("method", "strict_prx");
        writer.WriteString("patched_elf", result.PatchedElf);
        writer.WriteString("prx", result.Prx);
        writer.WriteNumber("dlc_count", dlc.Count);
        writer.WriteNumber("data_dlc_count", dlc.Count(x => x.Type == DlcInfo.DlcType.PSAC));
        writer.WriteNumber("license_only_count", dlc.Count(x => x.Type == DlcInfo.DlcType.PSAL));
        writer.WriteBoolean("runtime_verified", false);
        writer.WriteEndObject();
        writer.Flush();
        Console.Out.WriteLine();
    }

    private static void WriteErrorJson(string code, string message)
    {
        using var writer = new Utf8JsonWriter(Console.OpenStandardOutput());
        writer.WriteStartObject();
        writer.WriteString("status", "error");
        writer.WriteString("code", code);
        writer.WriteString("message", message);
        writer.WriteEndObject();
        writer.Flush();
        Console.Out.WriteLine();
    }

    private static void CheckEmbeddedTemplate()
    {
        var template = PrxLoaderStuff.LoadUnpatchedSignedDlcldrPrx();
        try
        {
            var sha256 = Convert.ToHexString(
                    System.Security.Cryptography.SHA256.HashData(template))
                .ToLowerInvariant();
            using var writer = new Utf8JsonWriter(Console.OpenStandardOutput());
            writer.WriteStartObject();
            writer.WriteString("status", "ok");
            writer.WriteBoolean("template_compatible", true);
            writer.WriteString("template_sha256", sha256);
            writer.WriteEndObject();
            writer.Flush();
            Console.Out.WriteLine();
        }
        finally
        {
            System.Security.Cryptography.CryptographicOperations.ZeroMemory(template);
        }
    }

    private static string SanitizeError(string message) =>
        string.IsNullOrWhiteSpace(message)
            ? "Unspecified patching error."
            : message.Replace('\r', ' ').Replace('\n', ' ');

    private static void WriteUsage()
    {
        Console.Out.WriteLine("Usage: ps4-dlc-patch --input game.elf --output-dir DIR --dlc-json FILE|-");
        Console.Out.WriteLine("       ps4-dlc-patch --check-template");
        Console.Out.WriteLine("Strict PRX method only; existing outputs are never overwritten.");
    }
}

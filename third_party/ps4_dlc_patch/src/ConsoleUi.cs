// Modified adaptation for PS4 FFPFSC, 2026-08-02; GPL-3.0.
// See ../UPSTREAM.md for provenance and removed interactive behavior.
namespace ps4_eboot_dlc_patcher;

internal static class ConsoleUi
{
    private static readonly object Sync = new();

    public static void LogError(string message) => Write("ERROR", message);

    public static void LogWarning(string message) => Write("WARN", message);

    public static void LogInfo(string message) => Write("INFO", message);

    public static void LogSuccess(string message) => Write("INFO", message);

    private static void Write(string level, string message)
    {
        lock (Sync)
        {
            Console.Error.Write(level);
            Console.Error.Write('\t');
            Console.Error.WriteLine(message.Replace('\r', ' ').Replace('\n', ' '));
        }
    }

    internal sealed class PercentProgressBar
    {
        private readonly string task;
        private int lastBucket = -1;

        public PercentProgressBar(string task)
        {
            this.task = task;
        }

        public Task Update(double newProgressPercent)
        {
            var bounded = Math.Clamp(newProgressPercent, 0, 100);
            var bucket = bounded >= 100 ? 4 : (int)(bounded / 25);
            if (bucket > lastBucket)
            {
                lastBucket = bucket;
                LogInfo($"{task}: {Math.Min(bucket * 25, 100)}%");
            }
            return Task.CompletedTask;
        }
    }
}

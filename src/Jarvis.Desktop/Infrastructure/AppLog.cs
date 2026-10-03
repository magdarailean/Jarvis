using System.Diagnostics;
using System.IO;
using System.Security;

namespace Jarvis.Desktop.Infrastructure;

// Diagnostics must never prevent the user from opening or closing the app.
internal static class AppLog
{
    private static readonly object Sync = new();

    public static void Write(string message)
    {
        var entry = $"{DateTimeOffset.UtcNow:O} [INFO] {message}{Environment.NewLine}";
        Trace.Write(entry);

        try
        {
            lock (Sync)
            {
                var directory = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Jarvis", "logs");
                Directory.CreateDirectory(directory);
                var path = Path.Combine(directory, "application.log");

                if (File.Exists(path) && new FileInfo(path).Length >= 1_048_576)
                    File.WriteAllText(path, string.Empty);

                File.AppendAllText(path, entry);
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or SecurityException)
        {
            Trace.WriteLine($"Diagnostic file unavailable: {error.GetType().Name}");
        }
    }
}

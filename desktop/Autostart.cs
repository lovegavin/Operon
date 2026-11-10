using Microsoft.Win32;

namespace Operon.Desktop;

// Operon never registers Python at login. Older builds or manual experiments may
// have left an entry behind; remove only names that belong to this product so a
// closed desktop can never relaunch a backend that holds files open.
internal static class Autostart
{
    private static readonly string[] Values =
        { "Operon Studio", "OperonStudio" };
    private static readonly string[] Links =
        { "Operon Studio.lnk" };

    public static void RemoveOwnEntries()
    {
        try
        {
            using var run = Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Run", writable: true);
            if (run is not null)
                foreach (var value in Values) run.DeleteValue(value, throwOnMissingValue: false);
        }
        catch (Exception) { }
        try
        {
            var startup = Environment.GetFolderPath(Environment.SpecialFolder.Startup);
            foreach (var name in Links)
            {
                var path = Path.Combine(startup, name);
                if (File.Exists(path)) File.Delete(path);
            }
        }
        catch (Exception) { }
    }
}

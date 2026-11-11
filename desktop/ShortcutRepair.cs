using System.Runtime.InteropServices;

namespace Operon.Desktop;

// The installer normally rewrites shortcuts during an upgrade. If a version
// directory was removed manually, the old .lnk can still point at the deleted
// executable. Repair only our own shortcuts, and only when their target is
// missing or inside this installation.
internal static class ShortcutRepair
{
    public static void Repair(ProfilePaths profile)
    {
        var executable = Environment.ProcessPath;
        if (string.IsNullOrWhiteSpace(executable)) return;
        var install = Path.GetFullPath(AppContext.BaseDirectory).TrimEnd(Path.DirectorySeparatorChar);
        if (!File.Exists(Path.Combine(install, "operon-install.json"))) return;
        var parent = Directory.GetParent(install);
        var root = parent?.Name == "versions" && parent.Parent is not null
            ? parent.Parent.FullName.TrimEnd(Path.DirectorySeparatorChar)
            : install;
        var pinned = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar");
        var links = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Operon Studio.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon", "Operon Studio.lnk"),
            Path.Combine(pinned, "Operon Studio.lnk"),
        };
        foreach (var link in links)
        {
            try { RepairLink(link, executable, root, profile.ProfileDir); }
            catch (COMException) { }
            catch (InvalidCastException) { }
        }
    }

    private static void RepairLink(string link, string executable, string root, string profile)
    {
        if (!File.Exists(link)) return;
        var type = Type.GetTypeFromProgID("WScript.Shell");
        if (type is null) return;
        dynamic shell = Activator.CreateInstance(type)!;
        try
        {
            dynamic shortcut = shell.CreateShortcut(link);
            try
            {
                var target = (string?)shortcut.TargetPath ?? "";
                var missing = string.IsNullOrWhiteSpace(target) || !File.Exists(target);
                var inside = !string.IsNullOrWhiteSpace(target) &&
                    target.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
                if (!missing && !inside) return;
                shortcut.TargetPath = executable;
                shortcut.Arguments = "--profile-dir \"" + profile + "\"";
                shortcut.WorkingDirectory = Path.GetDirectoryName(executable) ?? root;
                shortcut.IconLocation = executable + ",0";
                shortcut.Description = "Operon Studio";
                shortcut.Save();
            }
            finally { Marshal.FinalReleaseComObject(shortcut); }
        }
        finally { Marshal.FinalReleaseComObject(shell); }
    }
}

namespace Operon.Setup;

internal static class SetupInvocation
{
    internal static string[] Normalize(string[] args, string executable, string baseDirectory)
    {
        if (!string.Equals(Path.GetFileNameWithoutExtension(executable), "Operon_Uninstall", StringComparison.OrdinalIgnoreCase))
            return args;
        var result = args.ToList();
        if (!result.Contains("--uninstall") && !result.Contains("--install")) result.Add("--uninstall");
        if (!result.Contains("--install-dir")) { result.Add("--install-dir"); result.Add(Path.GetFullPath(baseDirectory)); }
        return result.ToArray();
    }
}

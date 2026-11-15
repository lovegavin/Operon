using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
using Operon.Setup;

internal static class PromotionTests
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(string path, uint access, uint share,
        IntPtr security, uint creation, uint flags, IntPtr template);

    private static string Stage(string root, string suffix)
    {
        var path = Path.Combine(root, ".install-" + suffix);
        Directory.CreateDirectory(path);
        InstallFiles.AtomicJson(Path.Combine(path, ".operon-install.json"), new { owner = InstallFiles.Owner });
        File.WriteAllText(Path.Combine(path, "preserve.txt"), "verified payload");
        return path;
    }

    private static SafeFileHandle Hold(string path)
    {
        var handle = CreateFile(path, 1, 3, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero);
        if (handle.IsInvalid) throw new System.ComponentModel.Win32Exception();
        return handle;
    }

    internal static async Task Run(string root, Action<bool, string> check)
    {
        var directory = Path.Combine(root, "promotion"); Directory.CreateDirectory(directory);
        var source = Stage(directory, "transient"); var target = Path.Combine(directory, "ready");
        var messages = new List<string>();
        using (var held = Hold(source))
        {
            var moving = InstallFiles.PromoteStage(source, target, CancellationToken.None, messages.Add,
                TimeSpan.FromSeconds(3));
            await Task.Delay(350);
            if (moving.IsFaulted) await moving;
            check(!moving.IsCompleted && Directory.Exists(source), "promotion ignored a real directory handle");
            held.Dispose();
            await moving;
        }
        check(File.ReadAllText(Path.Combine(target, "preserve.txt")) == "verified payload", "promotion lost payload");
        check(messages.Any(x => x.Contains("blocked")) && messages.Any(x => x.Contains("succeeded")), "promotion diagnostics missing");

        source = Stage(directory, "blocked"); target = Path.Combine(directory, "never-ready");
        using (var held = Hold(source))
        {
            try { await InstallFiles.PromoteStage(source, target, CancellationToken.None, _ => {}, TimeSpan.Zero);
                  throw new Exception("permanently blocked stage was enabled"); }
            catch (IOException error) { check(error.InnerException is IOException, "promotion lost native error"); }
        }
        check(Directory.Exists(source) && !Directory.Exists(target), "failed promotion mutated installation");
        using (var held = Hold(source))
        using (var cancel = new CancellationTokenSource(50))
        {
            try { await InstallFiles.PromoteStage(source, target, cancel.Token, _ => {});
                  throw new Exception("promotion ignored cancellation"); }
            catch (OperationCanceledException) { check(Directory.Exists(source), "cancel removed stage"); }
        }
        Directory.CreateDirectory(target);
        File.WriteAllText(Path.Combine(target, "existing.txt"), "keep");
        try { await InstallFiles.PromoteStage(source, target, CancellationToken.None, _ => {});
              throw new Exception("promotion overwrote destination"); }
        catch (IOException) { check(File.ReadAllText(Path.Combine(target, "existing.txt")) == "keep", "existing destination changed"); }
    }
}


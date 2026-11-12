using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;

namespace Operon.Setup;

internal sealed record InstallOptions(string InstallDir, string? Payload = null,
    bool Register = true, bool ForceReinstall = false);
internal sealed record InstallReceipt(string Owner, string Version, string Current, string Profile,
    List<string> Versions, Dictionary<string, string> Shortcuts, string? UninstallKey,
    string? InstallRoot = null);
internal sealed record InstallResult(string Status, string InstallDir, string? Executable, string? Profile,
    string Log, string? Message = null);

// Windows mutexes are thread-owned. Keep acquisition/release on one dedicated
// thread while the async installer awaits I/O on other threads.
internal sealed class InstallLease : IDisposable
{
    private readonly ManualResetEventSlim release = new();
    private readonly Thread thread;
    internal InstallLease(string name)
    {
        using var acquired = new ManualResetEventSlim();
        Exception? error = null;
        thread = new Thread(() => {
            using var mutex = new Mutex(false, name);
            var owned = false;
            try { try { owned = mutex.WaitOne(0); } catch (AbandonedMutexException) { owned = true; }
                if (!owned) throw new InvalidOperationException("Operon 或另一个安装程序正在使用此目录，请关闭后重试。"); }
            catch (Exception e) { error = e; }
            finally { acquired.Set(); }
            if (owned) { release.Wait(); mutex.ReleaseMutex(); }
        }) { IsBackground = true };
        thread.Start(); acquired.Wait();
        if (error is not null) { thread.Join(); release.Dispose(); throw error; }
    }
    public void Dispose() { release.Set(); thread.Join(); release.Dispose(); }
    internal static string Identity(string path) => Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(Path.GetFullPath(path).ToUpperInvariant())))[..24];
}

internal sealed class InstallEngine
{
    private readonly PayloadSpec spec;
    private readonly string work;
    internal string LogPath { get; }
    private readonly IProgress<InstallProgress> progress;
    private readonly object logGate = new();
    internal InstallEngine(PayloadSpec spec, IProgress<InstallProgress> progress, string? workRoot = null)
    {
        this.spec = spec; this.progress = progress;
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var baseDir = Path.GetFullPath(workRoot ?? (string.IsNullOrWhiteSpace(local)
            ? Path.Combine(Path.GetTempPath(), "OperonSetup") : Path.Combine(local, "Operon", "Setup")));
        string CreateWork(string directory)
        {
            InstallFiles.NoLinks(directory);
            Directory.CreateDirectory(directory);
            var attempt = Path.Combine(directory, DateTime.UtcNow.ToString("yyyyMMddTHHmmss") + "-" + Guid.NewGuid().ToString("N")[..8]);
            // An existing base directory may be readable but not writable.
            // Include creation of the actual attempt in the fallback boundary.
            Directory.CreateDirectory(attempt);
            File.WriteAllText(Path.Combine(attempt, "setup.log"), "", Encoding.UTF8);
            return attempt;
        }
        try { work = CreateWork(baseDir); }
        catch (Exception error) when (workRoot is null && error is UnauthorizedAccessException or IOException)
        {
            // Restricted or redirected accounts may deny LocalAppData. Keep
            // installation diagnostics available in the user's writable temp.
            baseDir = Path.Combine(Path.GetTempPath(), "OperonSetup");
            work = CreateWork(baseDir);
        }
        LogPath = Path.Combine(work, "setup.log");
        Log("Operon Setup " + spec.Version + " initialized.");
    }
    private void Log(string line)
    {
        lock (logGate) File.AppendAllText(LogPath, DateTimeOffset.Now.ToString("O") + " " + line + Environment.NewLine, Encoding.UTF8);
    }
    private void Report(string message, int percent) { Log(message); progress.Report(new(message, percent)); }
    private static string ReceiptPath(string root) => Path.Combine(root, "installation.json");

    // Resolve without modifying anything. Both UI and unattended installation
    // use this policy; ownership validation is repeated under the install lease.
    internal static string ResolveDestination(string selected)
    {
        if (string.IsNullOrWhiteSpace(selected)) throw new ArgumentException("请选择安装目录。");
        var root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(selected.Trim()));
        InstallFiles.NoLinks(root);
        if (File.Exists(root)) throw new IOException("安装位置是文件，请选择文件夹。");
        if (Directory.Exists(root)) ValidateConflict(root);
        return root;
    }

    internal static string NamedDestination(string selected)
    {
        if (string.IsNullOrWhiteSpace(selected)) throw new ArgumentException("请选择安装目录。");
        return Path.TrimEndingDirectorySeparator(Path.GetFullPath(selected.Trim()));
    }

    private static void ValidateConflict(string root)
    {
        foreach (var name in new[] { "versions", "workspace" })
        {
            var path = Path.Combine(root, name);
            if (File.Exists(path)) throw new IOException($"安装目录中的 {name} 是文件，请移走后重试。");
        }
        foreach (var name in new[] { "Operon_Uninstall.exe", ".operon-setup.json", "installation.json" })
        {
            var path = Path.Combine(root, name);
            if (Directory.Exists(path)) throw new IOException($"安装目录中的 {name} 是目录，请移走后重试。");
        }
    }

    private static bool Available(string root)
    {
        if (File.Exists(root)) return false;
        if (!Directory.Exists(root) || !Directory.EnumerateFileSystemEntries(root).Any()) return true;
        bool Owned(string path)
        {
            if (!File.Exists(path)) return false;
            using var value = JsonDocument.Parse(File.ReadAllText(path));
            return value.RootElement.ValueKind == JsonValueKind.Object &&
                value.RootElement.TryGetProperty("owner", out var owner) &&
                owner.ValueKind == JsonValueKind.String && owner.GetString() == InstallFiles.Owner;
        }
        bool marker;
        try { marker = Owned(Path.Combine(root, ".operon-setup.json")); }
        catch (JsonException) { marker = false; }
        bool receipt;
        try { receipt = Owned(ReceiptPath(root)); }
        catch (JsonException) when (!marker) { return false; }
        if (!marker && !receipt) return false;
        ReadReceipt(root); // Corrupt owned receipts never become an overwrite request.
        return true;
    }

    private static InstallReceipt? ReadReceipt(string root)
    {
        InstallFiles.NoLinks(root);
        if (!Directory.Exists(root)) return null;
        var file = ReceiptPath(root);
        if (!File.Exists(file))
        {
            // A foreign/non-empty directory is not ours. Installation may
            // coexist with unrelated files; cleanup only removes owned files.
            return null;
        }
        var receipt = JsonSerializer.Deserialize<InstallReceipt>(File.ReadAllText(file), InstallFiles.Json);
        if (receipt?.Owner != InstallFiles.Owner || !receipt.Versions.Contains(receipt.Current))
            throw new InvalidDataException("安装记录无效，请保留此目录并选择新的安装位置。");
        if (receipt.InstallRoot is not null &&
            !string.Equals(Path.GetFullPath(receipt.InstallRoot).TrimEnd(Path.DirectorySeparatorChar),
                root.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("安装记录中的根目录与当前目录不一致，请从原安装目录卸载。");
        foreach (var item in receipt.Versions)
        {
            var path = InstallFiles.Inside(root, item);
            if (Path.GetDirectoryName(path) != Path.Combine(root, "versions")) throw new InvalidDataException("安装记录包含无效版本目录。");
        }
        return receipt;
    }

    private static bool OwnedJson(string path)
    {
        try
        {
            if (!File.Exists(path)) return false;
            using var value = JsonDocument.Parse(File.ReadAllText(path));
            return value.RootElement.ValueKind == JsonValueKind.Object &&
                value.RootElement.TryGetProperty("owner", out var owner) &&
                owner.ValueKind == JsonValueKind.String && owner.GetString() == InstallFiles.Owner;
        }
        catch (Exception) { return false; }
    }

    private static bool OwnedReceipt(string root)
    {
        try
        {
            var file = ReceiptPath(root);
            if (!File.Exists(file)) return false;
            var receipt = JsonSerializer.Deserialize<InstallReceipt>(File.ReadAllText(file), InstallFiles.Json);
            return receipt?.Owner == InstallFiles.Owner;
        }
        catch (Exception) { return false; }
    }

    internal bool HasManagedArtifacts(string root)
    {
        if (!Directory.Exists(root)) return false;
        if (OwnedJson(Path.Combine(root, ".operon-setup.json")) || OwnedReceipt(root)) return true;
        var versions = Path.Combine(root, "versions");
        if (!Directory.Exists(versions)) return false;
        foreach (var directory in Directory.EnumerateDirectories(versions))
            if (OwnedJson(Path.Combine(directory, ".operon-install.json"))) return true;
        return false;
    }

    private async Task<JsonElement> Inspect(string code, CancellationToken token)
    {
        var report = Path.Combine(work, "inspection.json");
        var start = new ProcessStartInfo(InstallFiles.Inside(code, "runtime/python/python.exe")) {
            WorkingDirectory = code, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        foreach (var arg in new[] { "-I", "-X", "utf8", "-B", "-u", InstallFiles.Inside(code, "scripts/install_maintenance.py"), "--trace-stalls" }) start.ArgumentList.Add(arg);
        Operon.Desktop.IsolatedEnvironment.Configure(start, code);
        start.Environment["PYTHONUTF8"] = "1"; start.Environment["PYTHONIOENCODING"] = "utf-8";
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        start.Environment["MPLCONFIGDIR"] = Path.Combine(work, "matplotlib");
        using var lifetime = new Operon.Desktop.ProcessLifetime();
        using var child = Process.Start(start) ?? throw new IOException("无法启动内置运行环境。");
        try { lifetime.Attach(child); } catch { child.Kill(true); throw; }
        child.StandardInput.Close();
        var output = child.StandardOutput.ReadToEndAsync();
        async Task DrainErrors()
        {
            while (await child.StandardError.ReadLineAsync() is { } line) Log("Runtime: " + line);
        }
        var errors = DrainErrors();
        try { await child.WaitForExitAsync(token).WaitAsync(TimeSpan.FromMinutes(10), token); }
        catch
        {
            if (!child.HasExited) child.Kill(true);
            await child.WaitForExitAsync();
            try { await Task.WhenAll(output, errors).WaitAsync(TimeSpan.FromSeconds(5)); }
            catch (TimeoutException) { Log("Runtime diagnostics pipe did not close after cancellation."); }
            throw;
        }
        await errors;
        var result = PersistInspection(await output, report);
        Log("inspect: " + result.GetProperty("status").GetString());
        if (child.ExitCode != 0 || result.GetProperty("status").GetString() == "blocked")
        {
            var details = result.GetProperty("issues").EnumerateArray().Select(e => e.GetProperty("message").GetString());
            var message = string.Join(Environment.NewLine, details);
            Log(message); throw new InvalidOperationException(message);
        }
        return result;
    }

    internal static JsonElement PersistInspection(string output, string report)
    {
        try
        {
            using var data = JsonDocument.Parse(output);
            var value = data.RootElement;
            if (value.ValueKind != JsonValueKind.Object ||
                !value.TryGetProperty("schema_version", out var schema) || schema.ValueKind != JsonValueKind.Number || !schema.TryGetInt32(out var version) || version != 1 ||
                !value.TryGetProperty("status", out var status) || status.ValueKind != JsonValueKind.String ||
                status.GetString() is not ("ready" or "blocked"))
                throw new InvalidDataException("运行环境检查返回了无效报告，详情见安装日志。");
            var result = value.Clone();
            InstallFiles.AtomicJson(report, result);
            return result;
        }
        catch (JsonException error)
        {
            throw new InvalidDataException("运行环境检查未返回有效报告，详情见安装日志。", error);
        }
    }

    internal async Task<InstallResult> Install(InstallOptions options, CancellationToken token)
    {
        string root = ResolveDestination(options.InstallDir);
        using var installLease = new InstallLease("Local\\OperonSetup-" + InstallLease.Identity(root));
        InstallFiles.NoLinks(root);
        var old = ReadReceipt(root);
        string? stage = null, installed = null, resolvedProfile = null;
        InstallLease? profileLease = null;
        InstallUpgrade? upgrade = null;
        IReadOnlyList<UpgradeTarget> upgradeTargets = [];
        var priorLinks = new Dictionary<string, byte[]?>();
        string? registrationKey = null;
        Dictionary<string, (object Value, RegistryValueKind Kind)>? priorRegistration = null;
        string? savedUninstaller = null;
        bool wroteUninstaller = false;
        var committed = false;
        try
        {
            if (old is null && LooksLikeOperonRoot(root) && !options.ForceReinstall)
                throw new InvalidOperationException("此目录已有旧版 Operon 安装。请勾选“强制重装”以在同一个目录重新安装。");
            if (options.ForceReinstall && (old is not null || LooksLikeOperonRoot(root)))
            {
                Report("正在强制卸载安装目录中的旧版本…", 1);
                if (old is not null) RemovePreviousInstallation(root, old);
                RemoveRootExceptWorkspace(root);
                RemoveRegistrationsUnder(root);
                RemoveShortcutsUnder(root);
                old = null;
            }
            var cache = Path.Combine(Path.GetDirectoryName(work)!, "cache");
            var cached = InstallFiles.Inside(cache, spec.Sha256 + ".zip");
            bool reuseCache = options.Payload is not null || (File.Exists(cached) &&
                new FileInfo(cached).Length == spec.Bytes && InstallFiles.Hash(cached) == spec.Sha256);
            var drive = new DriveInfo(Path.GetPathRoot(root)!);
            var cacheDrive = new DriveInfo(Path.GetPathRoot(cache)!);
            bool sameDrive = string.Equals(drive.Name, cacheDrive.Name, StringComparison.OrdinalIgnoreCase);
            long required = InstallFiles.RequiredInstallBytes(spec, InstallFiles.ClusterBytes(root));
            if (!reuseCache && sameDrive) required += spec.Bytes;
            if (drive.AvailableFreeSpace < required)
                throw new IOException($"安装盘空间不足，需要约 {required / 1073741824.0:F1} GiB 可用空间。");
            if (!reuseCache && !sameDrive && cacheDrive.AvailableFreeSpace < spec.Bytes + 128L * 1024 * 1024)
                throw new IOException("安装缓存所在磁盘空间不足，请释放空间后重试。");
            Report("准备安装 Operon " + spec.Version, 0);
            var payload = await InstallFiles.MaterializePayload(spec, cache, options.Payload, progress, token);
            Directory.CreateDirectory(root);
            InstallFiles.AtomicJson(Path.Combine(root, ".operon-setup.json"), new { owner = InstallFiles.Owner });
            var versions = Path.Combine(root, "versions"); Directory.CreateDirectory(versions);
            stage = Path.Combine(versions, ".install-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(stage);
            InstallFiles.AtomicJson(Path.Combine(stage, ".operon-install.json"), new { owner = InstallFiles.Owner, version = spec.Version });
            await InstallFiles.Extract(payload, stage, spec, progress, token);
            Report("正在核对已安装文件…", 76); InstallFiles.VerifyPackage(stage, spec, token);
            var profileId = Guid.NewGuid().ToString("N");
            InstallFiles.AtomicJson(Path.Combine(stage, "operon-install.json"),
                new { schema_version = 1, isolated = true, profile_id = profileId, product = "operon", workspace = "workspace" });
            Report("正在验证独立运行环境…", 82);
            var inspection = await Inspect(stage, token);
            resolvedProfile = inspection.GetProperty("profile").GetProperty("profile_dir").GetString()
                ?? throw new InvalidDataException("用户档案路径无效。");
            if ((resolvedProfile.TrimEnd('\\') + "\\").StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("用户档案必须位于安装目录之外，以便升级和卸载时保留。");
            profileLease = new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(resolvedProfile));
            token.ThrowIfCancellationRequested();
            // A fresh profile is never populated from an old registry or target.
            if (Directory.Exists(resolvedProfile)) throw new IOException("新档案目录已存在，请重新运行安装程序。");
            if (old is not null)
            {
                upgradeTargets = InstallUpgrade.Targets(root, old);
                Report("正在检查旧版本并准备安全更新…", 86);
                upgrade = await InstallUpgrade.Prepare(upgradeTargets, message => Report(message, 88), token);
            }
            Report("正在启用独立安装…", 90);
            var relative = "versions/" + spec.Version + "-" + Guid.NewGuid().ToString("N")[..12];
            installed = InstallFiles.Inside(root, relative);
            Directory.Move(stage, installed); stage = null;
            var shortcuts = new Dictionary<string, string>();
            if (options.Register)
            {
                Report("正在创建快捷方式…", 96);
                foreach (var folder in new[] { Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon") })
                {
                    InstallFiles.NoLinks(folder);
                    Directory.CreateDirectory(folder);
                    var link = Path.Combine(folder, "Operon Studio.lnk");
                    priorLinks[link] = File.Exists(link) ? File.ReadAllBytes(link) : null;
                    CreateShortcut(link, Path.Combine(installed, "Operon Studio.exe"), resolvedProfile);
                    shortcuts[link] = InstallFiles.Hash(link);
                }
                RepairPinnedShortcut(installed, resolvedProfile);
                var uninstall = Path.Combine(root, "Operon_Uninstall.exe");
                if (File.Exists(uninstall)) { savedUninstaller = Path.Combine(work, "previous-uninstaller.exe"); File.Copy(uninstall, savedUninstaller); }
                SaveUninstaller(uninstall);
                wroteUninstaller = true;
                registrationKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudio-" + InstallLease.Identity(root);
                using (var previous = Registry.CurrentUser.OpenSubKey(registrationKey))
                    if (previous is not null) priorRegistration = previous.GetValueNames().ToDictionary(k => k,
                        k => (previous.GetValue(k, null, RegistryValueOptions.DoNotExpandEnvironmentNames)!, previous.GetValueKind(k)));
                using var key = Registry.CurrentUser.CreateSubKey(registrationKey);
                key.SetValue("DisplayName", "Operon Studio"); key.SetValue("DisplayVersion", spec.Version);
                key.SetValue("Publisher", "Operon contributors"); key.SetValue("InstallLocation", root);
                key.SetValue("DisplayIcon", Path.Combine(installed, "Operon Studio.exe"));
                key.SetValue("UninstallString", $"\"{uninstall}\" --uninstall --install-dir \"{root}\"");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord); key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            }
            var allVersions = old?.Versions.ToList() ?? [];
            allVersions.Add(relative);
            var receipt = new InstallReceipt(InstallFiles.Owner, spec.Version, relative, resolvedProfile, allVersions, shortcuts, registrationKey, root);
            InstallFiles.AtomicJson(ReceiptPath(root), receipt); committed = true;
            // Old software is removable only through its own receipt. Failure to
            // clean an old version never redirects or blocks the fresh runtime.
            if (old is not null)
            {
                Report("正在清理旧版本；用户档案会保留…", 98);
                foreach (var previous in old.Versions)
                    try { CleanVersion(root, previous, Path.GetDirectoryName(old.Profile)!,
                        upgradeTargets.FirstOrDefault(t => t.Directory == InstallFiles.Inside(root, previous))?.Profile); }
                    catch (Exception cleanupError) { Log("Old version retained: " + cleanupError.Message); }
            }
            Report("安装完成", 100);
            return new("installed", root, Path.Combine(installed, "Operon Studio.exe"), resolvedProfile, LogPath);
        }
        catch (Exception error)
        {
            Log(error.ToString());
            if (!committed)
            {
                foreach (var (path, content) in priorLinks)
                    try { if (content is null) File.Delete(path); else File.WriteAllBytes(path, content); } catch (Exception e) { Log("Shortcut restore: " + e.Message); }
                if (registrationKey is not null)
                    try {
                        Registry.CurrentUser.DeleteSubKeyTree(registrationKey, false);
                        if (priorRegistration is not null) { using var key = Registry.CurrentUser.CreateSubKey(registrationKey);
                            foreach (var (name, value) in priorRegistration) key.SetValue(name, value.Value, value.Kind); }
                    } catch (Exception e) { Log("Registration restore: " + e.Message); }
                if (wroteUninstaller)
                    try { var target = Path.Combine(root, "Operon_Uninstall.exe");
                        if (savedUninstaller is not null) File.Copy(savedUninstaller, target, true); else File.Delete(target);
                    } catch (Exception e) { Log("Uninstaller restore: " + e.Message); }
                foreach (var candidate in new[] { stage, installed }.Where(p => p is not null))
                    try { InstallFiles.DeleteOwnedStage(Path.Combine(root, "versions"), candidate!); } catch (Exception e) { Log("Stage retained: " + e.Message); }
            }
            throw;
        }
        finally { upgrade?.Dispose(); profileLease?.Dispose(); }
    }

    private void RepairPinnedShortcut(string installed, string profile)
    {
        try
        {
            var pinned = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar");
            var link = Path.Combine(pinned, "Operon Studio.lnk");
            if (!File.Exists(link)) return;
            CreateShortcut(link, Path.Combine(installed, "Operon Studio.exe"), profile);
        }
        catch (Exception e) { Log("Taskbar shortcut repair: " + e.Message); }
    }

    private static void CreateShortcut(string path, string executable, string profile)
    {
        var type = Type.GetTypeFromProgID("WScript.Shell") ?? throw new NotSupportedException("无法创建 Windows 快捷方式。");
        dynamic shell = Activator.CreateInstance(type)!;
        try {
            dynamic shortcut = shell.CreateShortcut(path);
            try { shortcut.TargetPath = executable; shortcut.Arguments = $"--profile-dir \"{profile}\"";
                shortcut.IconLocation = executable + ",0";
                shortcut.WorkingDirectory = Path.GetDirectoryName(executable); shortcut.Description = "Operon Studio"; shortcut.Save(); }
            finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut); }
        } finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
    }

    private static void SaveUninstaller(string destination)
    {
        // Copy just the self-contained program, not the large appended payload.
        using var source = File.OpenRead(Environment.ProcessPath!);
        source.Seek(-32, SeekOrigin.End); byte[] footer = new byte[32]; source.ReadExactly(footer);
        if (!footer.AsSpan(0, InstallFiles.FooterMagic.Length).SequenceEqual(InstallFiles.FooterMagic)) throw new InvalidDataException("安装包缺少卸载组件。");
        long length = BitConverter.ToInt64(footer, 16); source.Position = 0;
        var temporary = destination + ".tmp-" + Guid.NewGuid().ToString("N");
        try {
            using (var output = File.Create(temporary)) {
                byte[] buffer = new byte[1024 * 1024]; long copied = 0;
                while (copied < length) { int n = source.Read(buffer,0,(int)Math.Min(buffer.Length,length-copied));
                    if (n == 0) throw new EndOfStreamException(); output.Write(buffer,0,n); copied += n; }
            }
            File.Move(temporary, destination, true);
        } finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    internal InstallResult Uninstall(string installDir)
    {
        string root = Path.GetFullPath(installDir).TrimEnd(Path.DirectorySeparatorChar);
        // A running host or backend keeps files open and also holds the profile
        // lease. End only processes that live under this installation, before
        // the lease is requested, so a full uninstall can actually finish.
        var receipt = ReadReceipt(root);
        if (receipt is null) return UninstallManagedOnly(root);
        DisconnectAgents(receipt.Profile);
        var stopped = TerminateManagedProcesses(root);
        if (stopped > 0) Log($"Stopped {stopped} process(es) under the installation.");
        using var lease = new InstallLease("Local\\OperonSetup-" + InstallLease.Identity(root));
        using var profileLease = new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(receipt.Profile));
        Report("正在卸载软件；用户档案和分析数据会保留…", 0);
        var expectedKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudio-" + InstallLease.Identity(root);
        if (receipt.UninstallKey is not null && receipt.UninstallKey != expectedKey) throw new InvalidDataException("卸载注册信息无效。");
        var allowedLinks = new[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Operon Studio.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon", "Operon Studio.lnk") };
        foreach (var path in receipt.Shortcuts.Keys) {
            if (!allowedLinks.Contains(path, StringComparer.OrdinalIgnoreCase)) throw new InvalidDataException("快捷方式记录无效。");
            InstallFiles.NoLinks(path);
        }
        foreach (var relative in receipt.Versions) CleanVersion(root, relative, Path.GetDirectoryName(receipt.Profile)!, receipt.Profile);
        RemoveAutostart();
        foreach (var (path, hash) in receipt.Shortcuts)
            if (File.Exists(path) && (InstallFiles.Hash(path) == hash || ShortcutIsStale(path, root))) File.Delete(path);
        RemovePinnedShortcut(root);
        if (receipt.UninstallKey is not null)
        {
            Registry.CurrentUser.DeleteSubKeyTree(expectedKey, false);
        }
        RemoveRegistrationsUnder(root);
        RemoveShortcutsUnder(root);
        var uninstaller = Path.Combine(root,"Operon_Uninstall.exe");
        if (File.Exists(uninstaller) && !string.Equals(uninstaller, Environment.ProcessPath, StringComparison.OrdinalIgnoreCase))
        {
            for (var attempt = 0; attempt < 20 && File.Exists(uninstaller); attempt++)
            {
                try { File.Delete(uninstaller); }
                catch (IOException) { Thread.Sleep(250); }
                catch (UnauthorizedAccessException) { Thread.Sleep(250); }
            }
        }
        RemoveRootExceptWorkspace(root);
        Log("Uninstall root cleaned; workspace preserved.");
        Report("已卸载 Operon；用户档案、路线、数据和任务记录均已保留。",100);
        return new("uninstalled", root, null, receipt.Profile, LogPath);
    }

    private InstallResult UninstallManagedOnly(string root)
    {
        Report("正在卸载 Operon…", 0);
        using var lease = new InstallLease("Local\\OperonSetup-" + InstallLease.Identity(root));
        if (LooksLikeOperonRoot(root))
        {
            DisconnectAgents(null);
            TerminateManagedProcesses(root);
            RemoveRegistrationsUnder(root);
            RemoveShortcutsUnder(root);
            RemoveAutostart();
            RemoveRootExceptWorkspace(root);
        }
        else
        {
            RemovePreviousInstallation(root, null);
        }
        Report("已卸载 Operon；工作区保留。", 100);
        return new("uninstalled", root, null, null, LogPath);
    }

    private void RemoveManagedVersions(string root)
    {
        var versions = Path.Combine(root, "versions");
        if (!Directory.Exists(versions)) return;
        foreach (var directory in Directory.EnumerateDirectories(versions))
        {
            if (!OwnedJson(Path.Combine(directory, ".operon-install.json"))) continue;
            try { Directory.Delete(directory, true); }
            catch (Exception error) { Log("Managed version retained: " + error.Message); }
        }
        try
        {
            if (Directory.Exists(versions) && !Directory.EnumerateFileSystemEntries(versions).Any()) Directory.Delete(versions);
        }
        catch (Exception error) { Log("Versions directory retained: " + error.Message); }
    }

    private void RemoveManagedRegistration(string root)
    {
        var key = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudio-" + InstallLease.Identity(root);
        try
        {
            using var existing = Registry.CurrentUser.OpenSubKey(key);
            if (existing is null) return;
            var location = existing.GetValue("InstallLocation") as string;
            if (!string.IsNullOrWhiteSpace(location) &&
                !string.Equals(Path.GetFullPath(location).TrimEnd(Path.DirectorySeparatorChar),
                    root.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase)) return;
            Registry.CurrentUser.DeleteSubKeyTree(key, false);
        }
        catch (Exception error) { Log("Registration retained: " + error.Message); }
    }

    internal bool LooksLikeOperonRoot(string root)
    {
        if (!Directory.Exists(root)) return false;
        if (File.Exists(Path.Combine(root, "Operon_Uninstall.exe"))) return true;
        if (OwnedJson(Path.Combine(root, ".operon-setup.json")) || OwnedReceipt(root)) return true;
        try
        {
            foreach (var directory in Directory.EnumerateDirectories(root))
            {
                if (string.Equals(Path.GetFileName(directory), "workspace", StringComparison.OrdinalIgnoreCase)) continue;
                if (File.Exists(Path.Combine(directory, "Operon_Uninstall.exe"))) return true;
                if (OwnedReceipt(directory)) return true;
            }
        }
        catch (Exception) { }
        return false;
    }

    private void RemoveRootExceptWorkspace(string root)
    {
        if (!Directory.Exists(root)) return;
        foreach (var entry in Directory.EnumerateFileSystemEntries(root))
        {
            if (string.Equals(Path.GetFileName(entry), "workspace", StringComparison.OrdinalIgnoreCase)) continue;
            try
            {
                if (Directory.Exists(entry)) Directory.Delete(entry, true);
                else File.Delete(entry);
            }
            catch (Exception error) { Log("Root entry retained: " + entry + " (" + error.Message + ")"); }
        }
    }

    private static bool IsUnderOrEqual(string path, string root)
    {
        var full = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar);
        var prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
        return string.Equals(full, prefix, StringComparison.OrdinalIgnoreCase) ||
            full.StartsWith(prefix + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    private void RemoveRegistrationsUnder(string root)
    {
        try
        {
            using var uninstall = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall");
            if (uninstall is null) return;
            foreach (var name in uninstall.GetSubKeyNames())
            {
                if (!name.StartsWith("OperonStudio-", StringComparison.OrdinalIgnoreCase)) continue;
                using var key = uninstall.OpenSubKey(name);
                if (key?.GetValue("InstallLocation") is not string location) continue;
                if (!IsUnderOrEqual(location, root)) continue;
                Registry.CurrentUser.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + name, false);
            }
        }
        catch (Exception error) { Log("Registration cleanup retained: " + error.Message); }
    }

    private static void RemoveShortcutsUnder(string root)
    {
        var links = new[] {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Operon Studio.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon", "Operon Studio.lnk")
        };
        foreach (var path in links)
        {
            try { if (File.Exists(path) && ShortcutIsStale(path, root)) File.Delete(path); }
            catch (Exception) { }
        }
    }

    internal bool HasInstallation(string root)
    {
        // This is only a UI probe for the optional force-reinstall checkbox.
        // A foreign/non-empty folder is not an Operon installation; Install will
        // report the actionable directory error if the user actually proceeds.
        try { return ReadReceipt(root) is not null || LooksLikeOperonRoot(root); }
        catch (Exception) { return false; }
    }

    private void RemovePreviousInstallation(string root, InstallReceipt? receipt)
    {
        if (receipt is null)
        {
            DisconnectAgents(null);
            var foreignStopped = TerminateManagedProcesses(root);
            if (foreignStopped > 0) Log($"Stopped {foreignStopped} owned process(es).");
            RemoveManagedVersions(root);
            RemoveAutostart();
            RemovePinnedShortcut(root);
            RemoveManagedRegistration(root);
            if (OwnedReceipt(root)) try { File.Delete(ReceiptPath(root)); } catch (Exception) { }
            var ownsMarker = OwnedJson(Path.Combine(root, ".operon-setup.json"));
            if (ownsMarker) try { File.Delete(Path.Combine(root, ".operon-setup.json")); } catch (Exception) { }
            var foreignUninstaller = Path.Combine(root, "Operon_Uninstall.exe");
            if (ownsMarker) try { if (File.Exists(foreignUninstaller)) File.Delete(foreignUninstaller); } catch (Exception) { }
            return;
        }
        // Installing into an existing directory replaces the previous product
        // in place. Stop only processes owned by that installation, then remove
        // its managed versions and shell integration. Profiles, workspace data
        // and analysis results stay outside this deletion.
        DisconnectAgents(receipt.Profile);
        var stopped = TerminateManagedProcesses(root);
        if (stopped > 0) Log($"Stopped {stopped} process(es) from the previous installation.");
        var allowedLinks = new[] {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Operon Studio.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon", "Operon Studio.lnk")
        };
        foreach (var path in receipt.Shortcuts.Keys)
        {
            if (!allowedLinks.Contains(path, StringComparer.OrdinalIgnoreCase)) continue;
            try { if (File.Exists(path)) File.Delete(path); }
            catch (Exception error) { Log("Old shortcut retained: " + error.Message); }
        }
        RemoveAutostart();
        RemovePinnedShortcut(root);
        foreach (var relative in receipt.Versions)
            try { CleanVersion(root, relative, Path.GetDirectoryName(receipt.Profile)!, receipt.Profile); }
            catch (Exception error) { Log("Old version retained: " + error.Message); }
        if (receipt.UninstallKey is not null)
            try { Registry.CurrentUser.DeleteSubKeyTree(receipt.UninstallKey, false); }
            catch (Exception error) { Log("Old registration retained: " + error.Message); }
        try { File.Delete(ReceiptPath(root)); } catch (Exception error) { Log("Old receipt retained: " + error.Message); }
        try { File.Delete(Path.Combine(root, ".operon-setup.json")); } catch (Exception error) { Log("Old setup marker retained: " + error.Message); }
        var uninstaller = Path.Combine(root, "Operon_Uninstall.exe");
        try { if (File.Exists(uninstaller)) File.Delete(uninstaller); }
        catch (Exception error) { Log("Old uninstaller retained: " + error.Message); }
        var versions = Path.Combine(root, "versions");
        try { if (Directory.Exists(versions) && !Directory.EnumerateFileSystemEntries(versions).Any()) Directory.Delete(versions); }
        catch (Exception error) { Log("Old versions directory retained: " + error.Message); }
    }

    private void DisconnectAgents(string? profile)
    {
        var ports = new HashSet<int>();
        void AddProfile(string? directory)
        {
            if (string.IsNullOrWhiteSpace(directory)) return;
            try
            {
                var file = Path.Combine(directory, "port.txt");
                if (File.Exists(file) && int.TryParse(File.ReadAllText(file), out var port) && port is > 0 and < 65536)
                    ports.Add(port);
            }
            catch (Exception) { }
        }
        AddProfile(profile);
        var profiles = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".operon", "profiles");
        if (Directory.Exists(profiles))
            foreach (var directory in Directory.EnumerateDirectories(profiles)) AddProfile(directory);
        foreach (var port in ports) if (PortOpen(port)) DisconnectPort(port);
    }

    private static bool PortOpen(int port)
    {
        try
        {
            using var client = new System.Net.Sockets.TcpClient();
            var task = client.ConnectAsync("127.0.0.1", port);
            return task.Wait(150) && client.Connected;
        }
        catch (Exception) { return false; }
    }

    private void DisconnectPort(int port)
    {
        try
        {
            using var http = new HttpClient(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(3) };
            using var bootstrap = JsonDocument.Parse(http.GetStringAsync($"http://127.0.0.1:{port}/api/bootstrap").GetAwaiter().GetResult());
            var token = bootstrap.RootElement.GetProperty("token").GetString();
            if (string.IsNullOrEmpty(token)) return;
            using var request = new HttpRequestMessage(HttpMethod.Post, $"http://127.0.0.1:{port}/api/agent/connections/revoke-all");
            request.Headers.Add("X-Studio-Token", token);
            request.Content = new StringContent("{}", Encoding.UTF8, "application/json");
            using var response = http.Send(request);
            Log("Disconnected MCP clients: " + (int)response.StatusCode);
        }
        catch (Exception error) { Log("MCP disconnect skipped: " + error.Message); }
    }

    internal static int TerminateManagedProcesses(string installRoot)
    {
        var root = Path.GetFullPath(installRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var self = Environment.ProcessId;
        var stopped = new HashSet<int>();
        for (var attempt = 0; attempt < 3; attempt++)
        {
            foreach (var process in Process.GetProcesses())
            {
                if (process.Id == self) { process.Dispose(); continue; }
                try
                {
                    var image = process.MainModule?.FileName;
                    if (string.IsNullOrWhiteSpace(image)) continue;
                    var full = Path.GetFullPath(image);
                    if (!full.StartsWith(root, StringComparison.OrdinalIgnoreCase)) continue;
                    if (string.Equals(Path.GetFileName(full), "Operon_Uninstall.exe", StringComparison.OrdinalIgnoreCase)) continue;
                    process.Kill(entireProcessTree: true);
                    process.WaitForExit(3000);
                    stopped.Add(process.Id);
                }
                catch (Exception) { /* access denied or already exited */ }
                finally { process.Dispose(); }
            }
            if (attempt < 2) Thread.Sleep(500);
        }
        // Verify that nothing under the installation survived; refusing here is
        // safer than deleting a partially locked tree.
        foreach (var process in Process.GetProcesses())
        {
            if (process.Id == self) { process.Dispose(); continue; }
            try
            {
                var image = process.MainModule?.FileName;
                if (string.IsNullOrWhiteSpace(image)) continue;
                var full = Path.GetFullPath(image);
                if (!full.StartsWith(root, StringComparison.OrdinalIgnoreCase)) continue;
                if (string.Equals(Path.GetFileName(full), "Operon_Uninstall.exe", StringComparison.OrdinalIgnoreCase)) continue;
                throw new InvalidOperationException($"仍有进程占用安装目录，无法完全卸载（PID {process.Id}：{image}）。请从任务管理器结束该进程后重试。");
            }
            catch (InvalidOperationException) { throw; }
            catch (Exception) { }
            finally { process.Dispose(); }
        }
        return stopped.Count;
    }

    private static bool ShortcutIsStale(string path, string root)
    {
        try
        {
            var type = Type.GetTypeFromProgID("WScript.Shell");
            if (type is null) return false;
            dynamic shell = Activator.CreateInstance(type)!;
            try
            {
                dynamic shortcut = shell.CreateShortcut(path);
                try
                {
                    var target = (string?)shortcut.TargetPath ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(target) || !File.Exists(target)) return true;
                    var prefix = root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    return Path.GetFullPath(target).StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
                }
                finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut); }
            }
            finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
        }
        catch (Exception) { return false; }
    }

    private static void RemovePinnedShortcut(string root)
    {
        try
        {
            var pinned = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar");
            var link = Path.Combine(pinned, "Operon Studio.lnk");
            if (File.Exists(link) && ShortcutIsStale(link, root)) File.Delete(link);
        }
        catch (Exception) { }
    }

    private static void RemoveAutostart()
    {
        try
        {
            using var run = Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Run", writable: true);
            if (run is not null)
                foreach (var value in new[] { "Operon Studio", "OperonStudio" })
                    run.DeleteValue(value, throwOnMissingValue: false);
        }
        catch (Exception) { }
        try
        {
            var startup = Environment.GetFolderPath(Environment.SpecialFolder.Startup);
            foreach (var name in new[] { "Operon Studio.lnk" })
            {
                var path = Path.Combine(startup, name);
                if (File.Exists(path)) File.Delete(path);
            }
        }
        catch (Exception) { }
    }

    internal static void CleanVersion(string root, string relative, string profiles, string? heldProfile = null)
        {
            var version = InstallFiles.Inside(root, relative);
            if (!Directory.Exists(version) || !File.Exists(Path.Combine(version, "package-manifest.json"))) return;
            using var identity = JsonDocument.Parse(File.ReadAllText(InstallFiles.Inside(version, "operon-install.json")));
            var id = identity.RootElement.GetProperty("profile_id").GetString();
            if (!Guid.TryParseExact(id, "N", out _)) throw new InvalidDataException("旧安装档案标识无效，原文件已保留。");
            var profile = Path.Combine(profiles, id!);
            using var versionLease = string.Equals(profile, heldProfile, StringComparison.OrdinalIgnoreCase)
                ? null : new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(profile));
            // Only delete manifest-listed software files. Preserve unexpected
            // user files and any changed/linked paths for manual inspection.
            using var manifest = JsonDocument.Parse(File.ReadAllText(InstallFiles.Inside(version, "package-manifest.json")));
            foreach (var item in manifest.RootElement.GetProperty("files").EnumerateArray())
            {
                var path = InstallFiles.Inside(version, item.GetProperty("path").GetString()!);
                if (File.Exists(path) && InstallFiles.Hash(path) == item.GetProperty("sha256").GetString()) File.Delete(path);
            }
            File.Delete(Path.Combine(version, "package-manifest.json")); File.Delete(Path.Combine(version, ".operon-install.json"));
            File.Delete(Path.Combine(version, "operon-install.json"));
            // Python creates __pycache__ after installation. It is generated
            // software state, not a user file, and would otherwise keep the
            // version directory and the uninstall root alive.
            foreach (var cache in Directory.EnumerateDirectories(version, "__pycache__", SearchOption.AllDirectories).ToList())
            {
                try { InstallFiles.NoLinks(cache); Directory.Delete(cache, true); }
                catch (Exception e) { Console.Error.WriteLine("Cache retained: " + e.Message); }
            }
            void EmptyDirectories(string directory) {
                foreach (var child in Directory.EnumerateDirectories(directory)) { InstallFiles.NoLinks(child); EmptyDirectories(child); }
                if (!Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
            }
            EmptyDirectories(version);
        }
}

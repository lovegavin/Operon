using System.ComponentModel;
using System.Diagnostics;
using System.Text.Json;

namespace BioPipe.Setup;

internal sealed record UpgradeTarget(string Directory, string Profile);

// Never terminate processes by name. A managed version path is the boundary;
// normal window closure preserves the desktop's draft-flush and cancel prompts.
internal sealed class InstallUpgrade : IDisposable
{
    private readonly List<InstallLease> leases = [];
    internal static IReadOnlyList<UpgradeTarget> Targets(string root, InstallReceipt receipt)
    {
        var targets = new List<UpgradeTarget>();
        foreach (var relative in receipt.Versions)
        {
            var directory = InstallFiles.Inside(root, relative);
            if (!Directory.Exists(directory)) continue;
            var marker = Path.Combine(directory, "biopipe-install.json");
            if (!File.Exists(marker)) continue; // Already cleaned; unknown files are retained.
            using var document = JsonDocument.Parse(File.ReadAllText(marker));
            var id = document.RootElement.GetProperty("profile_id").GetString();
            if (!Guid.TryParseExact(id, "N", out _)) throw new InvalidDataException("旧版本的档案标识无效，原文件已保留。");
            targets.Add(new(directory, Path.Combine(Path.GetDirectoryName(receipt.Profile)!, id!)));
        }
        return targets;
    }

    private sealed record OwnedProcess(int Id, DateTime Started, string Executable);
    private static List<OwnedProcess> Processes(IReadOnlyList<UpgradeTarget> targets)
    {
        var result = new List<OwnedProcess>();
        foreach (var process in Process.GetProcesses())
        {
            using (process)
            try
            {
                var executable = process.MainModule?.FileName;
                if (executable is not null && targets.Any(target => executable.StartsWith(
                        Path.TrimEndingDirectorySeparator(target.Directory) + Path.DirectorySeparatorChar,
                        StringComparison.OrdinalIgnoreCase)))
                    result.Add(new(process.Id, process.StartTime, executable));
            }
            catch (Exception error) when (error is Win32Exception or InvalidOperationException or NotSupportedException)
            { /* Exited/other-account processes cannot be selected or signalled. */ }
        }
        return result;
    }

    private static bool IsHost(OwnedProcess process) => new[] { "Operon Studio.exe", "BioPipe Studio.exe" }
        .Contains(Path.GetFileName(process.Executable), StringComparer.OrdinalIgnoreCase);

    internal static void CheckRecordedTasks(string profile)
    {
        var data = Path.Combine(profile, "workspace", ".studio");
        CheckDataTasks(data);
    }

    internal static void CheckDataTasks(string data)
    {
        // Do not use the UI's last-60 history: an older active job may be below it.
        foreach (var kind in new[] { "jobs", "executions" })
        {
            var directory = Path.Combine(data, kind);
            if (!Directory.Exists(directory)) continue;
            InstallFiles.NoLinks(directory);
            foreach (var child in Directory.EnumerateDirectories(directory))
            {
                InstallFiles.NoLinks(child);
                var path = Path.Combine(child, "job.json");
                if (!File.Exists(path)) continue;
                using var document = JsonDocument.Parse(File.ReadAllText(path));
                var job = document.RootElement;
                if (!job.TryGetProperty("status", out var status) || status.GetString() is not
                    ("complete" or "failed" or "cancelled"))
                    throw new InvalidOperationException($"旧版本仍有未结束的任务（{Path.GetFileName(child)}）。请在 Operon 中等待完成或停止任务，再点击重新安装。原安装尚未切换。");
            }
        }
        var remote = Path.Combine(data, "remote", "profiles.json");
        if (File.Exists(remote))
        {
            InstallFiles.NoLinks(remote);
            using var document = JsonDocument.Parse(File.ReadAllText(remote));
            var state = document.RootElement;
            var pending = state.TryGetProperty("pending", out var requests) && requests.EnumerateObject().Any();
            var active = state.TryGetProperty("jobs", out var jobs) && jobs.EnumerateObject().Any(job =>
                !job.Value.TryGetProperty("summary", out var summary) || !summary.TryGetProperty("status", out var status) ||
                status.GetString() is not ("complete" or "failed" or "cancelled"));
            if (pending || active) throw new InvalidOperationException("旧版本仍有未结束或待确认的服务器任务。请先在旧窗口核对任务状态，再点击重新安装。");
        }
    }

    private static void CheckPoolWorkspaces(IReadOnlyList<UpgradeTarget> targets, List<OwnedProcess> processes)
    {
        // Older desktop hosts may own a Windows Job Object containing their
        // pool. Protect work accepted from OTHER workspaces before WM_CLOSE too.
        foreach (var home in targets.Select(t => Directory.GetParent(t.Profile)?.Parent?.Parent?.FullName).Distinct())
        {
            if (home is null) continue;
            var pool = Path.Combine(home, ".biopipe", "admission", Environment.MachineName, "managed-pool");
            var instance = Path.Combine(pool, "instance.json");
            if (!File.Exists(instance)) continue;
            InstallFiles.NoLinks(instance);
            using var record = JsonDocument.Parse(File.ReadAllText(instance));
            var owner = record.RootElement.GetProperty("owner");
            var pid = owner.GetProperty("pid").GetInt32();
            var created = owner.GetProperty("created").GetDouble();
            if (!processes.Any(p => p.Id == pid && Math.Abs(new DateTimeOffset(p.Started).ToUnixTimeMilliseconds() / 1000.0 - created) < .1)) continue;
            var registry = Path.Combine(pool, "workspaces.json");
            InstallFiles.NoLinks(registry);
            using var registrations = JsonDocument.Parse(File.ReadAllText(registry));
            foreach (var entry in registrations.RootElement.EnumerateObject())
            {
                var data = entry.Value.GetProperty("data_dir").GetString()!;
                if (!Path.IsPathFullyQualified(data)) throw new InvalidDataException("共享池工作区记录无效，请保留旧安装并检查日志。");
                InstallFiles.NoLinks(data);
                CheckDataTasks(data);
            }
        }
    }

    private static async Task CheckWindow(UpgradeTarget target, CancellationToken token)
    {
        // Old releases have no installer shutdown endpoint. Verify their profile
        // through the existing read-only bootstrap before requesting WM_CLOSE.
        var portFile = Path.Combine(target.Profile, "port.txt");
        if (!File.Exists(portFile) || !int.TryParse(File.ReadAllText(portFile), out var port) || port is < 1 or > 65535)
            throw new InvalidOperationException("旧版 Operon 尚未就绪，无法确认任务状态。请关闭旧窗口后点击重新安装。");
        using var http = new HttpClient(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(8) };
        using var document = JsonDocument.Parse(await http.GetStringAsync($"http://127.0.0.1:{port}/api/bootstrap", token));
        var value = document.RootElement;
        if (!value.GetProperty("desktop").GetBoolean() || !string.Equals(
                Path.GetFullPath(value.GetProperty("storage").GetProperty("profile_dir").GetString()!),
                Path.GetFullPath(target.Profile), StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("旧窗口与安装档案不匹配。请手动关闭旧版 Operon 后重试。");
        foreach (var job in value.GetProperty("history").EnumerateArray())
            if (job.GetProperty("status").GetString() is not ("complete" or "failed" or "cancelled"))
                throw new InvalidOperationException("旧版本仍有运行、上传或排队中的任务。请等待完成或在任务管理中停止，再点击重新安装。");
    }

    internal static async Task<InstallUpgrade> Prepare(IReadOnlyList<UpgradeTarget> targets,
        Action<string> report, CancellationToken token, TimeSpan? timeout = null)
    {
        var session = new InstallUpgrade();
        try
        {
            var processes = Processes(targets);
            var hosts = processes.Where(IsHost).ToList();
            CheckPoolWorkspaces(targets, processes);
            // Check every affected window before closing any of them.
            foreach (var target in targets.Where(t => processes.Any(p => p.Executable.StartsWith(
                         t.Directory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))))
            {
                CheckRecordedTasks(target.Profile);
                if (hosts.Any(p => string.Equals(Path.GetDirectoryName(p.Executable), target.Directory, StringComparison.OrdinalIgnoreCase)))
                    await CheckWindow(target, token);
            }
            foreach (var host in hosts)
            {
                token.ThrowIfCancellationRequested();
                try
                {
                    using var process = Process.GetProcessById(host.Id);
                    if (process.StartTime != host.Started) continue;
                    report($"正在保存草稿并关闭旧版 Operon（PID {host.Id}）…");
                    if (!process.CloseMainWindow())
                        throw new IOException($"旧版窗口暂时无法关闭（PID {host.Id}）。请关闭旧窗口后点击重新安装。");
                }
                catch (ArgumentException) { /* Already exited. */ }
            }
            var deadline = Stopwatch.StartNew();
            var limit = timeout ?? TimeSpan.FromSeconds(30);
            var leased = false;
            if (processes.Count > 0) report("正在等待旧版后台和共享池安全退出…");
            while (true)
            {
                token.ThrowIfCancellationRequested();
                processes = Processes(targets);
                if (!leased && !processes.Any(IsHost))
                {
                    foreach (var profile in targets.Select(t => t.Profile).Distinct(StringComparer.OrdinalIgnoreCase))
                        session.leases.Add(new InstallLease("Local\\BioPipeStudio-" + InstallLease.Identity(profile)));
                    leased = true; // Prevent the old shortcuts from reopening during the switch.
                }
                if (leased && processes.Count == 0) return session;
                if (deadline.Elapsed >= limit)
                    throw new IOException("旧版本尚未安全退出，安装未切换。请处理旧窗口中的提示，关闭使用旧版本的 CLI / Agent，或等待后台任务完成后点击重新安装。仍在运行：" +
                        string.Join(", ", processes.Select(p => $"{Path.GetFileName(p.Executable)} (PID {p.Id})")));
                await Task.Delay(300, token);
            }
        }
        catch { session.Dispose(); throw; }
    }

    public void Dispose() { foreach (var lease in leases) lease.Dispose(); leases.Clear(); }
}

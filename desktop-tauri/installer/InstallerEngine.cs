using Microsoft.Win32;
using Operon.Setup;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Operon.Setup.Experimental;

internal static class ProductIdentity
{
    internal const string Product = "operon-studio-experimental";
    internal const string Channel = "experimental";
    internal const string HostVersion = "0.1.0";
    internal const string ManagementRelease = "5.3.0";
    internal const string HostExe = "operon-desktop-experimental.exe";
    internal const string ManifestName = "experimental-manifest.json";
    internal const string ProfileMarker = ".operon-experimental.json";
    internal const string InstanceLock = ".operon-instance.lock";
    internal const string MaintenanceReceipt = ".operon-maintenance-host.json";
    internal static string DefaultRoot => System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Programs", "Operon Studio Experimental");
}

internal sealed class InstallerException : Exception
{
    internal int Code { get; }
    internal InstallerException(int code, string message, Exception? inner = null) : base(message, inner) => Code = code;
}

internal sealed class InstallerLog : IDisposable
{
    private readonly StreamWriter _writer;
    internal string Path { get; }

    private InstallerLog(string path, StreamWriter writer) { Path = path; _writer = writer; }

    internal static InstallerLog Create()
    {
        var directory = System.IO.Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Operon Studio Experimental", "installer-logs");
        try
        {
            Directory.CreateDirectory(directory);
            var path = System.IO.Path.Combine(directory,
                $"installer-{DateTime.UtcNow:yyyyMMdd-HHmmss}-{Environment.ProcessId}.log");
            return new InstallerLog(path, new StreamWriter(path, append: true, new UTF8Encoding(false)) { AutoFlush = true });
        }
        catch
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(),
                $"operon-experimental-installer-{Environment.ProcessId}.log");
            return new InstallerLog(path, new StreamWriter(path, append: true, new UTF8Encoding(false)) { AutoFlush = true });
        }
    }

    internal void Write(string message) => _writer.WriteLine($"{DateTime.UtcNow:O} {message}");
    public void Dispose() => _writer.Dispose();
}

internal sealed class ManifestComponent
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("bytes")] public long Bytes { get; set; }
}

internal sealed class ExperimentalManifest
{
    [JsonPropertyName("schema")] public int Schema { get; set; }
    [JsonPropertyName("product")] public string Product { get; set; } = "";
    [JsonPropertyName("channel")] public string Channel { get; set; } = "";
    [JsonPropertyName("build_id")] public string BuildId { get; set; } = "";
    [JsonPropertyName("host_version")] public string HostVersion { get; set; } = "";
    [JsonPropertyName("management_release")] public string ManagementRelease { get; set; } = "";
    [JsonPropertyName("source_commit")] public string SourceCommit { get; set; } = "";
    [JsonPropertyName("source_dirty")] public bool SourceDirty { get; set; }
    [JsonPropertyName("payload_id")] public string PayloadId { get; set; } = "";
    [JsonPropertyName("locks")] public Dictionary<string, string> Locks { get; set; } = new(StringComparer.Ordinal);
    [JsonPropertyName("components")] public List<ManifestComponent> Components { get; set; } = new();
    [JsonPropertyName("files")] public List<ManifestFile> Files { get; set; } = new();
}

internal sealed class InstalledVersion
{
    [JsonPropertyName("build_id")] public string BuildId { get; set; } = "";
    [JsonPropertyName("manifest_sha256")] public string ManifestSha256 { get; set; } = "";
    [JsonPropertyName("payload_id")] public string PayloadId { get; set; } = "";
    [JsonPropertyName("installed_utc")] public string InstalledUtc { get; set; } = "";
}

internal sealed class InstalledState
{
    [JsonPropertyName("schema")] public int Schema { get; set; } = 1;
    [JsonPropertyName("product")] public string Product { get; set; } = ProductIdentity.Product;
    [JsonPropertyName("channel")] public string Channel { get; set; } = ProductIdentity.Channel;
    [JsonPropertyName("installation_id")] public string InstallationId { get; set; } = "";
    [JsonPropertyName("versions")] public List<InstalledVersion> Versions { get; set; } = new();
}

internal sealed class CurrentPointer
{
    [JsonPropertyName("schema")] public int Schema { get; set; } = 1;
    [JsonPropertyName("product")] public string Product { get; set; } = ProductIdentity.Product;
    [JsonPropertyName("channel")] public string Channel { get; set; } = ProductIdentity.Channel;
    [JsonPropertyName("build_id")] public string BuildId { get; set; } = "";
    [JsonPropertyName("version_dir")] public string VersionDir { get; set; } = "";
    [JsonPropertyName("manifest_sha256")] public string ManifestSha256 { get; set; } = "";
    [JsonPropertyName("profile")] public string Profile { get; set; } = "";
}

internal sealed class InstallResult
{
    internal int Code { get; init; }
    internal bool Success => Code == 0;
    internal string Message { get; init; } = "";
    internal string? Root { get; init; }
    internal string? Action { get; init; }
    internal string? LogPath { get; init; }
}

internal sealed class InstallationLayout
{
    internal string Root { get; }
    internal string InstallationId { get; }
    internal string Versions => System.IO.Path.Combine(Root, "versions");
    internal string Profile => System.IO.Path.Combine(Root, "profiles", InstallationId);
    internal string StatePath => System.IO.Path.Combine(Root, "install-state.json");
    internal string CurrentPath => System.IO.Path.Combine(Root, "current.json");
    internal string Bin => System.IO.Path.Combine(Root, "bin");
    internal string Uninstaller => System.IO.Path.Combine(Bin, "Operon_Experimental_Uninstall.exe");
    internal string Shortcut
    {
        get
        {
            var suffix = InstallationId.Length >= 8 ? InstallationId[..8] : InstallationId;
            return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft", "Windows", "Start Menu", "Programs",
                $"Operon Studio Experimental ({suffix}).lnk");
        }
    }
    internal string UninstallKey => $@"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudioExperimental-{InstallationId}";

    internal InstallationLayout(string root, string installationId)
    {
        Root = PathPolicy.Full(root);
        InstallationId = installationId;
    }

    internal string VersionDirectory(string buildId)
    {
        var target = System.IO.Path.Combine(Versions, buildId);
        if (!PathPolicy.IsWithin(Versions, target)) throw new InstallerException(3, "The version directory escapes the installation root.");
        return target;
    }

    internal string HostConfig(string versionDirectory) => System.IO.Path.Combine(versionDirectory, "host.json");
}

internal static class PathPolicy
{
    internal static string Full(string path) => System.IO.Path.GetFullPath(path);

    internal static bool IsWithin(string root, string candidate)
    {
        var prefix = Full(root).TrimEnd(System.IO.Path.DirectorySeparatorChar) + System.IO.Path.DirectorySeparatorChar;
        var full = Full(candidate);
        return full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
    }

    internal static void EnsureNoReparse(string path)
    {
        try { InstallFiles.NoLinks(path); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException)
        { throw new InstallerException(3, "The selected path contains a link or redirected directory: " + path, error); }
    }

    internal static bool IsEffectivelyEmpty(string directory)
    {
        if (!Directory.Exists(directory)) return true;
        foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
        {
            if (File.Exists(entry)) return false;
            if (!IsEffectivelyEmpty(entry)) return false;
        }
        return true;
    }

    internal static bool HasOnlyTransientEntries(string root)
    {
        foreach (var entry in Directory.EnumerateFileSystemEntries(root))
        {
            var name = System.IO.Path.GetFileName(entry);
            if (name.StartsWith(".staging-", StringComparison.Ordinal) && Directory.Exists(entry)) continue;
            if (name.Equals("profiles", StringComparison.OrdinalIgnoreCase) && IsEffectivelyEmpty(entry)) continue;
            return false;
        }
        return true;
    }

    internal static string ResolveRoot(string selected)
    {
        var full = Full(selected);
        if (File.Exists(full)) throw new InstallerException(3, "The selected path is a file, not a directory.");
        EnsureNoReparse(full);
        if (!Directory.Exists(full)) return full;
        if (File.Exists(System.IO.Path.Combine(full, "install-state.json")))
            return full;
        if (HasOnlyTransientEntries(full)) return full;

        var child = System.IO.Path.Combine(full, "Operon Studio Experimental");
        EnsureNoReparse(child);
        if (File.Exists(System.IO.Path.Combine(child, "install-state.json"))) return child;
        if (File.Exists(child)) throw new InstallerException(3, "The selected directory contains a foreign file named Operon Studio Experimental.");
        if (Directory.Exists(child) && Directory.EnumerateFileSystemEntries(child).Any() && !HasOnlyTransientEntries(child))
            throw new InstallerException(3, "The selected directory contains a nonempty foreign child: " + child);
        return child;
    }

    internal static InstalledState? ReadState(string root)
    {
        var path = System.IO.Path.Combine(root, "install-state.json");
        if (!File.Exists(path)) return null;
        try
        {
            var state = JsonSerializer.Deserialize<InstalledState>(File.ReadAllBytes(path), InstallFiles.Json);
            if (state is null || state.Schema != 1 ||
                state.Product != ProductIdentity.Product || state.Channel != ProductIdentity.Channel ||
                string.IsNullOrWhiteSpace(state.InstallationId) ||
                state.InstallationId.Any(char.IsControl) ||
                !Regex.IsMatch(state.InstallationId, @"^[0-9a-fA-F-]{36}$") ||
                state.Versions is null)
                throw new InstallerException(3, "The existing installation state is not a valid experimental installation.");
            return state;
        }
        catch (JsonException error) { throw new InstallerException(3, "The existing installation state is invalid.", error); }
    }

    internal static T ReadRequired<T>(string path, string description) where T : class
    {
        if (!File.Exists(path)) throw new InstallerException(3, description + " is missing.");
        try
        {
            return JsonSerializer.Deserialize<T>(File.ReadAllBytes(path), InstallFiles.Json)
                ?? throw new InstallerException(3, description + " is invalid.");
        }
        catch (JsonException error) { throw new InstallerException(3, description + " is invalid.", error); }
    }
}

internal static class ManifestVerifier
{
    internal static ExperimentalManifest LoadEmbedded()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Operon.Experimental.json")
            ?? throw new InstallerException(3, "This setup does not contain an experimental payload manifest.");
        try { return JsonSerializer.Deserialize<ExperimentalManifest>(stream, InstallFiles.Json)
            ?? throw new InstallerException(3, "The experimental payload manifest is empty."); }
        catch (JsonException error) { throw new InstallerException(3, "The experimental payload manifest is invalid.", error); }
    }

    internal static byte[] ReadEmbeddedBytes()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Operon.Experimental.json")
            ?? throw new InstallerException(3, "This setup does not contain an experimental payload manifest.");
        using var copy = new MemoryStream();
        stream.CopyTo(copy);
        return copy.ToArray();
    }

    internal static void Validate(ExperimentalManifest manifest)
    {
        if (manifest.Schema != 1 ||
            manifest.Product != ProductIdentity.Product ||
            manifest.Channel != ProductIdentity.Channel)
            throw new InstallerException(3, "The payload is not an Operon Studio Experimental package.");
        if (string.IsNullOrWhiteSpace(manifest.BuildId) ||
            !Regex.IsMatch(manifest.BuildId, @"^[A-Za-z0-9._-]{1,64}$"))
            throw new InstallerException(3, "The payload build identifier is invalid.");
        if (manifest.HostVersion != ProductIdentity.HostVersion ||
            manifest.ManagementRelease != ProductIdentity.ManagementRelease)
            throw new InstallerException(3,
                $"The payload versions are not supported (host {manifest.HostVersion}, management {manifest.ManagementRelease}).");
        if (string.IsNullOrWhiteSpace(manifest.SourceCommit) || manifest.SourceCommit.Any(char.IsControl))
            throw new InstallerException(3, "The payload source identity is missing.");
        if (manifest.Locks is null)
            throw new InstallerException(3, "The payload lock identity is missing.");
        foreach (var key in new[] { "cargo_lock_sha256", "frontend_lock_sha256" })
            if (!manifest.Locks.TryGetValue(key, out var value) || !Regex.IsMatch(value, "^[0-9a-f]{64}$"))
                throw new InstallerException(3, "The payload lock identity is missing: " + key);
        if (manifest.Files is null || manifest.Files.Count == 0)
            throw new InstallerException(3, "The payload file manifest is empty.");
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var file in manifest.Files)
        {
            if (string.IsNullOrWhiteSpace(file.Path))
                throw new InstallerException(3, "The payload contains an empty file path.");
            if (!seen.Add(file.Path)) throw new InstallerException(3, "The payload contains a duplicate file: " + file.Path);
            if (file.Bytes < 0 || string.IsNullOrWhiteSpace(file.Sha256) ||
                !Regex.IsMatch(file.Sha256, "^[0-9a-f]{64}$"))
                throw new InstallerException(3, "The payload file identity is invalid: " + file.Path);
            try { _ = InstallFiles.Inside(System.IO.Path.GetTempPath(), file.Path); }
            catch (Exception error) when (error is InvalidDataException or IOException)
            { throw new InstallerException(3, "The payload contains an unsafe path: " + file.Path, error); }
        }
        if (string.IsNullOrWhiteSpace(manifest.PayloadId) ||
            !Regex.IsMatch(manifest.PayloadId, "^[0-9a-f]{64}$") ||
            ComputePayloadId(manifest) != manifest.PayloadId)
            throw new InstallerException(3, "The payload manifest identity does not match its contents.");
    }

    internal static string ComputePayloadId(ExperimentalManifest manifest)
    {
        var text = new StringBuilder();
        text.Append(manifest.Product).Append('\n')
            .Append(manifest.Channel).Append('\n')
            .Append(manifest.BuildId).Append('\n')
            .Append(manifest.HostVersion).Append('\n')
            .Append(manifest.ManagementRelease).Append('\n')
            .Append(manifest.SourceCommit).Append('\n')
            .Append(manifest.SourceDirty ? "true" : "false").Append('\n');
        foreach (var pair in manifest.Locks.OrderBy(pair => pair.Key, StringComparer.Ordinal))
            text.Append(pair.Key).Append('=').Append(pair.Value).Append('\n');
        foreach (var file in manifest.Files.OrderBy(file => file.Path, StringComparer.Ordinal))
            text.Append(file.Path).Append('\t').Append(file.Bytes).Append('\t').Append(file.Sha256).Append('\n');
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text.ToString()))).ToLowerInvariant();
    }

    internal static void VerifyStage(string stage, ExperimentalManifest manifest, byte[] embeddedManifest)
    {
        var manifestPath = System.IO.Path.Combine(stage, ProductIdentity.ManifestName);
        if (!File.Exists(manifestPath) || !File.ReadAllBytes(manifestPath).SequenceEqual(embeddedManifest))
            throw new InstallerException(3, "The extracted payload manifest differs from the setup manifest.");
        var expected = new HashSet<string>(manifest.Files.Select(file => file.Path), StringComparer.OrdinalIgnoreCase);
        var actual = new HashSet<string>(EnumerateFiles(stage)
            .Select(file => System.IO.Path.GetRelativePath(stage, file).Replace('\\', '/'))
            .Where(path => path != ProductIdentity.ManifestName), StringComparer.OrdinalIgnoreCase);
        if (!expected.SetEquals(actual))
            throw new InstallerException(3, "The extracted payload file set does not match the immutable manifest.");
        foreach (var file in manifest.Files)
        {
            var path = InstallFiles.Inside(stage, file.Path);
            if (!File.Exists(path) || new FileInfo(path).Length != file.Bytes || InstallFiles.Hash(path) != file.Sha256)
                throw new InstallerException(3, "The extracted payload file is damaged: " + file.Path);
        }
    }

    internal static IEnumerable<string> EnumerateFiles(string root)
    {
        var pending = new Stack<string>();
        pending.Push(root);
        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            InstallFiles.NoLinks(directory, ancestors: false);
            foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
            {
                if ((File.GetAttributes(entry) & FileAttributes.ReparsePoint) != 0)
                    throw new InstallerException(3, "The payload contains a link or reparse point: " + entry);
                if (Directory.Exists(entry)) pending.Push(entry);
                else yield return entry;
            }
        }
    }
}

internal sealed class FileSnapshot
{
    private readonly string _path;
    private readonly bool _existed;
    private readonly byte[] _bytes;

    internal FileSnapshot(string path)
    {
        _path = path;
        _existed = File.Exists(path);
        _bytes = _existed ? File.ReadAllBytes(path) : Array.Empty<byte>();
    }

    internal void Restore()
    {
        if (_existed)
        {
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(_path)!);
            File.WriteAllBytes(_path, _bytes);
        }
        else if (File.Exists(_path))
        {
            File.Delete(_path);
        }
    }
}

internal sealed class RegistrySnapshot
{
    private readonly string _keyPath;
    private readonly bool _existed;
    private readonly List<(string Name, object? Value, RegistryValueKind Kind)> _values = new();

    internal RegistrySnapshot(string keyPath)
    {
        _keyPath = keyPath;
        using var key = Registry.CurrentUser.OpenSubKey(keyPath);
        _existed = key is not null;
        if (key is null) return;
        foreach (var name in key.GetValueNames())
            _values.Add((name, key.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames), key.GetValueKind(name)));
    }

    internal void Restore()
    {
        if (!_existed)
        {
            Registry.CurrentUser.DeleteSubKeyTree(_keyPath, throwOnMissingSubKey: false);
            return;
        }
        using var key = Registry.CurrentUser.CreateSubKey(_keyPath, writable: true);
        foreach (var name in key.GetValueNames())
            if (_values.All(value => value.Name != name)) key.DeleteValue(name, throwOnMissingValue: false);
        foreach (var (name, value, kind) in _values)
            key.SetValue(name, value!, kind);
    }
}

internal static class ShortcutRegistration
{
    internal static void Create(string shortcutPath, string target, string arguments, string workingDirectory)
    {
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(shortcutPath)!);
        var shellType = Type.GetTypeFromProgID("WScript.Shell")
            ?? throw new InstallerException(5, "The Windows shortcut service is unavailable.");
        dynamic shell = Activator.CreateInstance(shellType)
            ?? throw new InstallerException(5, "The Windows shortcut service is unavailable.");
        dynamic shortcut = shell.CreateShortcut(shortcutPath);
        shortcut.TargetPath = target;
        shortcut.Arguments = arguments;
        shortcut.WorkingDirectory = workingDirectory;
        shortcut.Description = "Operon Studio Experimental";
        shortcut.Save();
    }

    internal static void Delete(string path)
    {
        if (File.Exists(path)) File.Delete(path);
    }
}

internal static class UninstallRegistration
{
    internal static void Write(InstallationLayout layout, ExperimentalManifest manifest, string hostExe, string manifestHash)
    {
        using var key = Registry.CurrentUser.CreateSubKey(layout.UninstallKey, writable: true);
        var suffix = layout.InstallationId.Length >= 8 ? layout.InstallationId[..8] : layout.InstallationId;
        key.SetValue("DisplayName", $"Operon Studio Experimental ({suffix})");
        key.SetValue("DisplayVersion", manifest.HostVersion);
        key.SetValue("Publisher", "Operon experimental build");
        key.SetValue("InstallLocation", layout.Root);
        key.SetValue("DisplayIcon", hostExe);
        key.SetValue("UninstallString", $"\"{layout.Uninstaller}\" --uninstall --install-dir \"{layout.Root}\"");
        key.SetValue("QuietUninstallString", $"\"{layout.Uninstaller}\" --silent --uninstall --install-dir \"{layout.Root}\"");
        key.SetValue("NoModify", 1, RegistryValueKind.DWord);
        key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        var bytes = manifest.Files.Sum(file => file.Bytes) / 1024;
        key.SetValue("EstimatedSize", bytes > int.MaxValue ? int.MaxValue : (int)bytes, RegistryValueKind.DWord);
        key.SetValue("OperonManifestSha256", manifestHash);
    }

    internal static void Delete(string keyPath)
    {
        Registry.CurrentUser.DeleteSubKeyTree(keyPath, throwOnMissingSubKey: false);
    }
}

internal sealed class InstallLock : IDisposable
{
    private readonly FileStream _stream;

    private InstallLock(FileStream stream) => _stream = stream;

    internal static InstallLock Acquire(string root)
    {
        var canonical = CanonicalRoot(root).ToLowerInvariant();
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(canonical))).ToLowerInvariant();
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrWhiteSpace(local))
            throw new InstallerException(4, "The per-user installation lock directory is unavailable.");
        var directory = System.IO.Path.Combine(local, "Operon Studio Experimental", "install-locks");
        try
        {
            Directory.CreateDirectory(directory);
            var path = System.IO.Path.Combine(directory, hash + ".lock");
            // FileShare.None is the OS-held exclusion. The empty lock file is
            // only a rendezvous point: no boolean or stale state is stored.
            return new InstallLock(new FileStream(path, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None));
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            throw new InstallerException(4, "Another setup is already operating on this installation root. Wait for it to finish and retry.", error);
        }
    }

    private static string CanonicalRoot(string root)
    {
        var full = PathPolicy.Full(root);
        if (full.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase)) full = @"\\" + full[8..];
        else if (full.StartsWith(@"\\?\", StringComparison.Ordinal)) full = full[4..];
        full = System.IO.Path.GetFullPath(full);
        var trimmed = full.TrimEnd(System.IO.Path.DirectorySeparatorChar, System.IO.Path.AltDirectorySeparatorChar);
        return trimmed.Length == 0 ? full : trimmed;
    }

    public void Dispose() => _stream.Dispose();
}

internal sealed class ExecutableRemovalBarrier : IDisposable
{
    private readonly List<FileStream> _handles = new();

    internal void AddExecutable(string path) =>
        _handles.Add(new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Delete));

    internal string Hash(string path)
    {
        var handle = _handles.FirstOrDefault(h => string.Equals(h.Name, path, StringComparison.OrdinalIgnoreCase));
        if (handle is null) return InstallFiles.Hash(path);
        handle.Position = 0;
        return Convert.ToHexString(SHA256.HashData(handle)).ToLowerInvariant();
    }

    internal static ExecutableRemovalBarrier Acquire(InstallationLayout layout, InstalledState state)
    {
        var guard = new ExecutableRemovalBarrier();
        try
        {
            foreach (var version in state.Versions)
            {
                var directory = layout.VersionDirectory(version.BuildId);
                if (!Directory.Exists(directory)) continue;
                PathPolicy.EnsureNoReparse(directory);
                var manifestPath = InstallFiles.Inside(directory, ProductIdentity.ManifestName);
                if (!File.Exists(manifestPath) || InstallFiles.Hash(manifestPath) != version.ManifestSha256)
                    throw new InstallerException(6, "Cannot establish a safe executable inventory for uninstall. The installed manifest is missing or modified.");
                var manifest = JsonSerializer.Deserialize<ExperimentalManifest>(File.ReadAllBytes(manifestPath), InstallFiles.Json)
                    ?? throw new InstallerException(6, "Invalid installed manifest.");
                ManifestVerifier.Validate(manifest);
                foreach (var file in manifest.Files.Where(f => f.Path.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)))
                {
                    var path = InstallFiles.Inside(directory, file.Path);
                    if (File.Exists(path))
                        // Allow our deletion, deny new image readers/writers.
                        guard.AddExecutable(path);
                }
            }
            return guard;
        }
        catch (Exception error)
        {
            guard.Dispose();
            if (error is InstallerException) throw;
            throw new InstallerException(4, "An installed executable is still in use. Nothing was removed; finish its task and retry.", error);
        }
    }

    public void Dispose()
    {
        foreach (var handle in _handles) handle.Dispose();
        _handles.Clear();
    }
}

internal sealed class ExperimentalInstaller
{
    private readonly InstallerLog _log;
    private readonly Action<string> _progress;

    internal ExperimentalInstaller(InstallerLog log, Action<string> progress)
    {
        _log = log;
        _progress = progress;
    }

    internal InstallResult Install(string selectedRoot, CancellationToken cancellation)
    {
        string? stage = null;
        string? promotedPath = null;
        string? replacedBackup = null;
        InstallLock? installLock = null;
        var freshInstall = false;
        InstallationLayout? layout = null;
        var manifest = ManifestVerifier.LoadEmbedded();
        ManifestVerifier.Validate(manifest);
        var embedded = ManifestVerifier.ReadEmbeddedBytes();
        try
        {
            cancellation.ThrowIfCancellationRequested();
            var root = PathPolicy.ResolveRoot(selectedRoot);
            installLock = InstallLock.Acquire(root);
            layout = new InstallationLayout(root, "");
            _log.Write($"install root selected: {root}");
            Directory.CreateDirectory(root);
            PathPolicy.EnsureNoReparse(root);

            var spec = ReadPayloadSpec();
            if (spec.Version != ProductIdentity.HostVersion)
                throw new InstallerException(3, "The setup payload version does not match the experimental host version.");
            if (manifest.Files.Count + 1 != spec.Files)
                throw new InstallerException(3, "The setup payload file count does not match the manifest.");

            stage = System.IO.Path.Combine(root, ".staging-" + manifest.BuildId + "-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(stage);
            _progress("Verifying setup payload...");
            var cache = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "OperonExperimentalSetup");
            var payload = InstallFiles.MaterializePayload(spec, cache, null,
                new Progress<InstallProgress>(value => _progress(value.Message)), cancellation).GetAwaiter().GetResult();
            _progress("Installing Operon Studio Experimental...");
            InstallFiles.Extract(payload, stage, spec,
                new Progress<InstallProgress>(value => _progress(value.Message)), cancellation).GetAwaiter().GetResult();
            ManifestVerifier.VerifyStage(stage, manifest, embedded);
            var extractedManifestHash = InstallFiles.Hash(System.IO.Path.Combine(stage, ProductIdentity.ManifestName));

            var state = PathPolicy.ReadState(root);
            freshInstall = state is null;
            var installationId = state?.InstallationId ?? Guid.NewGuid().ToString("D");
            layout = new InstallationLayout(root, installationId);
            ValidateProfile(layout);
            var pointer = state is null ? null : PathPolicy.ReadRequired<CurrentPointer>(layout.CurrentPath, "Current version pointer");
            if (pointer is not null && (pointer.Product != ProductIdentity.Product || pointer.Channel != ProductIdentity.Channel))
                throw new InstallerException(3, "The existing current pointer is not an experimental installation.");
            if (pointer is not null && (pointer.Profile != layout.Profile ||
                pointer.VersionDir != "versions/" + pointer.BuildId))
                throw new InstallerException(3, "The existing current pointer has an invalid profile or version path.");
            var currentVersion = pointer is null ? null : layout.VersionDirectory(pointer.BuildId);
            if (currentVersion is not null) PathPolicy.EnsureNoReparse(currentVersion);

            using var lease = MaintenanceLease.Acquire(installationId);
            cancellation.ThrowIfCancellationRequested();
            _progress("Waiting for Operon to exit...");
            if (currentVersion is not null)
            {
                var running = MaintenanceClient.FindOwnedHost(layout.Profile, currentVersion, installationId);
                if (running is not null)
                {
                    using (running)
                    {
                        _log.Write($"requesting graceful exit of owned host pid={running.Pid}");
                        try { MaintenanceClient.RequestQuit(running, installationId, cancellation); }
                        catch (OperationCanceledException) { throw new InstallerException(8, "Cancelled while waiting for Operon to exit. The current installation was not changed."); }
                        catch (MaintenanceException error) { throw new InstallerException(error.Code, error.Message, error); }
                    }
                }
            }
            else
            {
                using var unexpected = MaintenanceClient.FindOwnedHost(layout.Profile, layout.Versions, installationId);
                if (unexpected is not null)
                    throw new InstallerException(4, "A host is running without a current version pointer. Exit Operon manually and retry.");
            }

            cancellation.ThrowIfCancellationRequested();
            _progress("Promoting the verified version...");
            Directory.CreateDirectory(layout.Versions);
            PathPolicy.EnsureNoReparse(layout.Versions);
            var versionDirectory = layout.VersionDirectory(manifest.BuildId);
            if (Directory.Exists(versionDirectory))
            {
                if (pointer?.BuildId != manifest.BuildId)
                    throw new InstallerException(5, "The target version directory already exists and is not current. No files were changed.");
                var existingManifest = System.IO.Path.Combine(versionDirectory, ProductIdentity.ManifestName);
                var manifestMatches = File.Exists(existingManifest) &&
                    InstallFiles.Hash(existingManifest) == extractedManifestHash;
                if (!manifestMatches)
                    throw new InstallerException(5, "This build identifier already names a different payload. Use a new experimental build identifier; the current version was preserved.");
                if (manifestMatches && VerifyInstalledVersion(versionDirectory, manifest))
                {
                    // The current version already contains the exact immutable
                    // payload; only generated host.json/runtime cache may differ.
                    DeleteStage(stage, manifest);
                    stage = null;
                }
                else
                {
                    _log.Write("the current version directory is damaged; reinstalling the verified stage");
                    replacedBackup = ReplaceVersionDirectory(layout, stage, manifest);
                    stage = null;
                    promotedPath = versionDirectory;
                }
            }
            else
            {
                Directory.Move(stage, versionDirectory);
                stage = null;
                promotedPath = versionDirectory;
            }

            var hostConfig = layout.HostConfig(versionDirectory);
            var shortcutSnapshot = new FileSnapshot(layout.Shortcut);
            var pointerSnapshot = new FileSnapshot(layout.CurrentPath);
            var stateSnapshot = new FileSnapshot(layout.StatePath);
            var configSnapshot = new FileSnapshot(hostConfig);
            var uninstallerSnapshot = new FileSnapshot(layout.Uninstaller);
            var registrySnapshot = new RegistrySnapshot(layout.UninstallKey);
            try
            {
                cancellation.ThrowIfCancellationRequested();
                Directory.CreateDirectory(layout.Profile);
                InstallFiles.AtomicJson(hostConfig, new
                {
                    installation_id = installationId,
                    backend_root = ".",
                    python = "runtime/python/python.exe",
                    frontend = "frontend",
                    profile = layout.Profile
                });
                InstallUninstaller(layout);
                var hostExe = System.IO.Path.Combine(versionDirectory, ProductIdentity.HostExe);
                if (!File.Exists(hostExe)) throw new InstallerException(5, "The promoted payload is missing its host executable.");
                ShortcutRegistration.Create(layout.Shortcut, hostExe,
                    $"--config \"{hostConfig}\"", versionDirectory);
                UninstallRegistration.Write(layout, manifest, hostExe, extractedManifestHash);

                var nextState = state ?? new InstalledState { InstallationId = installationId };
                nextState.Versions.RemoveAll(value => value.BuildId == manifest.BuildId);
                nextState.Versions.Add(new InstalledVersion
                {
                    BuildId = manifest.BuildId,
                    ManifestSha256 = extractedManifestHash,
                    PayloadId = manifest.PayloadId,
                    InstalledUtc = DateTime.UtcNow.ToString("O")
                });
                InstallFiles.AtomicJson(layout.StatePath, nextState);
                InstallFiles.AtomicJson(layout.CurrentPath, new CurrentPointer
                {
                    BuildId = manifest.BuildId,
                    VersionDir = "versions/" + manifest.BuildId,
                    ManifestSha256 = extractedManifestHash,
                    Profile = layout.Profile
                });
            }
            catch
            {
                registrySnapshot.Restore();
                uninstallerSnapshot.Restore();
                configSnapshot.Restore();
                stateSnapshot.Restore();
                pointerSnapshot.Restore();
                shortcutSnapshot.Restore();
                throw;
            }

            if (replacedBackup is not null)
            {
                try { RemoveReplacedVersion(replacedBackup, manifest); }
                catch (Exception error) { _log.Write("failed to clean the replaced version copy: " + error.Message); }
                replacedBackup = null;
            }

            _log.Write($"installed build={manifest.BuildId} payload={manifest.PayloadId} profile={layout.Profile}");
            return new InstallResult
            {
                Code = 0,
                Message = "Operon Studio Experimental was installed. Launch it from the Start Menu.",
                Root = layout.Root,
                Action = "install",
                LogPath = _log.Path
            };
        }
        catch (OperationCanceledException)
        {
            CleanupFailedInstallation(stage, promotedPath, freshInstall, layout, manifest, replacedBackup);
            return Failure(8, "Installation cancelled. The existing installation was not changed.", layout);
        }
        catch (MaintenanceException error)
        {
            CleanupFailedInstallation(stage, promotedPath, freshInstall, layout, manifest, replacedBackup);
            _log.Write($"install maintenance failed code={error.Code}: {error.Message}");
            return Failure(error.Code, error.Message, layout);
        }
        catch (InstallerException error)
        {
            CleanupFailedInstallation(stage, promotedPath, freshInstall, layout, manifest, replacedBackup);
            _log.Write($"install failed code={error.Code}: {error.Message}");
            return Failure(error.Code, error.Message, layout);
        }
        catch (Exception error)
        {
            CleanupFailedInstallation(stage, promotedPath, freshInstall, layout, manifest, replacedBackup);
            _log.Write($"install failed: {error}");
            return Failure(5, "Installation failed: " + error.Message, layout);
        }
        finally
        {
            try { installLock?.Dispose(); } catch { }
        }
    }

    private void CleanupFailedInstallation(string? stage, string? promotedPath, bool freshInstall,
        InstallationLayout? layout, ExperimentalManifest manifest, string? replacedBackup)
    {
        try
        {
            if (stage is not null) DeleteStage(stage, manifest);
            if (promotedPath is not null) DeleteStage(promotedPath, manifest);
            if (promotedPath is not null)
            {
                var hostConfig = System.IO.Path.Combine(promotedPath, "host.json");
                if (File.Exists(hostConfig)) File.Delete(hostConfig);
            }
            if (replacedBackup is not null && layout is not null)
            {
                var versionDirectory = layout.VersionDirectory(manifest.BuildId);
                if (!Directory.Exists(versionDirectory) && Directory.Exists(replacedBackup))
                    Directory.Move(replacedBackup, versionDirectory);
                else if (Directory.Exists(replacedBackup))
                    _log.Write("the replaced version copy was retained because the promoted directory could not be removed: " + replacedBackup);
            }
            if (freshInstall && layout is not null)
            {
                if (File.Exists(layout.Uninstaller)) File.Delete(layout.Uninstaller);
                if (Directory.Exists(layout.Bin) && !Directory.EnumerateFileSystemEntries(layout.Bin).Any())
                    Directory.Delete(layout.Bin);
                var profile = layout.Profile;
                if (Directory.Exists(profile) && !Directory.EnumerateFileSystemEntries(profile).Any())
                    Directory.Delete(profile);
                var profiles = System.IO.Path.GetDirectoryName(profile);
                if (profiles is not null && Directory.Exists(profiles) &&
                    !Directory.EnumerateFileSystemEntries(profiles).Any()) Directory.Delete(profiles);
                var versions = layout.Versions;
                if (Directory.Exists(versions) && !Directory.EnumerateFileSystemEntries(versions).Any())
                    Directory.Delete(versions);
                if (Directory.Exists(layout.Root) && !Directory.EnumerateFileSystemEntries(layout.Root).Any())
                    Directory.Delete(layout.Root);
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            _log.Write("failed to remove one or more setup-owned staging files: " + error.Message);
        }
    }

    internal InstallResult Uninstall(string selectedRoot, CancellationToken cancellation)
    {
        InstallationLayout? layout = null;
        InstallLock? installLock = null;
        var removalsStarted = false;
        try
        {
            var root = PathPolicy.ResolveRoot(selectedRoot);
            installLock = InstallLock.Acquire(root);
            var state = PathPolicy.ReadState(root)
                ?? throw new InstallerException(6, "No Operon Studio Experimental installation exists at the selected directory.");
            layout = new InstallationLayout(root, state.InstallationId);

            // Validate ownership and reject reparse-point version roots before
            // reading any installed manifest or deleting anything.
            ValidateProfile(layout);
            PathPolicy.EnsureNoReparse(layout.Versions);
            foreach (var version in state.Versions)
                PathPolicy.EnsureNoReparse(layout.VersionDirectory(version.BuildId));

            using var lease = MaintenanceLease.Acquire(layout.InstallationId);
            var pointer = PathPolicy.ReadRequired<CurrentPointer>(layout.CurrentPath, "Current version pointer");
            if (pointer.Product != ProductIdentity.Product || pointer.Channel != ProductIdentity.Channel ||
                pointer.Profile != layout.Profile || pointer.VersionDir != "versions/" + pointer.BuildId)
                throw new InstallerException(6, "The current pointer is not valid for this experimental installation.");
            var currentVersion = layout.VersionDirectory(pointer.BuildId);
            PathPolicy.EnsureNoReparse(currentVersion);

            _progress("Waiting for Operon to exit...");
            var running = MaintenanceClient.FindOwnedHost(layout.Profile, currentVersion, layout.InstallationId);
            if (running is not null)
            {
                using (running)
                {
                    try { MaintenanceClient.RequestQuit(running, layout.InstallationId, cancellation); }
                    catch (OperationCanceledException) { throw new InstallerException(8, "Uninstall cancelled while waiting for Operon to exit. Nothing was removed."); }
                    catch (MaintenanceException error) { throw new InstallerException(error.Code, error.Message, error); }
                }
            }

            cancellation.ThrowIfCancellationRequested();
            // Prevent a bundled Python/host relaunch between process inventory
            // and removal. The backend itself and its scheduler stay unchanged.
            using var removalBarrier = ExecutableRemovalBarrier.Acquire(layout, state);
            MaintenanceClient.EnsureNoProcessImagesUnder(layout.Versions);
            _progress("Removing verified installation files...");
            var notes = new List<string>();
            foreach (var version in state.Versions)
            {
                var directory = layout.VersionDirectory(version.BuildId);
                if (!Directory.Exists(directory)) continue;
                var manifestPath = System.IO.Path.Combine(directory, ProductIdentity.ManifestName);
                if (!File.Exists(manifestPath) || InstallFiles.Hash(manifestPath) != version.ManifestSha256)
                {
                    notes.Add("Preserved a version whose immutable manifest was missing or modified.");
                    continue;
                }
                ExperimentalManifest manifest;
                try
                {
                    manifest = JsonSerializer.Deserialize<ExperimentalManifest>(File.ReadAllBytes(manifestPath), InstallFiles.Json)
                        ?? throw new JsonException("empty");
                }
                catch (JsonException)
                {
                    notes.Add("Preserved a version whose manifest could not be read.");
                    continue;
                }
                try { ManifestVerifier.Validate(manifest); }
                catch (InstallerException)
                {
                    notes.Add("Preserved a version whose manifest failed ownership validation.");
                    continue;
                }
                foreach (var file in manifest.Files.OrderByDescending(file => file.Path.Length))
                {
                    cancellation.ThrowIfCancellationRequested();
                    string target;
                    try { target = InstallFiles.Inside(directory, file.Path); }
                    catch (InvalidDataException) { notes.Add("Preserved an unsafe manifest path: " + file.Path); continue; }
                    if (!File.Exists(target)) continue;
                    if (removalBarrier.Hash(target) != file.Sha256)
                    {
                        notes.Add("Preserved a modified or unknown file: " + file.Path);
                        continue;
                    }
                    File.SetAttributes(target, FileAttributes.Normal);
                    File.Delete(target);
                    removalsStarted = true;
                }
                if (InstallFiles.Hash(manifestPath) == version.ManifestSha256)
                {
                    File.SetAttributes(manifestPath, FileAttributes.Normal);
                    File.Delete(manifestPath);
                    removalsStarted = true;
                }
                RemoveEmptyDirectories(directory);
            }

            ShortcutRegistration.Delete(layout.Shortcut);
            UninstallRegistration.Delete(layout.UninstallKey);
            if (File.Exists(layout.CurrentPath)) { File.Delete(layout.CurrentPath); removalsStarted = true; }
            if (File.Exists(layout.StatePath)) { File.Delete(layout.StatePath); removalsStarted = true; }
            if (File.Exists(layout.Uninstaller) &&
                !string.Equals(System.IO.Path.GetFullPath(layout.Uninstaller),
                    System.IO.Path.GetFullPath(Environment.ProcessPath ?? ""), StringComparison.OrdinalIgnoreCase))
            {
                File.Delete(layout.Uninstaller);
                removalsStarted = true;
            }
            else if (File.Exists(layout.Uninstaller))
                notes.Add("The installed uninstaller stub is still running and was retained.");
            if (Directory.Exists(layout.Bin) && !Directory.EnumerateFileSystemEntries(layout.Bin).Any()) Directory.Delete(layout.Bin);
            foreach (var empty in new[] { "versions", "profiles" })
            {
                var path = System.IO.Path.Combine(layout.Root, empty);
                if (Directory.Exists(path) && !Directory.EnumerateFileSystemEntries(path).Any()) Directory.Delete(path);
            }
            removalBarrier.Dispose();
            RemoveEmptyDirectories(layout.Versions);
            notes.Add("The profile was retained: " + layout.Profile);
            var message = "Operon Studio Experimental was uninstalled. " + string.Join(" ", notes);
            _log.Write(message);
            return new InstallResult { Code = 0, Message = message, Root = layout.Root, Action = "uninstall", LogPath = _log.Path };
        }
        catch (OperationCanceledException)
        {
            var message = removalsStarted
                ? "Uninstall cancelled after removals began. The installation is partially removed and may need another uninstall to finish."
                : "Uninstall cancelled. Nothing was removed.";
            return Failure(8, message, layout);
        }
        catch (MaintenanceException error)
        {
            _log.Write($"uninstall maintenance failed code={error.Code}: {error.Message}");
            return Failure(error.Code, error.Message, layout);
        }
        catch (InstallerException error)
        {
            _log.Write($"uninstall failed code={error.Code}: {error.Message}");
            return Failure(error.Code, error.Message, layout);
        }
        catch (Exception error)
        {
            _log.Write($"uninstall failed: {error}");
            return Failure(6, "Uninstall failed: " + error.Message, layout);
        }
        finally
        {
            try { installLock?.Dispose(); } catch { }
        }
    }

    private InstallResult Failure(int code, string message, InstallationLayout? layout) =>
        new() { Code = code, Message = message, Root = layout?.Root, LogPath = _log.Path };

    private static PayloadSpec ReadPayloadSpec()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Operon.Payload.json")
            ?? throw new InstallerException(3, "This setup does not contain an embedded payload specification.");
        var spec = JsonSerializer.Deserialize<PayloadSpec>(stream, InstallFiles.Json)
            ?? throw new InstallerException(3, "The embedded payload specification is invalid.");
        if (spec.Bytes <= 0 || spec.UnpackedBytes <= 0 || spec.Files <= 0 ||
            string.IsNullOrWhiteSpace(spec.Sha256) || !Regex.IsMatch(spec.Sha256, "^[0-9a-f]{64}$"))
            throw new InstallerException(3, "The embedded payload specification is invalid.");
        return spec;
    }

    private static void ValidateProfile(InstallationLayout layout)
    {
        var profile = layout.Profile;
        if (PathPolicy.IsWithin(layout.Versions, profile))
            throw new InstallerException(3, "The profile cannot be inside the version directory.");
        if (!Directory.Exists(profile)) return;
        PathPolicy.EnsureNoReparse(profile);
        var marker = System.IO.Path.Combine(profile, ProductIdentity.ProfileMarker);
        if (File.Exists(marker))
        {
            try
            {
                using var document = JsonDocument.Parse(File.ReadAllBytes(marker));
                var id = document.RootElement.GetProperty("installation_id").GetString();
                if (document.RootElement.GetProperty("schema_version").GetInt32() != 1 || id != layout.InstallationId)
                    throw new InstallerException(3, "The profile marker belongs to another installation.");
            }
            catch (Exception error) when (error is JsonException or KeyNotFoundException or InvalidOperationException)
            { throw new InstallerException(3, "The profile marker is invalid.", error); }
            return;
        }
        if (Directory.EnumerateFileSystemEntries(profile).Any())
            throw new InstallerException(3, "The profile is nonempty and is not owned by this installation: " + profile);
    }

    private static void InstallUninstaller(InstallationLayout layout)
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Operon.UninstallerStub.exe")
            ?? throw new InstallerException(5, "This setup does not contain the small experimental uninstaller.");
        Directory.CreateDirectory(layout.Bin);
        var temporary = layout.Uninstaller + ".tmp-" + Guid.NewGuid().ToString("N");
        try
        {
            using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                stream.CopyTo(output);
            File.Move(temporary, layout.Uninstaller, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static bool VerifyInstalledVersion(string directory, ExperimentalManifest manifest)
    {
        try
        {
            if (Directory.Exists(System.IO.Path.Combine(directory, "host.json"))) return false;
            var expected = new HashSet<string>(manifest.Files.Select(file => file.Path), StringComparer.OrdinalIgnoreCase);
            foreach (var file in manifest.Files)
            {
                var path = InstallFiles.Inside(directory, file.Path);
                if (!File.Exists(path) || new FileInfo(path).Length != file.Bytes ||
                    InstallFiles.Hash(path) != file.Sha256)
                    return false;
            }
            foreach (var path in ManifestVerifier.EnumerateFiles(directory))
            {
                var relative = System.IO.Path.GetRelativePath(directory, path).Replace('\\', '/');
                if (expected.Contains(relative) ||
                    string.Equals(relative, ProductIdentity.ManifestName, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(relative, "host.json", StringComparison.OrdinalIgnoreCase) ||
                    IsRuntimeCache(relative))
                    continue;
                return false;
            }
            return true;
        }
        catch (Exception error) when (error is InstallerException or IOException or UnauthorizedAccessException or ArgumentException)
        {
            return false;
        }
    }

    private static bool IsRuntimeCache(string relative)
    {
        foreach (var segment in relative.Split('/'))
            if (string.Equals(segment, "__pycache__", StringComparison.OrdinalIgnoreCase))
                return true;
        return relative.EndsWith(".pyc", StringComparison.OrdinalIgnoreCase) ||
               relative.EndsWith(".pyo", StringComparison.OrdinalIgnoreCase);
    }

    private static string ReplaceVersionDirectory(InstallationLayout layout, string stage, ExperimentalManifest manifest)
    {
        var versionDirectory = layout.VersionDirectory(manifest.BuildId);
        var backup = System.IO.Path.Combine(layout.Root,
            ".staging-replaced-" + manifest.BuildId + "-" + Guid.NewGuid().ToString("N"));
        Directory.Move(versionDirectory, backup);
        try
        {
            Directory.Move(stage, versionDirectory);
            return backup;
        }
        catch
        {
            if (!Directory.Exists(versionDirectory) && Directory.Exists(backup))
                Directory.Move(backup, versionDirectory);
            throw;
        }
    }

    private void RemoveReplacedVersion(string directory, ExperimentalManifest manifest)
    {
        if (!Directory.Exists(directory)) return;
        // This directory was the current same-build version. Remove only the
        // manifest-owned files and generated host config; unknown files remain.
        foreach (var file in manifest.Files.OrderByDescending(file => file.Path.Length))
        {
            try
            {
                var target = InstallFiles.Inside(directory, file.Path);
                if (!File.Exists(target)) continue;
                File.SetAttributes(target, FileAttributes.Normal);
                File.Delete(target);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException) { }
        }
        foreach (var name in new[] { ProductIdentity.ManifestName, "host.json" })
        {
            try
            {
                var path = System.IO.Path.Combine(directory, name);
                if (!File.Exists(path)) continue;
                File.SetAttributes(path, FileAttributes.Normal);
                File.Delete(path);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
        }
        RemoveEmptyDirectories(directory);
        if (Directory.Exists(directory))
            _log.Write("retained unknown or generated runtime files from the replaced version: " + directory);
    }

    private static void DeleteStage(string stage, ExperimentalManifest manifest)
    {
        if (!Directory.Exists(stage)) return;
        foreach (var file in manifest.Files)
        {
            try
            {
                var target = InstallFiles.Inside(stage, file.Path);
                if (File.Exists(target)) File.Delete(target);
            }
            catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException) { }
        }
        var manifestPath = System.IO.Path.Combine(stage, ProductIdentity.ManifestName);
        if (File.Exists(manifestPath)) File.Delete(manifestPath);
        RemoveEmptyDirectories(stage);
        if (Directory.Exists(stage) && !Directory.EnumerateFileSystemEntries(stage).Any()) Directory.Delete(stage);
    }

    internal static void RemoveEmptyDirectories(string root)
    {
        if (!Directory.Exists(root)) return;
        var pending = new Stack<string>();
        pending.Push(root);
        var directories = new List<string>();
        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            try
            {
                if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) continue;
                directories.Add(directory);
                foreach (var child in Directory.EnumerateDirectories(directory)) pending.Push(child);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
        }
        foreach (var directory in directories.OrderByDescending(value => value.Length))
        {
            try
            {
                if (!Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
        }
    }
}

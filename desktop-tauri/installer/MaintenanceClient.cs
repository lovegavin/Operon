using System.Diagnostics;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Operon.Setup.Experimental;

internal sealed class MaintenanceException : Exception
{
    internal int Code { get; }
    internal MaintenanceException(int code, string message) : base(message) => Code = code;
}

internal sealed class MaintenanceLease : IDisposable
{
    private const uint WaitObject0 = 0;
    private const uint WaitAbandoned = 0x80;
    private const uint WaitTimeout = 0x102;
    private IntPtr _mutex;
    private IntPtr _event;

    private MaintenanceLease(IntPtr mutex, IntPtr @event)
    {
        _mutex = mutex;
        _event = @event;
    }

    internal static MaintenanceLease Acquire(string installationId)
    {
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(installationId))).ToLowerInvariant();
        var mutexName = $"Local\\OperonExperimentalMaintenance-{hash}";
        var eventName = mutexName + "-active";
        // Create the mutex unowned and acquire it exactly once with the wait
        // below. Install/uninstall stay synchronous on one worker thread, so
        // ReleaseMutex is always called by the acquiring thread in Dispose.
        var mutex = CreateMutexW(IntPtr.Zero, false, mutexName);
        if (mutex == IntPtr.Zero) throw new MaintenanceException(4, "Cannot create the installation maintenance mutex.");
        var wait = WaitForSingleObject(mutex, 0);
        if (wait != WaitObject0 && wait != WaitAbandoned)
        {
            CloseHandle(mutex);
            throw new MaintenanceException(4, "Another setup or host startup is using this installation. Try again.");
        }
        var @event = CreateEventW(IntPtr.Zero, true, false, eventName);
        if (@event == IntPtr.Zero)
        {
            ReleaseMutex(mutex);
            CloseHandle(mutex);
            throw new MaintenanceException(4, "Cannot create the installation maintenance event.");
        }
        if (WaitForSingleObject(@event, 0) == WaitObject0)
        {
            CloseHandle(@event);
            ReleaseMutex(mutex);
            CloseHandle(mutex);
            throw new MaintenanceException(4, "Maintenance is already active for this installation.");
        }
        if (!SetEvent(@event))
        {
            CloseHandle(@event);
            ReleaseMutex(mutex);
            CloseHandle(mutex);
            throw new MaintenanceException(4, "Cannot activate the installation maintenance event.");
        }
        return new MaintenanceLease(mutex, @event);
    }

    public void Dispose()
    {
        // ReleaseMutex is thread-affine. Installs and uninstalls are synchronous
        // on the worker thread that called Acquire, so this always runs there.
        if (_event != IntPtr.Zero)
        {
            ResetEvent(_event);
            CloseHandle(_event);
            _event = IntPtr.Zero;
        }
        if (_mutex != IntPtr.Zero)
        {
            ReleaseMutex(_mutex);
            CloseHandle(_mutex);
            _mutex = IntPtr.Zero;
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateMutexW(IntPtr attributes, bool initialOwner, string name);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateEventW(IntPtr attributes, bool manualReset, bool initialState, string name);
    [DllImport("kernel32.dll")]
    private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll")]
    private static extern bool SetEvent(IntPtr handle);
    [DllImport("kernel32.dll")]
    private static extern bool ResetEvent(IntPtr handle);
    [DllImport("kernel32.dll")]
    private static extern bool ReleaseMutex(IntPtr mutex);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);
}

internal sealed class OwnedHost : IDisposable
{
    private IntPtr _handle;
    internal Process Process { get; }
    internal MaintenanceReceipt Receipt { get; }
    internal IntPtr Handle => _handle;
    internal int Pid => Process.Id;
    internal string ImagePath { get; }
    internal string CreatedFiletime { get; }

    internal OwnedHost(Process process, IntPtr handle, MaintenanceReceipt receipt, string imagePath, string createdFiletime)
    {
        Process = process;
        _handle = handle;
        Receipt = receipt;
        ImagePath = imagePath;
        CreatedFiletime = createdFiletime;
    }

    public void Dispose()
    {
        if (_handle != IntPtr.Zero)
        {
            MaintenanceClient.CloseProcessHandle(_handle);
            _handle = IntPtr.Zero;
        }
        Process.Dispose();
    }
}

internal sealed class MaintenanceReceipt
{
    [JsonPropertyName("schema")] public int Schema { get; set; }
    [JsonPropertyName("installation_id")] public string InstallationId { get; set; } = "";
    [JsonPropertyName("pid")] public uint Pid { get; set; }
    [JsonPropertyName("created_filetime")] public string CreatedFiletime { get; set; } = "";
    [JsonPropertyName("exe")] public string Exe { get; set; } = "";
    [JsonPropertyName("pipe_name")] public string PipeName { get; set; } = "";
    [JsonPropertyName("token")] public string Token { get; set; } = "";
}

internal sealed class MaintenanceClient
{
    private const string ReceiptName = ".operon-maintenance-host.json";
    private const string InstanceLockName = ".operon-instance.lock";
    private const string PipePrefix = @"\\.\pipe\";
    private const int FrameLimit = 4096;
    private const uint WaitObject0 = 0;
    private const uint WaitTimeout = 0x102;
    private const uint ProcessQueryLimitedInformation = 0x1000;
    private const uint Synchronize = 0x00100000;
    private static readonly TimeSpan FrameTimeout = TimeSpan.FromSeconds(3);
    private static readonly TimeSpan ExitTimeout = TimeSpan.FromSeconds(45);

    internal static string ReceiptPath(string profile) => Path.Combine(profile, ReceiptName);

    /// <summary>
    /// Returns a live owned host, or null when no live host exists. A live
    /// instance lock without a trustworthy receipt is refused, never ignored.
    /// </summary>
    internal static OwnedHost? FindOwnedHost(string profile, string currentVersionDirectory, string installationId)
    {
        var receiptPath = ReceiptPath(profile);
        if (!File.Exists(receiptPath))
        {
            if (InstanceLockHeld(profile))
                throw new MaintenanceException(4, "The application instance lock is live but the maintenance receipt is missing. Exit Operon manually and retry.");
            return null;
        }

        MaintenanceReceipt? receipt;
        try
        {
            if (new FileInfo(receiptPath).Length > 16 * 1024)
                throw new InvalidDataException("Maintenance receipt is too large.");
            receipt = JsonSerializer.Deserialize<MaintenanceReceipt>(File.ReadAllBytes(receiptPath));
        }
        catch (Exception error) when (error is JsonException or IOException or InvalidDataException)
        {
            receipt = null;
        }

        if (receipt is null || !ValidReceipt(receipt, installationId))
        {
            if (InstanceLockHeld(profile))
                throw new MaintenanceException(4, "The maintenance receipt is invalid and the application instance lock is live. Exit Operon manually and retry.");
            return null;
        }

        var host = ValidateProcess(receipt, currentVersionDirectory);
        if (host is not null) return host;

        if (InstanceLockHeld(profile))
            throw new MaintenanceException(4, "The maintenance receipt is stale and the application instance lock is live. Exit Operon manually and retry.");
        return null;
    }

    internal static void RequestQuit(
        OwnedHost host,
        string installationId,
        CancellationToken cancellation)
    {
        NamedPipeClientStream? client = null;
        for (var attempt = 0; attempt < 2 && client is null; attempt++)
        {
            cancellation.ThrowIfCancellationRequested();
            var candidate = new NamedPipeClientStream(".", PipeName(host.Receipt.PipeName), PipeDirection.InOut, PipeOptions.Asynchronous);
            try
            {
                candidate.Connect(3000);
                VerifyServerProcess(candidate, host);
                var requestId = Guid.NewGuid().ToString("D");
                Send(candidate, new
                {
                    schema = 1,
                    installation_id = installationId,
                    token = host.Receipt.Token,
                    action = "quit",
                    request_id = requestId
                });
                var response = ReadFrame(candidate);
                using var document = JsonDocument.Parse(response);
                var root = document.RootElement;
                if (root.GetProperty("schema").GetInt32() != 1 ||
                    root.GetProperty("request_id").GetString() != requestId ||
                    root.GetProperty("status").GetString() != "accepted")
                    throw new MaintenanceException(4, "The application rejected the maintenance request.");
                client = candidate;
            }
            catch (Exception error) when (error is IOException or TimeoutException or JsonException or KeyNotFoundException or InvalidOperationException)
            {
                candidate.Dispose();
                if (attempt == 1) throw new MaintenanceException(4, "The application maintenance channel did not accept the request: " + error.Message);
            }
            catch
            {
                candidate.Dispose();
                throw;
            }
        }
        if (client is null) throw new MaintenanceException(4, "The application maintenance channel is unavailable.");
        using (client)
        {
            WaitForExit(host, cancellation);
        }
    }

    internal static void EnsureNoProcessImagesUnder(string versionsRoot)
    {
        var root = NormalizePath(versionsRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        foreach (var process in Process.GetProcesses())
        {
            using (process)
            {
                var handle = OpenProcess(ProcessQueryLimitedInformation, false, process.Id);
                if (handle == IntPtr.Zero) continue;
                string? image = null;
                try { image = ProcessImage(handle); }
                catch { }
                finally { CloseHandle(handle); }
                if (image is null) continue;
                var full = NormalizePath(image);
                if (full.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    throw new MaintenanceException(4,
                        $"A process is still using installation files: PID {process.Id} ({Path.GetFileName(full)}). Close it and retry uninstall. Nothing was killed.");
            }
        }
    }

    private static void WaitForExit(OwnedHost host, CancellationToken cancellation)
    {
        var deadline = DateTime.UtcNow + ExitTimeout;
        while (true)
        {
            cancellation.ThrowIfCancellationRequested();
            var wait = WaitForSingleObject(host.Handle, 100);
            if (wait == WaitObject0) break;
            if (wait != WaitTimeout)
                throw new MaintenanceException(4, "The owned host process identity became invalid while waiting for it to exit.");
            if (DateTime.UtcNow >= deadline)
                throw new MaintenanceException(4, "Operon did not exit within the maintenance deadline. No installation files were changed.");
        }
        if (!GetExitCodeProcess(host.Handle, out var exitCode))
            throw new MaintenanceException(4, "The owned host exit status could not be read.");
        if (exitCode != 0)
            throw new MaintenanceException(4, $"Operon exited with code {exitCode}. No installation files were changed.");
    }

    private static bool ValidReceipt(MaintenanceReceipt receipt, string installationId)
    {
        if (receipt.Schema != 1 || receipt.InstallationId != installationId) return false;
        if (receipt.Pid == 0 || !Regex.IsMatch(receipt.CreatedFiletime, @"^[1-9][0-9]{0,19}$")) return false;
        if (!receipt.PipeName.StartsWith(PipePrefix, StringComparison.OrdinalIgnoreCase)) return false;
        if (!Regex.IsMatch(receipt.Token, @"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"))
            return false;
        return resetReceipt(receipt.Exe) && receipt.Exe.EndsWith("operon-desktop-experimental.exe", StringComparison.OrdinalIgnoreCase);

        static bool resetReceipt(string value) => !string.IsNullOrWhiteSpace(value) && Path.IsPathFullyQualified(value);
    }

    private static OwnedHost? ValidateProcess(MaintenanceReceipt receipt, string currentVersionDirectory)
    {
        Process process;
        try { process = Process.GetProcessById((int)receipt.Pid); }
        catch (ArgumentException) { return null; }

        // Keep this exact process handle open for the identity checks, the pipe
        // server validation, and the exit wait. Reopening by PID would allow a
        // reused PID to be mistaken for the owned host.
        var handle = OpenProcess(ProcessQueryLimitedInformation | Synchronize, false, (int)receipt.Pid);
        if (handle == IntPtr.Zero)
        {
            process.Dispose();
            return null;
        }
        try
        {
            var image = ProcessImage(handle);
            var created = CreationFiletime(handle);
            if (image is null || created is null || created != receipt.CreatedFiletime)
            {
                CloseHandle(handle);
                process.Dispose();
                return null;
            }
            var fullImage = NormalizePath(image);
            var fullReceipt = NormalizePath(receipt.Exe);
            var versionRoot = NormalizePath(currentVersionDirectory).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!string.Equals(fullImage, fullReceipt, StringComparison.OrdinalIgnoreCase) ||
                !fullImage.StartsWith(versionRoot, StringComparison.OrdinalIgnoreCase) ||
                WaitForSingleObject(handle, 0) == WaitObject0)
            {
                CloseHandle(handle);
                process.Dispose();
                return null;
            }
            return new OwnedHost(process, handle, receipt, fullImage, created);
        }
        catch
        {
            CloseHandle(handle);
            process.Dispose();
            return null;
        }
    }

    private static void VerifyServerProcess(NamedPipeClientStream client, OwnedHost expected)
    {
        if (!GetNamedPipeServerProcessId(client.SafePipeHandle.DangerousGetHandle(), out var serverPid) ||
            serverPid != (uint)expected.Pid)
            throw new MaintenanceException(4, "The pipe server is not the exact owned host process.");
        var image = ProcessImage(expected.Handle);
        var created = CreationFiletime(expected.Handle);
        if (image is null || created is null ||
            created != expected.CreatedFiletime ||
            !string.Equals(NormalizePath(image), expected.ImagePath, StringComparison.OrdinalIgnoreCase) ||
            WaitForSingleObject(expected.Handle, 0) == WaitObject0)
            throw new MaintenanceException(4, "The owned host identity changed before the request.");
    }

    private static string? ProcessImage(IntPtr handle)
    {
        var buffer = new StringBuilder(32768);
        var size = (uint)buffer.Capacity;
        if (!QueryFullProcessImageNameW(handle, 0, buffer, ref size)) return null;
        return buffer.ToString();
    }

    private static string? CreationFiletime(IntPtr handle)
    {
        if (!GetProcessTimes(handle, out var created, out _, out _, out _)) return null;
        return (((ulong)created.HighDateTime << 32) | created.LowDateTime).ToString();
    }

    private static bool InstanceLockHeld(string profile)
    {
        var path = Path.Combine(profile, InstanceLockName);
        if (!File.Exists(path)) return false;
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite);
            try
            {
                stream.Lock(0, 1);
                stream.Unlock(0, 1);
                return false;
            }
            catch (IOException) { return true; }
        }
        catch (IOException) { return true; }
        catch (UnauthorizedAccessException) { return true; }
    }

    private static string NormalizePath(string value)
    {
        var text = value;
        if (text.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase)) text = @"\\" + text[8..];
        else if (text.StartsWith(@"\\?\", StringComparison.Ordinal)) text = text[4..];
        try { return Path.GetFullPath(text); }
        catch (PathTooLongException) { return text; }
    }

    private static string PipeName(string full) =>
        full.StartsWith(PipePrefix, StringComparison.OrdinalIgnoreCase) ? full[PipePrefix.Length..] : full;

    private static void Send(NamedPipeClientStream client, object value)
    {
        var body = JsonSerializer.SerializeToUtf8Bytes(value);
        if (body.Length >= FrameLimit) throw new MaintenanceException(4, "Maintenance request is too large.");
        var framed = new byte[body.Length + 1];
        body.CopyTo(framed, 0);
        framed[^1] = (byte)'\n';
        WriteFrame(client, framed);
    }

    private static void WriteFrame(NamedPipeClientStream client, byte[] frame)
    {
        // One fixed deadline covers the whole write and flush, not each chunk.
        using var deadline = new CancellationTokenSource(FrameTimeout);
        using var abort = deadline.Token.Register(() => CloseQuietly(client));
        try
        {
            client.WriteAsync(frame.AsMemory(), deadline.Token).GetAwaiter().GetResult();
            client.FlushAsync(deadline.Token).GetAwaiter().GetResult();
        }
        catch (Exception error) when (deadline.IsCancellationRequested && error is not MaintenanceException)
        {
            CloseQuietly(client);
            throw new TimeoutException("The maintenance request could not be written within the frame deadline.", error);
        }
    }

    private static byte[] ReadFrame(NamedPipeClientStream client)
    {
        // One fixed deadline covers the entire newline-terminated frame.
        using var deadline = new CancellationTokenSource(FrameTimeout);
        using var abort = deadline.Token.Register(() => CloseQuietly(client));
        var output = new List<byte>(FrameLimit);
        var one = new byte[1];
        try
        {
            while (output.Count < FrameLimit)
            {
                var read = client.ReadAsync(one.AsMemory(0, 1), deadline.Token).GetAwaiter().GetResult();
                if (read == 0) throw new IOException("The maintenance pipe closed unexpectedly.");
                if (one[0] == (byte)'\n') return output.ToArray();
                output.Add(one[0]);
            }
            throw new MaintenanceException(4, "The maintenance reply exceeded the frame limit.");
        }
        catch (Exception error) when (deadline.IsCancellationRequested && error is not MaintenanceException)
        {
            CloseQuietly(client);
            throw new TimeoutException("The maintenance reply could not be read within the frame deadline.", error);
        }
    }

    private static void CloseQuietly(NamedPipeClientStream client)
    {
        try { client.Dispose(); } catch { }
    }

    internal static void CloseProcessHandle(IntPtr handle)
    {
        if (handle != IntPtr.Zero) CloseHandle(handle);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FileTime { public uint LowDateTime; public uint HighDateTime; }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool QueryFullProcessImageNameW(IntPtr process, uint flags, StringBuilder name, ref uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetProcessTimes(IntPtr process, out FileTime creation, out FileTime exit, out FileTime kernel, out FileTime user);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeServerProcessId(IntPtr pipe, out uint serverProcessId);
    [DllImport("kernel32.dll")]
    private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);
}

using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using BioPipe.Setup;

internal static class UpgradeTests
{
    internal static bool RunHost(string[] args)
    {
        if (args.FirstOrDefault() == "--upgrade-worker")
        {
            File.WriteAllText(args[1] + ".ready", "ready");
            while (!File.Exists(args[1])) Thread.Sleep(30);
            Thread.Sleep(1000); // Detached pool releases files after its window exits.
            return true;
        }
        if (args.FirstOrDefault() != "--upgrade-host") return false;
        var profile = args[1];
        Directory.CreateDirectory(profile);
        using var lease = new InstallLease("Local\\BioPipeStudio-" + InstallLease.Identity(profile));
        using var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        File.WriteAllText(Path.Combine(profile, "port.txt"), ((IPEndPoint)listener.LocalEndpoint).Port.ToString());
        _ = Task.Run(async () => {
            while (true)
            {
                using var client = await listener.AcceptTcpClientAsync();
                using var stream = client.GetStream();
                using var reader = new StreamReader(stream, leaveOpen: true);
                while (!string.IsNullOrEmpty(await reader.ReadLineAsync())) { }
                var busy = File.Exists(Path.Combine(profile, "busy"));
                var body = JsonSerializer.Serialize(new { desktop = true, storage = new { profile_dir = profile },
                    history = busy ? new[] { new { status = "running" } } : [] });
                var bytes = Encoding.UTF8.GetBytes(body);
                await stream.WriteAsync(Encoding.ASCII.GetBytes($"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {bytes.Length}\r\nConnection: close\r\n\r\n"));
                await stream.WriteAsync(bytes);
            }
        });
        using var form = new Form { Text = "Operon synthetic update host" };
        form.Shown += (_, _) => File.WriteAllText(Path.Combine(profile, "ready"), "ready");
        form.FormClosing += (_, e) => {
            if (File.Exists(Path.Combine(profile, "refuse"))) { e.Cancel = true; return; }
            File.WriteAllText(Path.Combine(profile, "draft-saved"), "saved through normal window close");
        };
        Application.Run(form);
        return true;
    }

    internal static async Task Run(string root, Action<bool, string> check)
    {
        var targets = new List<UpgradeTarget>();
        var actors = new List<Process>();
        async Task<(UpgradeTarget Target, Process Host)> Start(string label)
        {
            var directory = Path.Combine(root, "upgrade", label);
            Directory.CreateDirectory(directory);
            foreach (var path in Directory.EnumerateFiles(AppContext.BaseDirectory))
                File.Copy(path, Path.Combine(directory, Path.GetFileName(path)), true);
            var executable = Path.Combine(directory, "Operon Studio.exe");
            File.Copy(Environment.ProcessPath!, executable, true);
            var profile = Path.Combine(root, "test-home", ".operon", "profiles", label);
            var start = new ProcessStartInfo(executable) { UseShellExecute = false };
            start.ArgumentList.Add("--upgrade-host"); start.ArgumentList.Add(profile);
            var process = Process.Start(start)!; actors.Add(process);
            for (var attempt = 0; attempt < 100 && !File.Exists(Path.Combine(profile, "ready")); attempt++)
            { if (process.HasExited) throw new Exception("Synthetic update host failed"); await Task.Delay(100); }
            check(File.Exists(Path.Combine(profile, "ready")), "synthetic host not ready");
            return (new(directory, profile), process);
        }
        try
        {
            var first = await Start("first"); var unrelated = await Start("unrelated");
            targets.Add(first.Target);
            var lines = new List<string>();
            var discovery = Path.Combine(root, "test-home", ".biopipe", "admission", Environment.MachineName, "managed-pool");
            Directory.CreateDirectory(discovery);
            File.WriteAllText(Path.Combine(discovery, "instance.json"), JsonSerializer.Serialize(new {
                owner = new { pid = first.Host.Id, created = new DateTimeOffset(first.Host.StartTime).ToUnixTimeMilliseconds() / 1000.0 } }));
            var otherData = Path.Combine(root, "another-client", ".studio");
            var otherJob = Path.Combine(otherData, "jobs", "shared-work"); Directory.CreateDirectory(otherJob);
            File.WriteAllText(Path.Combine(discovery, "workspaces.json"), JsonSerializer.Serialize(new Dictionary<string, object> {
                ["another-client"] = new { data_dir = otherData } }));
            File.WriteAllText(Path.Combine(otherJob, "job.json"), "{\"status\":\"running\"}");
            try { using var unexpected = await InstallUpgrade.Prepare(targets, lines.Add, CancellationToken.None);
                throw new Exception("upgrade ignored another pool workspace's running task"); }
            catch (InvalidOperationException) { check(!first.Host.HasExited && !unrelated.Host.HasExited, "another client's work was not protected"); }
            File.WriteAllText(Path.Combine(otherJob, "job.json"), "{\"status\":\"complete\"}");
            var poolStart = new ProcessStartInfo(Path.Combine(first.Target.Directory, Path.GetFileName(Environment.ProcessPath!))) {
                UseShellExecute = false, CreateNoWindow = true };
            poolStart.ArgumentList.Add("--upgrade-worker");
            var saved = Path.Combine(first.Target.Profile, "draft-saved");
            poolStart.ArgumentList.Add(saved);
            var pool = Process.Start(poolStart)!; actors.Add(pool);
            for (var n = 0; n < 100 && !File.Exists(saved + ".ready"); n++) await Task.Delay(30);
            check(File.Exists(saved + ".ready"), "detached background fixture not ready");
            // The old installer only calls CleanVersion: a live profile is rejected,
            // proving that merely retrying deletion never closes the old window.
            try { using var blocked = new InstallLease("Local\\BioPipeStudio-" + InstallLease.Identity(first.Target.Profile));
                throw new Exception("baseline unexpectedly acquired an active profile"); }
            catch (InvalidOperationException) { check(!first.Host.HasExited, "baseline should leave host alive"); }

            using (await InstallUpgrade.Prepare(targets, lines.Add, CancellationToken.None))
            {
                check(first.Host.HasExited, "upgrade did not close the owned native host");
                check(pool.HasExited, "upgrade did not wait for detached background exit");
                check(File.Exists(Path.Combine(first.Target.Profile, "draft-saved")), "upgrade bypassed normal draft saving");
                check(!unrelated.Host.HasExited, "upgrade closed another installation");
                try { using var held = new InstallLease("Local\\BioPipeStudio-" + InstallLease.Identity(first.Target.Profile));
                    throw new Exception("upgrade did not hold the profile until commit"); }
                catch (InvalidOperationException) { check(true, "profile held"); }
            }
            check(lines.Any(line => line.Contains(first.Host.Id.ToString())), "missing process diagnostics");

            var second = await Start("busy");
            File.WriteAllText(Path.Combine(second.Target.Profile, "busy"), "active task");
            try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None);
                throw new Exception("upgrade closed an active workflow"); }
            catch (InvalidOperationException) { check(!second.Host.HasExited, "active host stopped"); }
            File.Delete(Path.Combine(second.Target.Profile, "busy"));
            // A job below the UI's history limit must still protect the installation.
            var job = Path.Combine(second.Target.Profile, "workspace", ".studio", "jobs", "older-active");
            Directory.CreateDirectory(job); File.WriteAllText(Path.Combine(job, "job.json"), "{\"status\":\"queued\"}");
            try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None);
                throw new Exception("upgrade ignored durable queued task"); }
            catch (InvalidOperationException) { check(!second.Host.HasExited, "queued task host stopped"); }
            File.WriteAllText(Path.Combine(job, "job.json"), "{\"status\":\"complete\"}");

            var remote = Path.Combine(second.Target.Profile, "workspace", ".studio", "remote");
            Directory.CreateDirectory(remote);
            File.WriteAllText(Path.Combine(remote, "profiles.json"), "{\"pending\":{\"request\":\"unknown-result\"},\"jobs\":{}}");
            try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None);
                throw new Exception("upgrade ignored pending remote submission"); }
            catch (InvalidOperationException) { check(!second.Host.HasExited, "pending remote task host stopped"); }
            File.WriteAllText(Path.Combine(remote, "profiles.json"), "{\"pending\":{},\"jobs\":{\"older\":{\"summary\":{\"status\":\"running\"}}}}");
            try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None);
                throw new Exception("upgrade ignored remote task below history limit"); }
            catch (InvalidOperationException) { check(!second.Host.HasExited, "remote task host stopped"); }
            File.WriteAllText(Path.Combine(remote, "profiles.json"), "{\"pending\":{},\"jobs\":{}}");

            File.WriteAllText(Path.Combine(second.Target.Profile, "refuse"), "simulate draft-save refusal");
            try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None, TimeSpan.FromMilliseconds(600));
                throw new Exception("upgrade ignored close refusal"); }
            catch (IOException error) { check(error.Message.Contains(second.Host.Id.ToString()) && !second.Host.HasExited, "timeout should preserve host and identify blocker"); }
            File.Delete(Path.Combine(second.Target.Profile, "refuse"));
            using (var cancelled = new CancellationTokenSource())
            {
                cancelled.Cancel();
                try { using var unexpected = await InstallUpgrade.Prepare([second.Target], lines.Add, cancelled.Token);
                    throw new Exception("cancelled upgrade proceeded"); }
                catch (OperationCanceledException) { check(!second.Host.HasExited, "cancelled update closed the host"); }
            }
            using (await InstallUpgrade.Prepare([second.Target], lines.Add, CancellationToken.None))
                check(second.Host.HasExited, "retry did not close the same host");
        }
        finally
        {
            foreach (var actor in actors)
            {
                if (!actor.HasExited) { actor.CloseMainWindow(); if (!actor.WaitForExit(3000)) actor.Kill(true); }
                actor.Dispose();
            }
        }
    }
}

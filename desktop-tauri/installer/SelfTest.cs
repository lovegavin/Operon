using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.IO.Pipes;

namespace Operon.Setup.Experimental;

internal static class SelfTest
{
    internal static InstallResult Run()
    {
        var root = Path.Combine(Path.GetTempPath(), "operon-experimental-self-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var failures = new List<string>();
        try
        {
            Check(failures, "traversal", () =>
            {
                try { _ = InstallFiles.Inside(root, "../escape.txt"); }
                catch (InvalidDataException) { return; }
                throw new Exception("traversal was accepted");
            });

            Check(failures, "pending-async-pipe-frame", () =>
            {
                var name = "OperonInstallerFrameTest-" + Guid.NewGuid().ToString("N");
                using var server = new NamedPipeServerStream(name, PipeDirection.InOut, 1,
                    PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                var peer = Task.Run(async () =>
                {
                    await server.WaitForConnectionAsync(timeout.Token);
                    // Force the client's memory-based ReadAsync to be pending.
                    await Task.Delay(150, timeout.Token);
                    await server.WriteAsync(Encoding.UTF8.GetBytes("accepted\n"), timeout.Token);
                    await server.FlushAsync(timeout.Token);
                    var ack = new byte[4];
                    await server.ReadExactlyAsync(ack, timeout.Token);
                    if (Encoding.UTF8.GetString(ack) != "ack\n") throw new Exception("ack mismatch");
                });
                using var client = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous);
                client.Connect(3000);
                if (Encoding.UTF8.GetString(MaintenanceClient.ReadFrame(client)) != "accepted")
                    throw new Exception("pending read failed");
                MaintenanceClient.WriteFrame(client, Encoding.UTF8.GetBytes("ack\n"));
                peer.WaitAsync(timeout.Token).GetAwaiter().GetResult();
            });

            Check(failures, "foreign-root-append", () =>
            {
                var selected = Path.Combine(root, "selected");
                Directory.CreateDirectory(selected);
                File.WriteAllText(Path.Combine(selected, "foreign.txt"), "foreign");
                var resolved = PathPolicy.ResolveRoot(selected);
                if (resolved != Path.Combine(selected, "Operon Studio Experimental"))
                    throw new Exception("nonempty unowned root did not append the product child");
                Directory.CreateDirectory(resolved);
                File.WriteAllText(Path.Combine(resolved, "foreign.txt"), "foreign");
                try { _ = PathPolicy.ResolveRoot(selected); }
                catch (InstallerException) { return; }
                throw new Exception("nonempty foreign child was accepted");
            });

            var fileBytes = Encoding.UTF8.GetBytes("payload");
            var fileHash = Convert.ToHexString(SHA256.HashData(fileBytes)).ToLowerInvariant();
            var manifest = new ExperimentalManifest
            {
                Schema = 1,
                Product = ProductIdentity.Product,
                Channel = ProductIdentity.Channel,
                BuildId = "test-build",
                HostVersion = ProductIdentity.HostVersion,
                ManagementRelease = ProductIdentity.ManagementRelease,
                SourceCommit = "test-commit",
                SourceDirty = false,
                Locks = new Dictionary<string, string>(StringComparer.Ordinal)
                {
                    ["cargo_lock_sha256"] = new string('a', 64),
                    ["frontend_lock_sha256"] = new string('b', 64)
                },
                Components = new List<ManifestComponent> { new() { Id = "host", Bytes = fileBytes.Length } },
                Files = new List<ManifestFile> { new("app.txt", fileBytes.Length, fileHash) }
            };
            manifest.PayloadId = ManifestVerifier.ComputePayloadId(manifest);
            Check(failures, "manifest", () =>
            {
                ManifestVerifier.Validate(manifest);
                var wrongProduct = Clone(manifest);
                wrongProduct.Product = "operon";
                MustReject(wrongProduct, "foreign product");
                var wrongChannel = Clone(manifest);
                wrongChannel.Channel = "production";
                MustReject(wrongChannel, "foreign channel");
                var unsafePath = Clone(manifest);
                unsafePath.Files = new List<ManifestFile> { new("../app.txt", 1, new string('c', 64)) };
                try { ManifestVerifier.Validate(unsafePath); }
                catch (InstallerException) { return; }
                throw new Exception("unsafe manifest path was accepted");
            });

            Check(failures, "rollback-snapshot", () =>
            {
                var pointer = Path.Combine(root, "current.json");
                File.WriteAllText(pointer, "old");
                var snapshot = new FileSnapshot(pointer);
                File.WriteAllText(pointer, "new");
                snapshot.Restore();
                if (File.ReadAllText(pointer) != "old") throw new Exception("pointer snapshot did not restore");
            });

            Check(failures, "empty-directory-safety", () =>
            {
                var owned = Path.Combine(root, "owned");
                Directory.CreateDirectory(Path.Combine(owned, "empty"));
                File.WriteAllText(Path.Combine(owned, "keep.txt"), "keep");
                ExperimentalInstaller.RemoveEmptyDirectories(owned);
                if (Directory.Exists(Path.Combine(owned, "empty")))
                    throw new Exception("empty directory was not removed");
                if (!File.Exists(Path.Combine(owned, "keep.txt")))
                    throw new Exception("unknown file was removed");
            });

            Check(failures, "executable-removal-barrier", () =>
            {
                var executable = Path.Combine(root, "barrier.exe");
                File.WriteAllText(executable, "synthetic executable placeholder");
                var expected = InstallFiles.Hash(executable);
                using var barrier = new ExecutableRemovalBarrier();
                barrier.AddExecutable(executable);
                if (barrier.Hash(executable) != expected) throw new Exception("owned handle hash mismatch");
                var denied = false;
                try { using var reader = File.OpenRead(executable); }
                catch (IOException) { denied = true; }
                if (!denied) throw new Exception("new image reader was not excluded");
                File.Delete(executable);
                barrier.Dispose();
                if (File.Exists(executable)) throw new Exception("owned executable was not removed");
            });

            Check(failures, "stage-set", () =>
            {
                var stage = Path.Combine(root, "stage");
                Directory.CreateDirectory(stage);
                var embedded = JsonSerializer.SerializeToUtf8Bytes(manifest, InstallFiles.Json);
                File.WriteAllBytes(Path.Combine(stage, ProductIdentity.ManifestName), embedded);
                File.WriteAllBytes(Path.Combine(stage, "app.txt"), fileBytes);
                ManifestVerifier.VerifyStage(stage, manifest, embedded);
                File.WriteAllText(Path.Combine(stage, "foreign.txt"), "foreign");
                try { ManifestVerifier.VerifyStage(stage, manifest, embedded); }
                catch (InstallerException) { return; }
                throw new Exception("extra stage file was accepted");
            });
        }
        catch (Exception error)
        {
            failures.Add("self-test harness: " + error.Message);
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
        return failures.Count == 0
            ? new InstallResult { Code = 0, Message = "Self-test passed.", Action = "self-test" }
            : new InstallResult { Code = 9, Message = "Self-test failed: " + string.Join("; ", failures), Action = "self-test" };
    }

    private static void Check(List<string> failures, string name, Action action)
    {
        try { action(); }
        catch (Exception error) { failures.Add(name + ": " + error.Message); }
    }

    private static void MustReject(ExperimentalManifest manifest, string description)
    {
        try { ManifestVerifier.Validate(manifest); }
        catch (InstallerException) { return; }
        throw new Exception(description + " was accepted");
    }

    private static ExperimentalManifest Clone(ExperimentalManifest source) => new()
    {
        Schema = source.Schema,
        Product = source.Product,
        Channel = source.Channel,
        BuildId = source.BuildId,
        HostVersion = source.HostVersion,
        ManagementRelease = source.ManagementRelease,
        SourceCommit = source.SourceCommit,
        SourceDirty = source.SourceDirty,
        PayloadId = source.PayloadId,
        Locks = new Dictionary<string, string>(source.Locks, StringComparer.Ordinal),
        Components = source.Components.Select(value => new ManifestComponent { Id = value.Id, Bytes = value.Bytes }).ToList(),
        Files = source.Files.ToList()
    };
}

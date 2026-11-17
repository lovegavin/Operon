using System.Diagnostics;
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

            Check(failures, "library-migration-exact-copy", () =>
            {
                var layout = NewLayout(root, "library-exact");
                var version = layout.VersionDirectory("build-exact");
                var source = Path.Combine(version, "library");
                Directory.CreateDirectory(Path.Combine(source, "packages"));
                Directory.CreateDirectory(Path.Combine(source, "snapshots", "empty"));
                Directory.CreateDirectory(Path.Combine(source, "environments"));
                var pin = Encoding.UTF8.GetBytes("{\"pin\":\"provider@1\",\"audit_archive\":\"C:\\\\absolute\\\\audit.zip\"}");
                var snapshot = Encoding.UTF8.GetBytes("snapshot-bytes");
                var environment = Encoding.UTF8.GetBytes("environment-bytes");
                File.WriteAllBytes(Path.Combine(source, "packages", "pins.json"), pin);
                File.WriteAllBytes(Path.Combine(source, "snapshots", "snap.bin"), snapshot);
                File.WriteAllBytes(Path.Combine(source, "environments", "env.json"), environment);

                var bindingPath = layout.LibraryBinding(version);
                File.WriteAllText(layout.CurrentPath, "old-pointer");

                var result = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId,
                    CancellationToken.None);
                if (!result.Migrated || !result.StableLibraryAvailable || result.Reused)
                    throw new Exception("migration did not report a staged copy");
                var stable = layout.Library;
                if (!File.ReadAllBytes(Path.Combine(stable, "packages", "pins.json")).SequenceEqual(pin))
                    throw new Exception("pin bytes changed");
                if (!File.ReadAllBytes(Path.Combine(stable, "snapshots", "snap.bin")).SequenceEqual(snapshot))
                    throw new Exception("snapshot bytes changed");
                if (!File.ReadAllBytes(Path.Combine(stable, "environments", "env.json")).SequenceEqual(environment))
                    throw new Exception("environment bytes changed");
                if (!Directory.Exists(Path.Combine(stable, "snapshots", "empty")))
                    throw new Exception("empty relative directory was not copied");
                if (!File.ReadAllBytes(Path.Combine(source, "packages", "pins.json")).SequenceEqual(pin))
                    throw new Exception("version-local source library was moved or changed");
                if (File.Exists(bindingPath))
                    throw new Exception("migration published a binding before version commit");
                if (File.ReadAllText(layout.CurrentPath) != "old-pointer")
                    throw new Exception("migration changed the current pointer");
                if (Directory.EnumerateDirectories(layout.Root, ".library-migration-*").Any())
                    throw new Exception("migration staging directory was retained");
            });

            Check(failures, "library-migration-idempotent", () =>
            {
                var layout = NewLayout(root, "library-idempotent");
                var version = layout.VersionDirectory("build-idempotent");
                var source = Path.Combine(version, "library");
                Directory.CreateDirectory(source);
                File.WriteAllText(Path.Combine(source, "pins.json"), "pins");
                var first = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId,
                    CancellationToken.None);
                var stablePins = Path.Combine(layout.Library, "pins.json");
                var firstBytes = File.ReadAllBytes(stablePins);
                var second = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId,
                    CancellationToken.None);
                if (!first.Migrated || !second.Reused || second.Migrated)
                    throw new Exception("repeated migration was not an idempotent reuse");
                if (!File.ReadAllBytes(stablePins).SequenceEqual(firstBytes))
                    throw new Exception("repeated migration changed the stable library");
                if (!File.Exists(Path.Combine(source, "pins.json")))
                    throw new Exception("repeated migration removed the version-local source");
                if (Directory.EnumerateDirectories(layout.Root, ".library-migration-*").Any())
                    throw new Exception("repeated migration retained a staging directory");
            });

            Check(failures, "bound-library-no-content-scan", () =>
            {
                var layout = NewLayout(root, "library-bound-fast");
                var version = layout.VersionDirectory("build-bound");
                Directory.CreateDirectory(version);
                Directory.CreateDirectory(layout.Library);
                ExperimentalInstaller.WriteLibraryBinding(layout, version, layout.InstallationId);
                var file = Path.Combine(layout.Library, "package-held.bin");
                File.WriteAllText(file, "immutable package bytes");
                using var held = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.None);
                var result = ExperimentalInstaller.MigrateLibrary(layout, version,
                    layout.InstallationId, CancellationToken.None);
                if (!result.Reused) throw new Exception("bound library was not reused");
            });

            Check(failures, "library-empty-stable", () =>
            {
                var layout = NewLayout(root, "library-empty");
                var result = ExperimentalInstaller.MigrateLibrary(layout, null, layout.InstallationId,
                    CancellationToken.None);
                if (!result.StableLibraryAvailable || result.Migrated || !Directory.Exists(layout.Library))
                    throw new Exception("a fresh bound version did not get an empty stable library directory");
                if (Directory.EnumerateFileSystemEntries(layout.Library).Any())
                    throw new Exception("the fresh stable library directory was not empty");
            });

            Check(failures, "library-migration-divergent", () =>
            {
                var layout = NewLayout(root, "library-divergent");
                var version = layout.VersionDirectory("build-divergent");
                var source = Path.Combine(version, "library");
                Directory.CreateDirectory(source);
                Directory.CreateDirectory(layout.Library);
                File.WriteAllText(Path.Combine(source, "old.json"), "old");
                File.WriteAllText(Path.Combine(layout.Library, "stable.json"), "stable");

                var rejected = false;
                try { _ = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId, CancellationToken.None); }
                catch (InstallerException error)
                {
                    rejected = true;
                    if (!error.Message.Contains(source) || !error.Message.Contains(layout.Library))
                        throw new Exception("divergence message omitted the exact source/stable paths");
                }
                if (!rejected)
                    throw new Exception("divergent nonempty libraries were merged or replaced");
                if (File.ReadAllText(Path.Combine(source, "old.json")) != "old" ||
                    File.ReadAllText(Path.Combine(layout.Library, "stable.json")) != "stable")
                    throw new Exception("divergent refusal changed one of the libraries");

                ExperimentalInstaller.WriteLibraryBinding(layout, version, layout.InstallationId);
                var bound = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId,
                    CancellationToken.None);
                if (!bound.Reused || bound.Migrated)
                    throw new Exception("a version already bound to the stable library was not authoritative");
                if (!File.Exists(Path.Combine(source, "old.json")) ||
                    !File.Exists(Path.Combine(layout.Library, "stable.json")))
                    throw new Exception("bound reuse removed or merged the divergent copy");
            });

            Check(failures, "library-migration-reparse", () =>
            {
                var layout = NewLayout(root, "library-reparse");
                var version = layout.VersionDirectory("build-reparse");
                var source = Path.Combine(version, "library");
                var outside = Path.Combine(layout.Root, "outside");
                Directory.CreateDirectory(source);
                Directory.CreateDirectory(outside);
                File.WriteAllText(Path.Combine(outside, "target.txt"), "target");
                var link = Path.Combine(source, "linked");
                if (!TryCreateReparsePoint(link, outside))
                    throw new Exception("could not create a directory reparse point for the test");
                try
                {
                    try { _ = ExperimentalInstaller.MigrateLibrary(layout, version, layout.InstallationId, CancellationToken.None); }
                    catch (InstallerException error)
                    {
                        if (error.Message.IndexOf("reparse", StringComparison.OrdinalIgnoreCase) < 0 &&
                            error.Message.IndexOf("link", StringComparison.OrdinalIgnoreCase) < 0)
                            throw new Exception("unexpected reparse rejection: " + error.Message);
                        if (Directory.Exists(layout.Library))
                            throw new Exception("stable library was created despite the reparse point");
                        return;
                    }
                    throw new Exception("a reparse point inside the imported library was accepted");
                }
                finally
                {
                    try { if (Directory.Exists(link)) Directory.Delete(link); } catch { }
                }
            });

            Check(failures, "library-binding-rollback", () =>
            {
                var layout = NewLayout(root, "library-binding-rollback");
                var oldVersion = layout.VersionDirectory("old-build");
                Directory.CreateDirectory(oldVersion);
                var oldBinding = layout.LibraryBinding(oldVersion);
                var oldBytes = Encoding.UTF8.GetBytes(
                    "{\"schema\":1,\"installation_id\":\"" + layout.InstallationId + "\",\"location\":\"../../library\"}");
                File.WriteAllBytes(oldBinding, oldBytes);
                File.WriteAllText(layout.CurrentPath, "old-pointer");

                var bindingSnapshot = new FileSnapshot(oldBinding);
                var pointerSnapshot = new FileSnapshot(layout.CurrentPath);
                var newVersion = layout.VersionDirectory("new-build");
                Directory.CreateDirectory(newVersion);
                var newBindingSnapshot = new FileSnapshot(layout.LibraryBinding(newVersion));

                File.WriteAllText(oldBinding, "replacement-binding");
                ExperimentalInstaller.WriteLibraryBinding(layout, newVersion, layout.InstallationId);
                File.WriteAllText(layout.CurrentPath, "new-pointer");

                bindingSnapshot.Restore();
                newBindingSnapshot.Restore();
                pointerSnapshot.Restore();
                if (!File.ReadAllBytes(oldBinding).SequenceEqual(oldBytes))
                    throw new Exception("rollback did not restore the old binding bytes");
                if (File.Exists(layout.LibraryBinding(newVersion)))
                    throw new Exception("rollback did not remove the promoted binding");
                if (File.ReadAllText(layout.CurrentPath) != "old-pointer")
                    throw new Exception("rollback did not restore the current pointer");
            });

            Check(failures, "library-binding-integrity", () =>
            {
                var layout = NewLayout(root, "library-binding-integrity");
                var version = layout.VersionDirectory("binding-build");
                Directory.CreateDirectory(version);
                File.WriteAllBytes(Path.Combine(version, "app.txt"), fileBytes);
                File.WriteAllText(Path.Combine(version, "host.json"), "{}");
                ExperimentalInstaller.WriteLibraryBinding(layout, version, layout.InstallationId);
                if (!ExperimentalInstaller.HasValidLibraryBinding(version, layout.InstallationId))
                    throw new Exception("generated binding was not accepted");
                if (ExperimentalInstaller.HasValidLibraryBinding(version, Guid.NewGuid().ToString("D")))
                    throw new Exception("binding for another installation was accepted");

                Directory.CreateDirectory(Path.Combine(version, "library"));
                File.WriteAllText(Path.Combine(version, "library", "legacy.json"), "legacy");
                if (!ExperimentalInstaller.VerifyInstalledVersion(version, manifest, allowLegacyLibrary: true))
                    throw new Exception("binding plus legacy library failed integrity checks");
                if (ExperimentalInstaller.VerifyInstalledVersion(version, manifest, allowLegacyLibrary: false))
                    throw new Exception("legacy library was ignored without a stable library");

                File.WriteAllText(Path.Combine(version, "library", "legacy.json"), "tampered");
                if (!ExperimentalInstaller.VerifyInstalledVersion(version, manifest, allowLegacyLibrary: true))
                    throw new Exception("mutable legacy library content was treated as immutable payload");

                File.WriteAllText(Path.Combine(version, "foreign.txt"), "foreign");
                if (ExperimentalInstaller.VerifyInstalledVersion(version, manifest, allowLegacyLibrary: true))
                    throw new Exception("foreign file was accepted");
                File.Delete(Path.Combine(version, "foreign.txt"));

                File.WriteAllText(layout.LibraryBinding(version),
                    "{\"schema\":1,\"installation_id\":\"" + layout.InstallationId + "\",\"location\":\"../../other\"}");
                if (ExperimentalInstaller.HasValidLibraryBinding(version, layout.InstallationId))
                    throw new Exception("binding with a foreign location was accepted");

                ExperimentalInstaller.WriteLibraryBinding(layout, version, layout.InstallationId);
                File.WriteAllText(Path.Combine(version, "app.txt"), "corrupt");
                if (ExperimentalInstaller.VerifyInstalledVersion(version, manifest, allowLegacyLibrary: true))
                    throw new Exception("corrupt manifest-owned file was accepted");
            });

            Check(failures, "retained-library-root", () =>
            {
                var retained = Path.Combine(root, "retained-root");
                var installationId = Guid.NewGuid().ToString("D");
                Directory.CreateDirectory(Path.Combine(retained, "library"));
                var profile = Path.Combine(retained, "profiles", installationId);
                Directory.CreateDirectory(profile);
                File.WriteAllText(Path.Combine(profile, ProductIdentity.ProfileMarker),
                    "{\"schema_version\":1,\"installation_id\":\"" + installationId + "\"}");
                if (PathPolicy.ResolveRoot(retained) != retained)
                    throw new Exception("retained library root was not reused");

                var parent = Path.Combine(root, "retained-parent");
                Directory.CreateDirectory(parent);
                var child = Path.Combine(parent, "Operon Studio Experimental");
                Directory.Move(retained, child);
                if (PathPolicy.ResolveRoot(parent) != child)
                    throw new Exception("retained library child was not reused");
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

    private static InstallationLayout NewLayout(string root, string name)
    {
        var layout = new InstallationLayout(Path.Combine(root, name), Guid.NewGuid().ToString("D"));
        Directory.CreateDirectory(layout.Root);
        return layout;
    }

    private static bool TryCreateReparsePoint(string link, string target)
    {
        try
        {
            Directory.CreateSymbolicLink(link, target);
            return true;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or NotSupportedException) { }

        try
        {
            var command = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe";
            var start = new ProcessStartInfo(command)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                Arguments = $"/d /c mklink /J \"{link}\" \"{target}\""
            };
            using var process = Process.Start(start);
            if (process is null) return false;
            if (!process.WaitForExit(10000)) return false;
            return process.ExitCode == 0 && Directory.Exists(link);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or System.ComponentModel.Win32Exception)
        {
            return false;
        }
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

using System.Text;
using System.Text.Json;

namespace Operon.Setup.Experimental;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        var cli = CommandLine.Parse(args);
        if (cli.Error is not null)
        {
            WriteResult(cli.ResultPath, new InstallResult { Code = 2, Message = cli.Error, Action = "usage" });
            return 2;
        }
        cli.ApplyCompiledDefaults();
        if (cli.Help)
        {
            WriteResult(cli.ResultPath, new InstallResult
            {
                Code = 0,
                Message = "Usage: setup.exe [--silent --install-dir <path> [--uninstall] [--result <path>]] | --self-test [--result <path>]",
                Action = "help"
            });
            return 0;
        }
        if (cli.SelfTest)
        {
            var selfTestResult = SelfTest.Run();
            WriteResult(cli.ResultPath, selfTestResult);
            return selfTestResult.Code;
        }
        if (!cli.Silent)
        {
            Application.Run(new InstallerForm(cli.InstallDir, cli.Uninstall));
            return 0;
        }

        if (string.IsNullOrWhiteSpace(cli.InstallDir))
        {
            WriteResult(cli.ResultPath, new InstallResult { Code = 2, Message = "--install-dir is required with --silent.", Action = "usage" });
            return 2;
        }

        using var log = InstallerLog.Create();
        var engine = new ExperimentalInstaller(log, _ => { });
        InstallResult result;
        try
        {
            result = cli.Uninstall
                ? engine.Uninstall(cli.InstallDir, CancellationToken.None)
                : engine.Install(cli.InstallDir, CancellationToken.None);
        }
        catch (Exception error)
        {
            log.Write("unhandled setup failure: " + error);
            result = new InstallResult
            {
                Code = cli.Uninstall ? 6 : 5,
                Message = (cli.Uninstall ? "Uninstall failed: " : "Installation failed: ") + error.Message,
                Action = cli.Uninstall ? "uninstall" : "install",
                LogPath = log.Path
            };
        }
        WriteResult(cli.ResultPath, result);
        return result.Code;
    }

    private static void WriteResult(string? path, InstallResult result)
    {
        if (string.IsNullOrWhiteSpace(path)) return;
        try
        {
            var full = Path.GetFullPath(path);
            Directory.CreateDirectory(Path.GetDirectoryName(full)!);
            var body = new
            {
                product = ProductIdentity.Product,
                success = result.Success,
                code = result.Code,
                message = result.Message,
                action = result.Action,
                root = result.Root,
                log = result.LogPath,
                completed_utc = DateTime.UtcNow.ToString("O")
            };
            var temporary = full + ".tmp-" + Guid.NewGuid().ToString("N");
            File.WriteAllText(temporary, JsonSerializer.Serialize(body, InstallFiles.Json) + "\n", new UTF8Encoding(false));
            File.Move(temporary, full, true);
        }
        catch
        {
            // A result path failure must not change the already-decided exit code.
        }
    }
}

internal sealed class CommandLine
{
    internal bool Silent { get; private set; }
    internal bool Uninstall { get; private set; }
    internal bool SelfTest { get; private set; }
    internal bool Help { get; private set; }
    internal string? InstallDir { get; private set; }
    internal string? ResultPath { get; private set; }
    internal string? Error { get; private set; }

    internal void ApplyCompiledDefaults()
    {
#if UNINSTALLER_STUB
        if (SelfTest) return;
        // The installed stub is a separate executable; its only product action
        // is uninstall. An explicit --install-dir still selects the root.
        Uninstall = true;
        if (string.IsNullOrWhiteSpace(InstallDir)) InstallDir = InferredUninstallerRoot();
#endif
    }

#if UNINSTALLER_STUB
    private static string? InferredUninstallerRoot()
    {
        var process = Environment.ProcessPath;
        if (string.IsNullOrWhiteSpace(process)) return null;
        try
        {
            // Installed layout: <root>\bin\Operon_Experimental_Uninstall.exe
            var bin = Path.GetDirectoryName(Path.GetFullPath(process));
            if (string.IsNullOrWhiteSpace(bin)) return null;
            var root = Path.GetDirectoryName(bin);
            return string.IsNullOrWhiteSpace(root) ? null : root;
        }
        catch (Exception error) when (error is ArgumentException or IOException or NotSupportedException)
        {
            return null;
        }
    }
#endif

    internal static CommandLine Parse(string[] args)
    {
        var result = new CommandLine();
        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--silent":
                    result.Silent = true;
                    break;
                case "--uninstall":
                    result.Uninstall = true;
                    break;
                case "--self-test":
                    result.Silent = true;
                    result.SelfTest = true;
                    break;
                case "--help":
                case "-h":
                    result.Help = true;
                    break;
                case "--install-dir":
                    if (++index >= args.Length) result.Error = "--install-dir requires a path.";
                    else result.InstallDir = args[index];
                    break;
                case "--result":
                    if (++index >= args.Length) result.Error = "--result requires a path.";
                    else result.ResultPath = args[index];
                    break;
                default:
                    result.Error = "Unknown argument: " + args[index];
                    break;
            }
            if (result.Error is not null) break;
        }
        if (result.Uninstall && result.SelfTest) result.Error = "--uninstall and --self-test cannot be combined.";
        return result;
    }
}

internal sealed class InstallerForm : Form
{
    private readonly TextBox _path = new() { Dock = DockStyle.Fill };
    private readonly Label _status = new() { Dock = DockStyle.Fill, Text = "Choose an installation directory." };
    private readonly ProgressBar _progress = new() { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, Visible = false };
    private readonly Button _install = new() { Text = "Install / Update", AutoSize = true };
    private readonly Button _uninstall = new() { Text = "Uninstall", AutoSize = true };
    private readonly Button _cancel = new() { Text = "Cancel", AutoSize = true, Enabled = false };
    private readonly Button _close = new() { Text = "Close", AutoSize = true };
    private CancellationTokenSource? _cancellation;

    private readonly bool _autoUninstall;

    internal InstallerForm(string? initialPath = null, bool autoUninstall = false)
    {
        _autoUninstall = autoUninstall;
        Text = autoUninstall ? "Operon Studio Experimental Uninstall" : "Operon Studio Experimental Setup";
        Width = 760;
        Height = 300;
        MinimumSize = new Size(620, 260);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 9F);

        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(16), ColumnCount = 1, RowCount = 6 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        root.Controls.Add(new Label { Text = "Install Operon Studio Experimental beside production. The profile is always retained.", AutoSize = true }, 0, 0);

        var pathRow = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100));
        _path.Text = string.IsNullOrWhiteSpace(initialPath) ? ProductIdentity.DefaultRoot : initialPath;
        _path.Anchor = AnchorStyles.Left | AnchorStyles.Right;
        var browse = new Button { Text = "Browse...", Dock = DockStyle.Fill };
        browse.Click += (_, _) =>
        {
            using var dialog = new FolderBrowserDialog { SelectedPath = _path.Text, Description = "Select the experimental installation directory" };
            if (dialog.ShowDialog(this) == DialogResult.OK) _path.Text = dialog.SelectedPath;
        };
        pathRow.Controls.Add(_path, 0, 0);
        pathRow.Controls.Add(browse, 1, 0);
        root.Controls.Add(pathRow, 0, 1);
        root.Controls.Add(_status, 0, 2);
        root.Controls.Add(_progress, 0, 3);

        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
        _close.Click += (_, _) => Close();
        _install.Click += (_, _) => Start(install: true);
        _uninstall.Click += (_, _) => Start(install: false);
        _cancel.Click += (_, _) => _cancellation?.Cancel();
        buttons.Controls.Add(_close);
        buttons.Controls.Add(_cancel);
        buttons.Controls.Add(_uninstall);
        buttons.Controls.Add(_install);
        _install.Visible = !_autoUninstall;
        _uninstall.Visible = _autoUninstall;
        root.Controls.Add(buttons, 0, 5);
        Controls.Add(root);
        FormClosing += (_, args) =>
        {
            if (_cancellation is null) return;
            args.Cancel = true;
            _cancellation.Cancel();
        };
        if (_autoUninstall)
            Shown += (_, _) => BeginInvoke(() => Start(install: false));
    }

    private async void Start(bool install)
    {
        var selected = _path.Text.Trim();
        if (selected.Length == 0)
        {
            _status.Text = "Enter an installation directory.";
            _path.Focus();
            return;
        }
        if (!install && MessageBox.Show(this,
                "Uninstall Operon Studio Experimental? Profiles and unknown files are retained.",
                "Uninstall Operon Studio Experimental", MessageBoxButtons.OKCancel, MessageBoxIcon.Warning) != DialogResult.OK)
            return;

        SetBusy(true);
        _status.Text = install ? "Installing..." : "Uninstalling...";
        _cancellation = new CancellationTokenSource();
        var token = _cancellation.Token;
        try
        {
            var result = await Task.Run(() =>
            {
                using var log = InstallerLog.Create();
                var engine = new ExperimentalInstaller(log, message =>
                {
                    if (!IsDisposed && IsHandleCreated)
                        BeginInvoke(() => { if (!IsDisposed) _status.Text = message; });
                });
                return install ? engine.Install(selected, token) : engine.Uninstall(selected, token);
            });
            _status.Text = result.Message;
            if (result.Root is not null) _path.Text = result.Root;
            if (result.Success && install)
                MessageBox.Show(this, result.Message, "Operon Studio Experimental", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception error)
        {
            _status.Text = "Operation failed: " + error.Message;
            _logUI(error);
        }
        finally
        {
            _cancellation?.Dispose();
            _cancellation = null;
            SetBusy(false);
        }
    }

    private void _logUI(Exception error)
    {
        try
        {
            using var log = InstallerLog.Create();
            log.Write("interactive setup failure: " + error);
        }
        catch { }
    }

    private void SetBusy(bool busy)
    {
        _progress.Visible = busy;
        _install.Enabled = !busy;
        _uninstall.Enabled = !busy;
        _cancel.Enabled = busy;
        _close.Enabled = !busy;
        _path.ReadOnly = busy;
        if (!busy) _path.ReadOnly = false;
        UseWaitCursor = busy;
    }
}

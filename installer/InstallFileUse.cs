using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace Operon.Setup;

// Query only; never ask Restart Manager to kill/restart other applications.
// https://learn.microsoft.com/windows/win32/rstmgr/functions
internal static class InstallFileUse
{
    [StructLayout(LayoutKind.Sequential)]
    private struct UniqueProcess
    {
        public uint Pid;
        public System.Runtime.InteropServices.ComTypes.FILETIME Started;
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessInfo
    {
        public UniqueProcess Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string Name;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string Service;
        public uint ApplicationType;
        public uint Status;
        public uint Session;
        [MarshalAs(UnmanagedType.Bool)] public bool Restartable;
    }
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmStartSession(out uint session, uint flags, StringBuilder key);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmRegisterResources(uint session, uint count, string[] files,
        uint applications, IntPtr processes, uint services, IntPtr names);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmGetList(uint session, out uint needed, ref uint count,
        [In, Out] ProcessInfo[]? processes, ref uint rebootReasons);
    [DllImport("rstrtmgr.dll")]
    private static extern int RmEndSession(uint session);

    internal static void AssertUnused(List<string> files)
    {
        if (files.Count == 0) return;
        var result = RmStartSession(out var session, 0, new StringBuilder(Guid.NewGuid().ToString("N"), 33));
        if (result != 0) throw new IOException("无法确认文件占用状态，软件尚未删除。", new Win32Exception(result));
        try
        {
            foreach (var batch in files.Chunk(512))
            {
                result = RmRegisterResources(session, (uint)batch.Length, batch, 0, IntPtr.Zero, 0, IntPtr.Zero);
                if (result != 0) throw new IOException("无法检查安装文件占用，软件尚未删除。", new Win32Exception(result));
            }
            uint count = 0, reasons = 0;
            ProcessInfo[]? processes = null;
            for (var attempt = 0; attempt < 4; attempt++)
            {
                result = RmGetList(session, out var needed, ref count, processes, ref reasons);
                if (result == 0)
                {
                    if (count > 0)
                        throw new IOException("软件文件仍被以下程序占用，尚未开始删除。请关闭对应程序后重试：" +
                            string.Join(", ", processes!.Take((int)count).Select(p => $"{p.Name} (PID {p.Process.Pid})")));
                    return;
                }
                if (result != 234 || needed > 4096) break; // ERROR_MORE_DATA
                count = needed; processes = new ProcessInfo[needed];
            }
            throw new IOException("文件占用状态正在变化，软件尚未删除。请稍候重试。", new Win32Exception(result));
        }
        finally { RmEndSession(session); }
    }
}

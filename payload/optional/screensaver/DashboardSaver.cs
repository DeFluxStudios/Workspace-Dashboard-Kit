// DashboardSaver.cs - Windows screensaver (.scr) that shows this workspace's dashboard full screen.
// Part of the workspace dashboard kit (optional extra). Own code.
// Opens Edge (or Chrome) in kiosk mode with its own profile, then closes it on any mouse or keyboard input.
// Args from Windows: /s run, /p <hwnd> preview (does nothing), /c settings (shows which page it will open).
// Which page: the path in DashboardSaver.path.txt beside the .scr; otherwise the nearest Workspace_Dashboard.html
// found by walking up from the .scr's folder. Build with build_screensaver.cmd.
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

static class DashboardSaver
{
    const string ProfileTag = "workspace_dashboard_saver_profile";

    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO i);

    static uint LastInput()
    {
        var i = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
        GetLastInputInfo(ref i);
        return i.dwTime;
    }

    static string Here()
    {
        return Path.GetDirectoryName(Path.GetFullPath(Application.ExecutablePath));
    }

    static string FindDashboard()
    {
        string here = Here();
        string pathFile = Path.Combine(here, "DashboardSaver.path.txt");
        if (File.Exists(pathFile))
        {
            string p = File.ReadAllText(pathFile).Trim().Trim('"');
            if (p.Length > 0) return Path.GetFullPath(Path.Combine(here, p));
        }
        for (var d = new DirectoryInfo(here); d != null; d = d.Parent)
        {
            string c = Path.Combine(d.FullName, "Workspace_Dashboard.html");
            if (File.Exists(c)) return c;
        }
        return null;
    }

    static string FindBrowser()
    {
        string pf86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string pf = Environment.GetEnvironmentVariable("ProgramW6432") ?? Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string[] tries = {
            Path.Combine(pf86, @"Microsoft\Edge\Application\msedge.exe"),
            Path.Combine(pf, @"Microsoft\Edge\Application\msedge.exe"),
            Path.Combine(pf, @"Google\Chrome\Application\chrome.exe"),
            Path.Combine(pf86, @"Google\Chrome\Application\chrome.exe"),
            Path.Combine(local, @"Google\Chrome\Application\chrome.exe"),
        };
        foreach (var t in tries) if (File.Exists(t)) return t;
        return null;
    }

    [STAThread]
    static void Main(string[] args)
    {
        string mode = args.Length > 0 ? args[0].ToLowerInvariant().Substring(0, Math.Min(2, args[0].Length)) : "/c";
        if (mode == "/p") return;
        string page = FindDashboard();
        string browser = FindBrowser();
        if (mode != "/s")
        {
            MessageBox.Show("Shows the workspace dashboard full screen.\nMove the mouse or press a key to exit.\n\n" +
                "Page: " + (page ?? "(not found: run install_screensaver.ps1 again)") + "\n" +
                "Browser: " + (browser ?? "(Edge or Chrome not found)"),
                "Dashboard screensaver");
            return;
        }
        if (page == null || !File.Exists(page) || browser == null) return;

        string profile = Path.Combine(Path.GetTempPath(), ProfileTag);
        string url = new Uri(page).AbsoluteUri;
        bool edge = browser.EndsWith("msedge.exe", StringComparison.OrdinalIgnoreCase);
        string kiosk = edge ? "--kiosk \"" + url + "\" --edge-kiosk-type=fullscreen" : "--kiosk \"" + url + "\"";
        var psi = new ProcessStartInfo(browser,
            kiosk + " --no-first-run --no-default-browser-check --disable-features=Translate --user-data-dir=\"" + profile + "\"");
        psi.UseShellExecute = false;
        Process p = Process.Start(psi);

        Thread.Sleep(2500);                 // let the window appear; ignore input caused by it opening
        uint baseline = LastInput();
        while (!p.HasExited)
        {
            if (LastInput() != baseline) break;
            Thread.Sleep(150);
        }
        // Close only browser processes using the saver's own profile, never the normal browser.
        try
        {
            using (var s = new System.Management.ManagementObjectSearcher(
                "SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name='msedge.exe' OR Name='chrome.exe'"))
                foreach (System.Management.ManagementObject o in s.Get())
                {
                    var cl = o["CommandLine"] as string;
                    if (cl != null && cl.Contains(ProfileTag))
                        try { Process.GetProcessById(Convert.ToInt32(o["ProcessId"])).Kill(); } catch { }
                }
        }
        catch { }
        try { if (!p.HasExited) p.Kill(); } catch { }
    }
}

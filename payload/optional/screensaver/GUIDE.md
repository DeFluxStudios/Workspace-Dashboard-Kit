# Dashboard screensaver: full guide

This guide explains how to turn your workspace dashboard into a Windows screensaver. It is written for someone who has not done this kind of thing before. Every step says what to type, what you should see, and what to do if something goes wrong.

You can also hand the whole job to an AI assistant (such as Claude Code). Section 2 has a prompt you can paste.

---

## Contents

1. What this is
2. Let your AI assistant do it
3. Before you start
4. Step by step (by hand)
5. Choosing how long before it starts
6. Turning it off or removing it
7. Troubleshooting
8. How it works (technical details)
9. Safety and privacy
10. Files in this folder

---

## 1. What this is

When your PC has been idle for a while, Windows starts a screensaver. This one shows your workspace dashboard full screen (the red, black and blue page made by the dashboard kit) instead of the usual Windows picture. Moving the mouse or pressing any key closes it, the same as any screensaver.

- It is **optional**. The dashboard kit does not install it unless you ask.
- It only works on **Windows 10 or 11**.
- It does not change your dashboard, your files or your normal web browser.
- You can undo it fully with one command (section 6).

---

## 2. Let your AI assistant do it

Open your AI coding assistant in the workspace that has the dashboard, and paste this:

```
Read workspace_dashboard/optional/screensaver/GUIDE.md and follow it to set up the dashboard screensaver on this PC.
Check section 3 first and tell me if anything is missing. Build it and let me test it before you activate it.
Ask me before running -Activate, because it changes my Windows screensaver setting.
Tell me the idle time you will use (default 10 minutes) and how to undo it.
```

**Notes for the AI assistant:**
- The kit installs this folder at `<workspace>/workspace_dashboard/optional/screensaver/`. If the dashboard page `Workspace_Dashboard.html` does not exist yet, build the dashboard first (`python workspace_dashboard/build_dashboard.py`).
- Run the installer from PowerShell with `-ExecutionPolicy Bypass -File` as shown in section 4. It needs no admin rights.
- Do not run `-Activate` without the person's yes. Do not start the screensaver with `/s` yourself: it fills their screen. Let them test it (step 4.4).
- Report what was built, which page it shows, and whether it was activated. If something fails, use section 7 and quote the exact error.
- Never put personal information (names, emails, account names, private paths) in any file you write while doing this.

---

## 3. Before you start

Check these three things.

| You need | How to check | If it is missing |
|---|---|---|
| Windows 10 or 11 | Press the Windows key, type `winver`, press Enter. | This screensaver does not work on Mac or Linux. |
| Microsoft Edge or Google Chrome | Edge comes with Windows. Look for it in the Start menu. | Install Edge or Chrome. |
| The dashboard built at least once | Look for `workspace_dashboard\Workspace_Dashboard.html` in your workspace folder. | Double-click `Open_Dashboard.cmd` in your workspace, or run `python workspace_dashboard\build_dashboard.py`. |

You also need the **.NET Framework 4**, which is part of every Windows 10 and 11 PC. The installer uses the C# compiler that comes with it, so you don't need to download any programming tools.

---

## 4. Step by step (by hand)

### 4.1 Open PowerShell in the screensaver folder

1. Open File Explorer and go to your workspace folder.
2. Open `workspace_dashboard`, then `optional`, then `screensaver`.
3. Click the address bar at the top, type `powershell` and press Enter.

A blue or black PowerShell window opens in this folder.

### 4.2 Build the screensaver

Type this and press Enter:

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1
```

You should see three lines like these:

```
Built   ...\workspace_dashboard\optional\screensaver\DashboardSaver.scr
Shows   ...\workspace_dashboard\Workspace_Dashboard.html
Not activated. Try it: right-click DashboardSaver.scr > Test. Make it the screensaver with -Activate.
```

This step only creates two files in this folder: `DashboardSaver.scr` (the screensaver program) and `DashboardSaver.path.txt` (which page it shows). It doesn't change any Windows settings yet.

### 4.3 What `-ExecutionPolicy Bypass` means

Windows blocks PowerShell scripts by default. This option lets just this one script run, just this once. It doesn't change your PC's settings.

### 4.4 Test it

1. In File Explorer, right-click `DashboardSaver.scr`.
2. Choose **Test**. On Windows 11 you may need **Show more options** first.
3. Your dashboard should fill the screen after a second or two.
4. Move the mouse. It should close.

If it doesn't work, see section 7.

### 4.5 Make it your screensaver

When you are happy with the test, type:

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1 -Activate
```

You should see:

```
Active: starts after 10 minutes idle. Undo with -Remove.
```

Your old screensaver setting is saved first in `previous_screensaver.json`, so it can be put back later.

### 4.6 Check it in Windows Settings (optional)

Press the Windows key, type `screen saver`, and open **Change screen saver**. The list should show **DashboardSaver**. You can also use the **Preview** button there.

---

## 5. Choosing how long before it starts

Add `-WaitMinutes` with a number:

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1 -Activate -WaitMinutes 5
```

You can also change the wait in **Change screen saver** in Windows (section 4.6).

---

## 6. Turning it off or removing it

**Remove it completely and put your old screensaver back:**

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1 -Remove
```

This puts your previous screensaver setting back and deletes `DashboardSaver.scr` and `DashboardSaver.path.txt`. The source files stay, so you can build it again later.

**Just switch it off for now:** open **Change screen saver** in Windows and choose **(None)** or another screensaver.

**If you are removing the whole dashboard:** run `-Remove` first, then delete the `workspace_dashboard` folder.

---

## 7. Troubleshooting

| What you see | Why | What to do |
|---|---|---|
| `Workspace_Dashboard.html not found above this folder` | The dashboard was never built, or this folder was moved out of the workspace. | Build the dashboard (section 3), then run step 4.2 again. |
| `C# compiler not found` | The .NET Framework 4 is missing or turned off. | Open **Turn Windows features on or off**, tick **.NET Framework 4.8 Advanced Services**, then try again. |
| `Build failed.` | The compiler reported an error above that line. | Read the error lines above it. If you changed `DashboardSaver.cs`, undo your change. |
| `running scripts is disabled on this system` | The command was typed without `-ExecutionPolicy Bypass`. | Use the exact command from step 4.2. |
| Test shows nothing | Edge and Chrome are not in their usual places, or the page moved. | Right-click `DashboardSaver.scr` and choose **Configure**. It shows which page and browser it found. Run step 4.2 again if the page path is wrong. |
| Black screen for a second, then the dashboard | The browser is starting. | This is normal. |
| It closes as soon as it opens | Something keeps sending input (a mouse that jitters, a game controller, a tool that moves the mouse). | Unplug or stop that device or tool, then test again. |
| The dashboard shows old information | The page is only as fresh as its last build. | Rebuild the dashboard, or keep its updater window running. |
| Antivirus warns about `DashboardSaver.scr` | It is a new program built on your PC, so the antivirus has never seen it before. | You can read every line of it in `DashboardSaver.cs` (about 120 lines). If you are unsure, don't use it, and run `-Remove`. |
| You moved or renamed the workspace | `DashboardSaver.path.txt` still points to the old place. | Run step 4.2 again, and step 4.5 if it was active. |

---

## 8. How it works (technical details)

**Windows screensavers** are ordinary programs whose file name ends in `.scr`. Windows starts them with one of three arguments:
- `/s` to run full screen;
- `/p <window>` to draw a small preview in the Settings window (this one draws nothing there);
- `/c` to show its settings (this one shows a box with the page and browser it found).

The active screensaver is stored per user in the registry, under `HKEY_CURRENT_USER\Control Panel\Desktop`:

| Value | Meaning |
|---|---|
| `SCRNSAVE.EXE` | Full path to the `.scr` file |
| `ScreenSaveActive` | `1` means on |
| `ScreenSaveTimeOut` | Idle time in seconds |

**`DashboardSaver.cs`** is a small C# program for the .NET Framework 4:
1. **Finds the page.** It reads `DashboardSaver.path.txt` beside the `.scr`. If that file is missing, it walks up the folders from where the `.scr` sits until it finds `Workspace_Dashboard.html`.
2. **Finds a browser.** It tries Edge (32-bit and 64-bit Program Files), then Chrome (Program Files and the per-user install).
3. **Opens the page** with `--kiosk` (full screen, no address bar) and its own profile folder in your temporary folder, `%TEMP%\workspace_dashboard_saver_profile`. A separate profile keeps your normal browser windows, tabs, history and logins apart and untouched.
4. **Watches for input.** It waits 2.5 seconds so the window opening doesn't count as input. Then it checks every 0.15 seconds with the Windows `GetLastInputInfo` function to see if the mouse or keyboard was used.
5. **Closes the window.** On input, it closes only browser processes whose command line contains that profile name, so your own browser is never closed.

**`build_screensaver.cmd`** runs `csc.exe` from `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\` (or the 32-bit folder) and links `System.Windows.Forms` and `System.Management`.

**`install_screensaver.ps1`** does the following:
- **Finds the page** the same way, by walking up the folders.
- **Builds** the `.scr` and writes `DashboardSaver.path.txt`.
- **With `-Activate`:**
  - saves the three registry values above to `previous_screensaver.json`, only the first time, so a second run never overwrites your real old setting;
  - then sets them to this screensaver.
- **With `-Remove`:** writes the saved values back (deleting any that were empty before) and deletes the built files.

**No prebuilt program is shipped.** The kit contains only source code, which is built on your own PC. You can read exactly what will run before you run it.

---

## 9. Safety and privacy

- **Nothing leaves your PC.** The screensaver opens a local file. It has no network code and sends no data anywhere.
- **No admin rights.** Only your own user settings are changed, and only with `-Activate`.
- **What's on screen:** the screensaver shows your dashboard, which is built from your workspace's own files. Anyone near your screen can read it while it runs. If your dashboard shows something private, either don't use the screensaver or remove that content from the dashboard first.
- **The kit itself** carries no personal information from the project it came from. The starter friends and profile are placeholders until you fill them in.
- **Your browser data is not used.** The screensaver's browser profile is separate and holds nothing of yours. You can delete `%TEMP%\workspace_dashboard_saver_profile` at any time.

---

## 10. Files in this folder

| File | What it is | Made by |
|---|---|---|
| `GUIDE.md` | This guide | Kit |
| `README.md` | Short version | Kit |
| `DashboardSaver.cs` | The screensaver's source code | Kit |
| `build_screensaver.cmd` | Compiles the source into `DashboardSaver.scr` | Kit |
| `install_screensaver.ps1` | Builds, activates, removes | Kit |
| `DashboardSaver.scr` | The built screensaver | Step 4.2 |
| `DashboardSaver.path.txt` | Which page to show | Step 4.2 |
| `previous_screensaver.json` | Your old screensaver setting | Step 4.5 |

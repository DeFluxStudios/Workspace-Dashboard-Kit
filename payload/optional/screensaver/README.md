# Dashboard screensaver (optional, Windows)

Shows this workspace's dashboard full screen when the PC is idle, in the same red, black and blue style. Moving the mouse or pressing a key closes it. It is not installed by default. Ask the person before running it.

**Full step-by-step guide, troubleshooting and technical details: [GUIDE.md](GUIDE.md).** It also has a prompt to hand the job to an AI assistant.

## Needs

- Windows 10 or 11 (uses the C# compiler that ships with Windows, .NET Framework 4).
- Microsoft Edge or Google Chrome.
- The dashboard built at least once (`workspace_dashboard\Workspace_Dashboard.html` exists).

## Install

In PowerShell, from this folder:

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1            builds it; nothing else changes
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1 -Activate  also makes it your screensaver (10 minutes idle)
```

`-WaitMinutes 5` changes the idle time. To try it first, right-click `DashboardSaver.scr` and choose **Test**.

## How it works

- `DashboardSaver.cs` is the whole program, about 120 lines. `build_screensaver.cmd` compiles it into `DashboardSaver.scr`. No prebuilt program is shipped, so what runs is what you can read.
- It opens the page in a kiosk browser window with its own temporary profile, and closes only that window. Your normal browser is never touched.
- The page it shows is written in `DashboardSaver.path.txt`. If that file is missing, it uses the nearest `Workspace_Dashboard.html` above its folder.
- `-Activate` changes only the current user's screensaver setting, and saves the old setting first in `previous_screensaver.json`.

## Remove

```
powershell -ExecutionPolicy Bypass -File install_screensaver.ps1 -Remove
```

This puts the old screensaver setting back and deletes the built files. Deleting this folder afterwards removes the rest.

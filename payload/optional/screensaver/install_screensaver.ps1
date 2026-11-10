<#
Optional extra of the workspace dashboard kit: a Windows screensaver that shows this workspace's dashboard.
Opt-in. Ask the person before running it, because -Activate changes their screensaver setting.

  install_screensaver.ps1             builds DashboardSaver.scr here and points it at this workspace's page
  install_screensaver.ps1 -Activate   also makes it the current user's screensaver (old setting saved first)
  install_screensaver.ps1 -Remove     puts the old screensaver setting back and deletes the built files

Only the current user's settings are touched (HKCU\Control Panel\Desktop). No admin rights needed.
#>
param([switch]$Activate, [switch]$Remove, [int]$WaitMinutes = 10)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$scr = Join-Path $here 'DashboardSaver.scr'
$pathFile = Join-Path $here 'DashboardSaver.path.txt'
$saved = Join-Path $here 'previous_screensaver.json'
$key = 'HKCU:\Control Panel\Desktop'

if ($Remove) {
    if (Test-Path $saved) {
        $old = Get-Content $saved -Raw | ConvertFrom-Json
        foreach ($n in 'SCRNSAVE.EXE', 'ScreenSaveActive', 'ScreenSaveTimeOut') {
            $v = $old.$n
            if ($null -eq $v -or $v -eq '') { Remove-ItemProperty -Path $key -Name $n -ErrorAction SilentlyContinue }
            else { Set-ItemProperty -Path $key -Name $n -Value $v }
        }
        Remove-Item $saved
        Write-Output 'Previous screensaver setting restored.'
    }
    Remove-Item $scr, $pathFile -ErrorAction SilentlyContinue
    Write-Output 'Screensaver files removed. The source files stay.'
    exit 0
}

# The kit puts the page at <workspace>\workspace_dashboard\Workspace_Dashboard.html; this script sits in
# <workspace>\workspace_dashboard\optional\screensaver. Search upward so a custom layout still works.
$page = $null
$d = Get-Item $here
while ($d) {
    $c = Join-Path $d.FullName 'Workspace_Dashboard.html'
    if (Test-Path $c) { $page = $c; break }
    $d = $d.Parent
}
if (-not $page) { throw 'Workspace_Dashboard.html not found above this folder. Build the dashboard first.' }

& cmd /c "`"$(Join-Path $here 'build_screensaver.cmd')`""
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $scr)) { throw 'Build failed.' }
Set-Content -Path $pathFile -Value $page -Encoding UTF8
Write-Output "Built $scr"
Write-Output "Shows   $page"

if ($Activate) {
    if (-not (Test-Path $saved)) {
        $p = Get-ItemProperty -Path $key
        @{ 'SCRNSAVE.EXE' = $p.'SCRNSAVE.EXE'; 'ScreenSaveActive' = $p.ScreenSaveActive; 'ScreenSaveTimeOut' = $p.ScreenSaveTimeOut } |
            ConvertTo-Json | Set-Content -Path $saved -Encoding UTF8
    }
    Set-ItemProperty -Path $key -Name 'SCRNSAVE.EXE' -Value $scr
    Set-ItemProperty -Path $key -Name 'ScreenSaveActive' -Value '1'
    Set-ItemProperty -Path $key -Name 'ScreenSaveTimeOut' -Value ([string]($WaitMinutes * 60))
    Write-Output "Active: starts after $WaitMinutes minutes idle. Undo with -Remove."
} else {
    Write-Output 'Not activated. Try it: right-click DashboardSaver.scr > Test. Make it the screensaver with -Activate.'
}

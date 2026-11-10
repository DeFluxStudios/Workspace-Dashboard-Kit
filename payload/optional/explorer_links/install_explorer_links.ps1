# Optional, and needs the owner's approval. Registers this workspace's link type for the current
# Windows user, so dashboard links can open File Explorer. Writes only HKCU\Software\Classes\<Scheme>;
# no administrator needed. Then set "reveal_links": true in dashboard_config.json.
#   Find the scheme: "Explorer link scheme" in the output of build_dashboard.py --doctor.
#   Install: powershell -ExecutionPolicy Bypass -File install_explorer_links.ps1 -Scheme wsdash-xxxxxxxx
#   Remove:  add -Uninstall
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^wsdash-[0-9a-f]{8}$')][string]$Scheme,
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"

$key = "HKCU:\Software\Classes\$Scheme"
if ($Uninstall) {
    if (Test-Path $key) { Remove-Item -Path $key -Recurse -Force }
    Write-Output "Removed $Scheme links."
    exit 0
}

$handler = Join-Path $PSScriptRoot "open_in_explorer.ps1"
$command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$handler`" `"%1`""
New-Item -Path "$key\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path $key -Name "(default)" -Value "URL:Workspace dashboard location"
Set-ItemProperty -Path $key -Name "URL Protocol" -Value ""
Set-ItemProperty -Path "$key\shell\open\command" -Name "(default)" -Value $command
Write-Output "Registered $Scheme links for this user: $command"

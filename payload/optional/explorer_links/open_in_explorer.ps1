# Handles this workspace's wsdash-xxxxxxxx: links by showing the target in File Explorer.
# It never runs or opens the target itself, and refuses anything outside this workspace.
param(
    [Parameter(Mandatory = $true)][string]$Link,
    [switch]$ValidateOnly
)
$ErrorActionPreference = "Stop"

# This file sits in workspace_dashboard\optional\explorer_links, three folders below the workspace.
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))

function Resolve-WorkspacePath([string]$Value) {
    $relative = [Uri]::UnescapeDataString(($Value -replace '^wsdash-[0-9a-f]+:', '')).Replace('/', '\')
    if ([string]::IsNullOrWhiteSpace($relative)) { return $root }
    if ([IO.Path]::IsPathRooted($relative)) { throw "Absolute paths are refused." }
    $full = [IO.Path]::GetFullPath((Join-Path $root $relative))
    # The trailing separator stops a sibling such as work-other from passing as inside work.
    $inside = $full -ieq $root -or $full.StartsWith($root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
    if (-not $inside) { throw "Outside the workspace." }
    if (-not (Test-Path -LiteralPath $full)) { throw "Not found." }
    return $full
}

try {
    $target = Resolve-WorkspacePath $Link
} catch {
    if ($ValidateOnly) { Write-Output "REFUSED: $($_.Exception.Message)"; exit 1 }
    Add-Type -AssemblyName PresentationFramework
    [void][Windows.MessageBox]::Show("Could not show this location.`n$($_.Exception.Message)", "Workspace dashboard")
    exit 1
}

if ($ValidateOnly) { Write-Output "OK: $target"; exit 0 }
if (Test-Path -LiteralPath $target -PathType Container) {
    Start-Process explorer.exe -ArgumentList "`"$target`""
} else {
    Start-Process explorer.exe -ArgumentList "/select,`"$target`""
}

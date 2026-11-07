# Script to create a Desktop shortcut for AI Video Creator
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$TargetBat = Join-Path $PSScriptRoot "..\launch.bat"
$TargetBat = (Resolve-Path $TargetBat).Path
$WorkingDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$ShortcutPath = Join-Path $DesktopPath "AI Video Creator.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetBat
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "Launch AI Video Creator WebApp"

# Look for an icon or use python icon if available
$IconCandidate = Join-Path $WorkingDir "remotion-video\build\favicon.ico"
if (Test-Path $IconCandidate) {
    $Shortcut.IconLocation = "$IconCandidate,0"
}

$Shortcut.Save()
Write-Host "[+] Desktop shortcut successfully created at: $ShortcutPath" -ForegroundColor Green

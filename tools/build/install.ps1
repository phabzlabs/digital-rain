# Installs a built MatrixRain into a folder it runs from, then warms it up.
#   powershell -ExecutionPolicy Bypass -File tools\build\install.ps1 [-Source <folder or zip>] [-Dest <folder>] [-NoWarmUp]
#   -Source    dist\MatrixRain (default) or a MatrixRain.zip from build.ps1 or a release
#   -Dest      the install folder (default %LOCALAPPDATA%\Programs\MatrixRain)
#   -NoWarmUp  skip the warm-up run
# The old MatrixRain.scr and _internal in -Dest are replaced; anything else there (a fonts
# folder, say) is kept. The screensaver choice in Windows is not touched: a first install
# still needs right-click MatrixRain.scr > Install.
#
# Warm-up: Windows Defender scans freshly written libraries the first time they load, which
# made the first launch after an install take seconds. MatrixRain.scr --warm-up loads them
# once, hidden, for about a second, so the first real launch is as quick as later ones.
param(
    [string]$Source = "",
    [string]$Dest = "",
    [switch]$NoWarmUp
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Fail($msg) {
    Write-Host $msg
    exit 1
}

if (-not $Source) { $Source = Join-Path $root "dist\MatrixRain" }
if (-not $Dest) { $Dest = Join-Path $env:LOCALAPPDATA "Programs\MatrixRain" }
if (-not (Test-Path $Source)) { Fail "Nothing to install: $Source not found (run build.ps1 first)" }

$unzipped = $null
if ((Get-Item $Source).PSIsContainer) {
    $from = $Source
} else {
    $unzipped = Join-Path $env:TEMP ("MatrixRain-install-" + [guid]::NewGuid().ToString("N"))
    Expand-Archive -Path $Source -DestinationPath $unzipped
    $from = Join-Path $unzipped "MatrixRain"
}
try {
    if (-not (Test-Path (Join-Path $from "MatrixRain.scr"))) { Fail "$from has no MatrixRain.scr" }
    if (-not (Test-Path (Join-Path $from "_internal"))) { Fail "$from has no _internal folder" }

    # A running saver or preview holds its files open.
    $exe = Join-Path $Dest "MatrixRain.scr"
    $running = Get-CimInstance Win32_Process -Filter "Name = 'MatrixRain.scr'" |
        Where-Object { $_.ExecutablePath -eq $exe }
    if ($running) { Fail "MatrixRain is running from $Dest (saver or preview); close it first" }

    New-Item -ItemType Directory -Force $Dest | Out-Null
    foreach ($old in "_internal", "MatrixRain.scr") {
        $path = Join-Path $Dest $old
        if (Test-Path $path) { Remove-Item $path -Recurse -Force }
    }
    Copy-Item (Join-Path $from "*") $Dest -Recurse -Force
    Write-Host "Installed to $Dest"
} finally {
    if ($unzipped) { Remove-Item $unzipped -Recurse -Force -ErrorAction SilentlyContinue }
}

if (-not $NoWarmUp) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process $exe -ArgumentList "--warm-up" -PassThru -WindowStyle Hidden
    if (-not $p.WaitForExit(120000)) {
        Stop-Process -Id $p.Id -Force
        Fail "Warm-up did not finish within 120 s"
    }
    if ($p.ExitCode -ne 0) { Fail "Warm-up failed (exit $($p.ExitCode))" }
    Write-Host "Warm-up: $($watch.ElapsedMilliseconds) ms"
}

# Builds the PyInstaller one-folder build (its exe renamed to .scr), MatrixRain.zip and DigitalRain-Setup.exe
# MatrixRain.zip is a local build output; releases carry only DigitalRain-Setup.exe (Inno Setup 6, installer\windows).
# The screensaver picker shows the .scr's string 1, "Digital Rain" (tools\build\scr_name.py);
# the file and folder stay MatrixRain so existing installs keep working.
# Run from a clean Python 3.14 venv with the pinned packages in requirements/requirements-build.txt.
#   -Python <path>  interpreter used to create build\venv (default: py -3.14)
#   -ReuseVenv      reuse build\venv if it exists instead of recreating it
#   -NoSmoke        skip the smoke test of the built exe (needs a desktop)
#   -Iscc <path>    Inno Setup compiler (default: PATH, then the usual install folders)
#   -NoInstaller    skip DigitalRain-Setup.exe
param(
    [string]$Python = "",
    [switch]$ReuseVenv,
    [switch]$NoSmoke,
    [string]$Iscc = "",
    [switch]$NoInstaller
)
Set-Location $PSScriptRoot
$ErrorActionPreference = "Stop"

function Fail($msg) {
    Write-Host $msg
    exit 1
}

if (-not $Python) {
    try { $Python = (& py -3.14 -c "import sys; print(sys.executable)" | Out-String).Trim() } catch { $Python = "" }
    if (-not $Python -or $LASTEXITCODE -ne 0) { Fail "Python 3.14 not found (install it or pass -Python)" }
}
& $Python -c "import sys; sys.exit(sys.version_info[:2] != (3, 14))"
if ($LASTEXITCODE -ne 0) { Fail "$Python is not Python 3.14" }

$venv = Join-Path $PSScriptRoot "build\venv"
$vpy = Join-Path $venv "Scripts\python.exe"
if (-not ($ReuseVenv -and (Test-Path $vpy))) {
    if (Test-Path $venv) { Remove-Item $venv -Recurse -Force }
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { Fail "Creating the build venv failed ($LASTEXITCODE)" }
}
& $vpy -m pip install --disable-pip-version-check -r requirements/requirements-build.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed ($LASTEXITCODE)" }
& $vpy -m pip check
if ($LASTEXITCODE -ne 0) { Fail "pip check failed ($LASTEXITCODE)" }

$font = Join-Path $PSScriptRoot "assets\rezmason\Matrix-Code.ttf"
if (-not (Test-Path $font)) { Fail "Missing $font" }
# Depth network for grid-mode pictures (digital_rain/surfaces.py); onnxruntime comes from requirements/requirements.txt.
$depthModel = Join-Path $PSScriptRoot "assets\models\depth_anything_v2_small_q.onnx"
if (-not (Test-Path $depthModel)) { Fail "Missing $depthModel" }

# Pictures that ship with the saver (optional): assets\images, used when no image folder is set.
$extra = @()
$imgdir = Join-Path $PSScriptRoot "assets\images"
if ((Test-Path $imgdir) -and (Get-ChildItem $imgdir -File -Include *.jpg,*.jpeg,*.png,*.webp,*.bmp -Recurse)) {
    $extra = @("--add-data", ($imgdir + ";assets\images"))
}

$strings = Join-Path $PSScriptRoot "build\scr-name.bin"
New-Item -ItemType Directory -Force -Path (Split-Path $strings) | Out-Null
& $vpy tools\build\scr_name.py write $strings
if ($LASTEXITCODE -ne 0) { Fail "Writing the picker name failed ($LASTEXITCODE)" }

# --specpath build makes PyInstaller resolve relative paths from build\, so every path is absolute.
& $vpy -m PyInstaller --noconfirm --clean --onedir --noconsole --name MatrixRain `
    --icon (Join-Path $PSScriptRoot "icon.ico") `
    --version-file (Join-Path $PSScriptRoot "version_info.txt") `
    --resource ($strings + ",6,1,0") `
    --hidden-import glcontext --collect-submodules moderngl `
    --add-data ((Join-Path $PSScriptRoot "assets\rezmason") + ";assets\rezmason") `
    --add-data ((Join-Path $PSScriptRoot "assets\shaders") + ";assets\shaders") `
    --add-data ((Join-Path $PSScriptRoot "assets\presets") + ";assets\presets") `
    --add-data ($depthModel + ";assets\models") `
    --collect-binaries onnxruntime `
    @extra `
    --distpath (Join-Path $PSScriptRoot "dist") `
    --workpath (Join-Path $PSScriptRoot "build\pyi") `
    --specpath (Join-Path $PSScriptRoot "build") `
    matrix_saver.py
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed ($LASTEXITCODE)" }
Move-Item dist\MatrixRain\MatrixRain.exe dist\MatrixRain\MatrixRain.scr -Force
& $vpy tools\build\scr_name.py check dist\MatrixRain\MatrixRain.scr
if ($LASTEXITCODE -ne 0) { Fail "The .scr does not carry the picker name" }
Compress-Archive -Path dist\MatrixRain -DestinationPath MatrixRain.zip -Force

if (-not $NoSmoke) {
    $scr = Join-Path $PSScriptRoot "dist\MatrixRain\MatrixRain.scr"
    $appdata = Join-Path $PSScriptRoot "build\smoke-appdata"
    if (Test-Path $appdata) { Remove-Item $appdata -Recurse -Force }
    New-Item -ItemType Directory -Path $appdata | Out-Null
    $oldAppData = $env:APPDATA
    $env:APPDATA = $appdata
    try {
        # Start-Process (or double-click) on a .scr makes Windows append /S and drop the
        # arguments, so each run starts the .scr directly, timed, with a 60 s timeout.
        $runs = @(
            @{ Name = "gpu"; Args = @("/s", "--seconds", "3", "--shot", "build\smoke-gpu.png"); Png = "build\smoke-gpu.png"; Min = 10000; LimitMs = 9000 },
            @{ Name = "software"; Args = @("/s", "--seconds", "3", "--renderer", "software", "--shot", "build\smoke-soft.png"); Png = "build\smoke-soft.png"; Min = 10000; LimitMs = 9000 },
            @{ Name = "dialog"; Args = @("/c", "--dialog-shot", "build\smoke-dialog.png"); Png = "build\smoke-dialog.png"; Min = 2000; LimitMs = 4000 }
        )
        foreach ($run in $runs) {
            $png = Join-Path $PSScriptRoot $run.Png
            if (Test-Path $png) { Remove-Item $png -Force }
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $scr
            $psi.Arguments = ($run.Args | ForEach-Object { '"' + $_ + '"' }) -join " "
            $psi.WorkingDirectory = $PSScriptRoot
            $psi.UseShellExecute = $false
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $p = [System.Diagnostics.Process]::Start($psi)
            if (-not $p.WaitForExit(60000)) {
                $p.Kill()
                Fail "Smoke test $($run.Name) did not exit within 60 s"
            }
            $sw.Stop()
            $ms = $sw.ElapsedMilliseconds
            if ($p.ExitCode -ne 0) { Fail "Smoke test failed: $($run.Args -join ' ') exited $($p.ExitCode)" }
            if (-not (Test-Path $png) -or (Get-Item $png).Length -lt $run.Min) {
                Fail "Smoke test failed: $($run.Png) missing or smaller than $($run.Min) bytes"
            }
            if ($ms -gt $run.LimitMs) { Fail "Smoke test $($run.Name) took $ms ms (limit $($run.LimitMs) ms)" }
            Write-Host "Smoke test $($run.Name): $ms ms"
        }
    } finally {
        $env:APPDATA = $oldAppData
    }
}

if (-not $NoInstaller) {
    if (-not $Iscc) {
        $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($cmd) { $Iscc = $cmd.Source }
    }
    if (-not $Iscc) {
        $dirs = @($env:LOCALAPPDATA, ${env:ProgramFiles(x86)}, $env:ProgramFiles) | Where-Object { $_ }
        foreach ($dir in $dirs) {
            $cand = Join-Path $dir "Programs\Inno Setup 6\ISCC.exe"
            if (-not (Test-Path $cand)) { $cand = Join-Path $dir "Inno Setup 6\ISCC.exe" }
            if (Test-Path $cand) { $Iscc = $cand; break }
        }
    }
    if (-not $Iscc -or -not (Test-Path $Iscc)) { Fail "Inno Setup 6 not found (install it, pass -Iscc, or use -NoInstaller)" }
    $vtext = Get-Content (Join-Path $PSScriptRoot "version_info.txt") -Raw
    if ($vtext -notmatch "StringStruct\('ProductVersion', '([^']+)'\)") { Fail "No ProductVersion in version_info.txt" }
    $version = $Matches[1]
    $setup = Join-Path $PSScriptRoot "DigitalRain-Setup.exe"
    if (Test-Path $setup) { Remove-Item $setup -Force }
    & $Iscc "/DAppVersion=$version" (Join-Path $PSScriptRoot "installer\windows\DigitalRain.iss")
    if ($LASTEXITCODE -ne 0) { Fail "Inno Setup failed ($LASTEXITCODE)" }
    if (-not (Test-Path $setup)) { Fail "Inno Setup did not write $setup" }
    Write-Host ("DigitalRain-Setup.exe: {0:N1} MB" -f ((Get-Item $setup).Length / 1MB))
}

Write-Host "Done: $PSScriptRoot\DigitalRain-Setup.exe (the release file) and MatrixRain.zip (local only)"
Write-Host "Install: run DigitalRain-Setup.exe, or tools\build\install.ps1 for a quick dev install"

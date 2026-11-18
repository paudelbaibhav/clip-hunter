# Clip Hunter - one-line installer for Windows. Paste this into PowerShell:
#
#   irm https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.ps1 | iex
#
# It installs Python if needed, downloads Clip Hunter into %USERPROFILE%\clip-hunter and runs install.py
# (Python packages, ffmpeg, TwitchDownloaderCLI, caption model, final check). Running it again updates the code and
# keeps your clips, settings and downloads.
# Options (set before running):  $env:CLIP_HUNTER_DIR = 'D:\clip-hunter'    $env:CLIP_HUNTER_DEMO = '<twitch channel>'

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'          # makes Invoke-WebRequest much faster
$Repo = if ($env:CLIP_HUNTER_REPO) { $env:CLIP_HUNTER_REPO } else { 'paudelbaibhav/clip-hunter' }
$Dir  = if ($env:CLIP_HUNTER_DIR)  { $env:CLIP_HUNTER_DIR }  else { Join-Path $HOME 'clip-hunter' }
$Zip  = if ($env:CLIP_HUNTER_ZIP)  { $env:CLIP_HUNTER_ZIP }  else { "https://github.com/$Repo/archive/refs/heads/main.zip" }

function Say($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

function Find-Python {
    foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
        try {
            $exe = $c[0]; $pre = @($c | Select-Object -Skip 1)
            $ok = & $exe @pre -c 'import sys; print(sys.version_info >= (3, 10))' 2>$null
            if ($LASTEXITCODE -eq 0 -and "$ok".Trim() -eq 'True') { return ,@($c) }
        } catch { }
    }
    return $null
}

Say 'Clip Hunter installer'
$py = Find-Python
if (-not $py) {
    Say 'Installing Python 3.12 (winget)'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Python 3.10+ is missing and winget is not available. Install Python from https://www.python.org/downloads/ (tick "Add to PATH"), then run this line again.'
    }
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $py = Find-Python
    if (-not $py) { throw 'Python was installed but this window cannot see it yet. Close PowerShell, open a new one and run the same line again.' }
}
Write-Host "    Python: $($py -join ' ')"

Say "Downloading Clip Hunter into $Dir"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("clip-hunter-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force $tmp | Out-Null
$zipFile = Join-Path $tmp 'src.zip'
if (Test-Path $Zip) { Copy-Item $Zip $zipFile } else { Invoke-WebRequest -UseBasicParsing $Zip -OutFile $zipFile }
Expand-Archive $zipFile -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'install.py') } | Select-Object -First 1
if (-not $src) { throw 'The download did not contain install.py' }
New-Item -ItemType Directory -Force $Dir | Out-Null
Copy-Item (Join-Path $src.FullName '*') $Dir -Recurse -Force      # code only; runs/, tools/, .venv/, channels.json are kept
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

Say 'Running install.py'
$args2 = @()
if ($env:CLIP_HUNTER_DEMO) { $args2 += @('--demo', $env:CLIP_HUNTER_DEMO) }
if ($env:CLIP_HUNTER_ARGS) { $args2 += ($env:CLIP_HUNTER_ARGS -split ' ') }
Push-Location $Dir
try {
    $exe = $py[0]; $pre = @($py | Select-Object -Skip 1)
    & $exe @pre install.py @args2
    if ($LASTEXITCODE -ne 0) { throw "install.py stopped with an error (see above)" }
} finally { Pop-Location }
Say "Done. Clip Hunter is in $Dir"

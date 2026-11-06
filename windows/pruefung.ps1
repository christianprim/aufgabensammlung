#requires -Version 5.1
<#
Startet die Streamlit-App "Physikpruefung" unter Windows.

Verwendung (cmd):
  windows\pruefung.cmd                 Vordergrund
  windows\pruefung.cmd --background    Hintergrund
  windows\pruefung.cmd --stop          Hintergrund-App beenden
  windows\pruefung.cmd --status        Status anzeigen
  windows\pruefung.cmd --help          Hilfe anzeigen

Direkt in PowerShell:
  .\windows\pruefung.ps1 -Foreground
  .\windows\pruefung.ps1 -Background
  .\windows\pruefung.ps1 -Stop
  .\windows\pruefung.ps1 -Status

Umgebung:
  PRUEFUNG_DIR         Projektordner (Standard: dieser Ordner)
  PRUEFUNG_PORT        Port (Standard: 8501)
  PRUEFUNG_NO_BROWSER  1 = Browser nicht automatisch oeffnen
  PRUEFUNG_STATE_DIR   Ordner fuer PID- und Logdateien
#>
[CmdletBinding()]
param(
    [switch]$Foreground,
    [switch]$Background,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptDir

function Expand-UserPath {
    param([string]$Value)
    $value = [Environment]::ExpandEnvironmentVariables($Value).Trim('"')
    if ($value -eq "~") {
        return $HOME
    }
    if ($value.StartsWith("~\") -or $value.StartsWith("~/")) {
        return (Join-Path $HOME $value.Substring(2))
    }
    return $value
}

function Resolve-AppDir {
    if ($env:PRUEFUNG_DIR) {
        return [System.IO.Path]::GetFullPath((Expand-UserPath $env:PRUEFUNG_DIR))
    }
    if (Test-Path (Join-Path $RepoRoot "app.py")) {
        return $RepoRoot
    }
    if ($env:TYPST_ROOT) {
        return [System.IO.Path]::GetFullPath((Join-Path $env:TYPST_ROOT "pruefung"))
    }
    return [System.IO.Path]::GetFullPath((Join-Path $HOME "Dokumente\typst\pruefung"))
}

$AppDir = Resolve-AppDir
$HostName = if ($env:PRUEFUNG_HOST) { $env:PRUEFUNG_HOST } else { "127.0.0.1" }
$Port = if ($env:PRUEFUNG_PORT) { $env:PRUEFUNG_PORT } else { "8501" }
$Url = "http://${HostName}:${Port}"

if ($env:PRUEFUNG_STATE_DIR) {
    $StateDir = Expand-UserPath $env:PRUEFUNG_STATE_DIR
} elseif ($env:LOCALAPPDATA) {
    $StateDir = Join-Path $env:LOCALAPPDATA "pruefung"
} else {
    $StateDir = Join-Path $HOME ".pruefung"
}
$StateDir = [System.IO.Path]::GetFullPath($StateDir)
$LogFile = Join-Path $StateDir "streamlit.log"
$ErrorLogFile = Join-Path $StateDir "streamlit.err.log"
$PidFile = Join-Path $StateDir "streamlit.pid"
$NoBrowser = ($env:PRUEFUNG_NO_BROWSER -eq "1")

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
if (-not $env:PRUEFUNG_ROOT) { $env:PRUEFUNG_ROOT = $AppDir }
$env:PRUEFUNG_STATE_DIR = $StateDir

function Show-Usage {
    Write-Host @'
Verwendung: pruefung.cmd [--background|--stop|--status|--help]

  (ohne Option)   App im Vordergrund starten
  --background    App im Hintergrund starten
  --stop          Hintergrund-App beenden
  --status        Status anzeigen
  --help          Diese Hilfe anzeigen

PowerShell direkt:
  pruefung.ps1 [-Foreground] [-Background] [-Stop] [-Status]

Umgebung:
  PRUEFUNG_DIR         Projektordner (Standard: dieser Ordner)
  PRUEFUNG_PORT        Port (Standard: 8501)
  PRUEFUNG_NO_BROWSER  1 = Browser nicht automatisch oeffnen
'@
}

function Get-StreamlitCommand {
    $venvPython = Join-Path $AppDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return [pscustomobject]@{ File = $venvPython; Prefix = @("-m", "streamlit") }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ File = $python.Source; Prefix = @("-m", "streamlit") }
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $resolved = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            $resolved = ([string]$resolved).Trim()
            if (Test-Path $resolved) {
                return [pscustomobject]@{ File = $resolved; Prefix = @("-m", "streamlit") }
            }
        }
    }

    $streamlit = Get-Command streamlit.exe -ErrorAction SilentlyContinue
    if ($streamlit) {
        return [pscustomobject]@{ File = $streamlit.Source; Prefix = @() }
    }

    throw "Streamlit wurde nicht gefunden. Bitte .venv im Projektordner anlegen."
}

function Test-Running {
    try {
        $response = Invoke-WebRequest -Uri "$Url/_stcore/health" -UseBasicParsing -TimeoutSec 1
        return ($response.StatusCode -eq 200 -and ([string]$response.Content).Trim() -eq "ok")
    } catch {
        return $false
    }
}

function Open-Browser {
    if ($NoBrowser) {
        Write-Host "App laeuft unter $Url"
        return
    }
    Start-Process $Url
}

function Wait-ForServer {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) {
            return $false
        }
        if (Test-Running) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Test-OurProcess {
    param([int]$ProcessId)
    try {
        $info = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        if (-not $info -or -not $info.CommandLine) {
            return $false
        }
        return ($info.CommandLine -match "streamlit" -and $info.CommandLine -match "app\.py")
    } catch {
        return $false
    }
}

function Start-Foreground {
    if (Test-Running) {
        Open-Browser
        return
    }

    $appFile = Join-Path $AppDir "app.py"
    if (-not (Test-Path $appFile)) {
        throw "app.py wurde nicht gefunden: $appFile"
    }

    $streamlit = Get-StreamlitCommand
    $arguments = @($streamlit.Prefix) + @(
        "run", "app.py",
        "--server.address", $HostName,
        "--server.port", "$Port",
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false"
    )

    Push-Location $AppDir
    try {
        Write-Host "Starte Physikpruefung unter $Url ..."
        $exe = $streamlit.File
        & $exe @arguments
    } finally {
        Pop-Location
    }
}

function Start-Background {
    if (Test-Running) {
        Open-Browser
        return
    }

    $appFile = Join-Path $AppDir "app.py"
    if (-not (Test-Path $appFile)) {
        throw "app.py wurde nicht gefunden: $appFile"
    }

    $streamlit = Get-StreamlitCommand
    $arguments = @($streamlit.Prefix) + @(
        "run", "app.py",
        "--server.address", $HostName,
        "--server.port", "$Port",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    )

    $exe = $streamlit.File
    $process = Start-Process -FilePath $exe `
        -ArgumentList $arguments `
        -WorkingDirectory $AppDir `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $ErrorLogFile `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $PidFile -Value $process.Id -NoNewline -Encoding ASCII

    if (-not (Wait-ForServer -Process $process -TimeoutSeconds 30)) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        throw "Die App konnte nicht gestartet werden. Siehe $LogFile und $ErrorLogFile"
    }

    Open-Browser
    Write-Host "Physikpruefung laeuft im Hintergrund (PID $($process.Id))."
    Write-Host "Log: $LogFile"
}

function Stop-Background {
    if (-not (Test-Path $PidFile)) {
        if (Test-Running) {
            throw "Die App laeuft, wurde aber nicht ueber --background gestartet. Bitte im Terminal mit Ctrl+C beenden."
        }
        Write-Host "Keine Hintergrund-App gefunden."
        return
    }

    $rawPid = Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue
    $serverPid = 0
    if (-not $rawPid -or -not [int]::TryParse(([string]$rawPid).Trim(), [ref]$serverPid)) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Ungueltige PID-Datei entfernt."
        return
    }

    $process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Keine laufende Hintergrund-App gefunden."
        return
    }

    if (-not (Test-OurProcess -ProcessId $serverPid)) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Die gespeicherte PID $serverPid gehoert nicht mehr zur App; PID-Datei entfernt."
        return
    }

    Stop-Process -Id $serverPid -ErrorAction SilentlyContinue
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Process -Id $serverPid -ErrorAction SilentlyContinue) -and ((Get-Date) -lt $deadline)) {
        Start-Sleep -Milliseconds 200
    }
    if (Get-Process -Id $serverPid -ErrorAction SilentlyContinue) {
        Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
    }

    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host "Physikpruefung beendet."
}

function Show-Status {
    if (Test-Running) {
        Write-Host "Physikpruefung laeuft: $Url"
        if (Test-Path $PidFile) {
            $rawPid = Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue
            if ($rawPid) {
                Write-Host "PID: $(([string]$rawPid).Trim())"
            }
        }
        Write-Host "Log: $LogFile"
    } else {
        Write-Host "Physikpruefung laeuft nicht."
    }
}

try {
    if ($Help) {
        Show-Usage
        exit 0
    }
    if ($Stop) {
        Stop-Background
        exit 0
    }
    if ($Status) {
        Show-Status
        exit 0
    }
    if ($Background) {
        Start-Background
        exit 0
    }
    Start-Foreground
    exit 0
} catch {
    Write-Host "Fehler: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

param(
    [ValidateRange(5, 120)]
    [int]$TimeoutSeconds = 60
)

# Launch through the Windows desktop shell so Docker does not inherit a
# packaged agent application's AppData virtualization context.
$ErrorActionPreference = 'Stop'
$taskDockerCommand = Get-Command docker -ErrorAction Stop
$taskEndpoint = & docker context inspect --format '{{.Endpoints.docker.Host}}'
if ($LASTEXITCODE -ne 0 -or $taskEndpoint -notlike 'npipe://*') {
    throw 'Select a local Windows Docker context before using this script.'
}

function Get-LocalDockerVersion {
    try {
        $taskVersion = & docker info --format '{{.ServerVersion}}' 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $taskVersion
        }
    } catch {
        # A stopped engine is expected before launch.
    }
    return $null
}

$taskCurrentVersion = Get-LocalDockerVersion
if ($taskCurrentVersion) {
    Write-Output "Docker is ready: $taskCurrentVersion"
    exit 0
}

$taskInstallRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $taskDockerCommand.Source))
$taskCandidates = @(
    (Join-Path $taskInstallRoot 'Docker Desktop.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
    (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
)
$taskDockerExe = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $taskDockerExe) {
    throw 'Docker Desktop executable was not found. Check its installation path.'
}

Start-Process -FilePath explorer.exe -ArgumentList ('"' + $taskDockerExe + '"') -WindowStyle Hidden
$taskDeadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds 2
    $taskCurrentVersion = Get-LocalDockerVersion
    if ($taskCurrentVersion) {
        Write-Output "Docker is ready: $taskCurrentVersion"
        exit 0
    }
} while ((Get-Date) -lt $taskDeadline)

throw 'Docker did not become ready before timeout. Inspect Docker Desktop and its startup log; this script does not reset data or change settings.'

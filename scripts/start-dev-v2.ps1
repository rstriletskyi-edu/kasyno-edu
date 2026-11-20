#Requires -Version 5.1
# Run this file. It prepares tools, copies example settings, and starts both apps.
[CmdletBinding()]
param([switch]$Install, [switch]$Help)
if ($Help) { Write-Host 'Usage: .\scripts\start-dev.ps1 [-Install] [-Help]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'On Ubuntu, use bash scripts/start-dev.sh.' }
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root '.dev-tools'
$servers = @()
$gates = @()
$job = $null
Push-Location -LiteralPath $root

function Run([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed (exit $LASTEXITCODE). See the output above; check internet/proxy access if installing." }
}
function Download([string]$Url, [string]$File, [string]$Hash) {
    Write-Host "[INFO] Downloading $Url"
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $File -TimeoutSec 120
    if ((Get-FileHash -LiteralPath $File).Hash -ne $Hash) { throw "Checksum failed: $File. Download will not be executed." }
}
function Get-Uv {
    $exe = Join-Path $tools 'uv\uv.exe'
    if (!(Test-Path -LiteralPath $exe)) {
        $target = 'x86_64-pc-windows-msvc'
        $hash = '529e78a9cec6cd7e3e014f7ecd8bda0c113969d4ed0f2efeedb85c30943325b8'
        if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
            $target = 'aarch64-pc-windows-msvc'
            $hash = '59e6d919bed1f72035e622a7c930058f08a8931c4c78ceaf9f56e7fb74dd2c48'
        }
        Download "https://github.com/astral-sh/uv/releases/download/0.13.8/uv-$target.zip" "$tools\uv.zip" $hash
        Expand-Archive -LiteralPath "$tools\uv.zip" -DestinationPath "$tools\uv" -Force
    }
    return $exe
}
function Http-Ready([string]$Url) {
    try {
        $request = [Net.HttpWebRequest]::Create($Url); $request.Proxy = $null; $request.Timeout = 1000
        $response = $request.GetResponse()
        try { return [int]$response.StatusCode -eq 200 } finally { $response.Close() }
    } catch { return $false }
}
function Servers-Healthy {
    foreach ($server in $servers) {
        if ($server.HasExited) { throw "A server exited (code $($server.ExitCode)). Check its logs above." }
    }
    return (Http-Ready 'http://127.0.0.1:8000/api/health') -and (Http-Ready 'http://127.0.0.1:4200/')
}

try {
    # 1. Check the checkout and ports before installing anything.
    Write-Host '[INFO] Checking development environment...'
    foreach ($file in @('frontend/package.json','frontend/package-lock.json','frontend/.env.example','backend/pyproject.toml','backend/poetry.lock','backend/.env.example')) {
        if (!(Test-Path -LiteralPath $file)) { throw "Missing project file: $file" }
    }
    foreach ($port in @(4200,8000)) {
        $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,$port)
        $listener.ExclusiveAddressUse = $true
        try { $listener.Start() } catch { throw "Port $port is busy. Stop its owner and try again." }
        finally { $listener.Stop() }
    }
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
    $env:NG_CLI_ANALYTICS = 'false'
    $env:POETRY_NO_INTERACTION = '1'
    $env:POETRY_VIRTUALENVS_IN_PROJECT = 'true'
    $env:VIRTUAL_ENV = $null
    $env:UV_CACHE_DIR = "$tools\uv-cache"
    $env:UV_PYTHON_INSTALL_DIR = "$tools\python"
    $env:UV_PYTHON_BIN_DIR = "$tools\bin"
    $env:UV_TOOL_DIR = "$tools\python-tools"
    $env:UV_TOOL_BIN_DIR = "$tools\bin"
    $env:npm_config_cache = "$tools\npm-cache"
    $env:npm_config_fetch_retries = '1'
    $env:npm_config_fetch_timeout = '30000'
    $env:npm_config_engine_strict = 'true'

    # 2. Reuse compatible Node, otherwise download an official, verified archive.
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
    $nodeDir = "$tools\node-v24.15.0-win-$arch"
    $env:PATH = "$nodeDir;$tools\bin;$env:PATH"
    $node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
    $version = if ($node) { [version]((& $node --version).TrimStart('v')) } else { [version]'0.0.0' }
    $compatible = ($version.Major -eq 22 -and $version -ge [version]'22.22.3') -or ($version.Major -eq 24 -and $version -ge [version]'24.15.0') -or $version.Major -eq 26
    if (!$compatible) {
        $name = "node-v24.15.0-win-$arch.zip"
        $sums = (Invoke-WebRequest -UseBasicParsing 'https://nodejs.org/dist/v24.15.0/SHASUMS256.txt' -TimeoutSec 30).Content
        $hash = (($sums -split "`n" | Where-Object { $_.Trim().EndsWith("  $name") }) -split '\s+')[0]
        if (!$hash) { throw 'Cannot find the Node.js archive checksum.' }
        Download "https://nodejs.org/dist/v24.15.0/$name" "$tools\node.zip" $hash
        Expand-Archive -LiteralPath "$tools\node.zip" -DestinationPath $tools -Force
        $node = "$nodeDir\node.exe"
    }
    $npmVersion = (Get-Content frontend/package.json -Raw | ConvertFrom-Json).packageManager -replace '^npm@',''
    $npm = "$tools\npm\node_modules\npm\bin\npm-cli.js"
    if (!(Test-Path -LiteralPath $npm) -or (& $node $npm --version) -ne $npmVersion) {
        $bundledNpm = Join-Path (Split-Path $node) 'node_modules\npm\bin\npm-cli.js'
        Run $node @($bundledNpm,'install','--prefix',"$tools\npm",'--no-package-lock','--no-save',"npm@$npmVersion")
    }
    $env:PATH = "$tools\npm\node_modules\.bin;$(Split-Path $node);$env:PATH"
    Write-Host "[OK] Node $(& $node --version), npm $(& $node $npm --version)"

    # 3. Use Python 3.13+ and Poetry; missing tools are isolated in .dev-tools.
    $python = $null
    foreach ($candidate in @("$root\backend\.venv\Scripts\python.exe",(Get-Command python.exe -ErrorAction SilentlyContinue).Source)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate) -and $candidate -notlike '*\WindowsApps\*') {
            & $candidate -c 'import sys; sys.exit(not ((3,13) <= sys.version_info < (4,0)))'
            if ($LASTEXITCODE -eq 0) { $python=$candidate; break }
        }
    }
    if (!$python) {
        $uv = Get-Uv
        $python = & $uv python find 3.13 2>$null
        if ($LASTEXITCODE -ne 0 -or !$python -or !(Test-Path -LiteralPath $python)) {
            Run $uv @('python','install','3.13')
            $python = & $uv python find 3.13
            if ($LASTEXITCODE -ne 0) { throw 'Cannot locate Python 3.13.' }
        }
    }
    $env:PATH = "$(Split-Path $python);$env:PATH"
    $poetry = (Get-Command poetry.exe -ErrorAction SilentlyContinue).Source
    $poetryOk = $false
    if ($poetry) {
        try { $poetryOk = (& $poetry --version 2>$null) -eq 'Poetry (version 2.5.0)' -and $LASTEXITCODE -eq 0 } catch { $poetryOk = $false }
    }
    if (!$poetryOk) {
        $uv = Get-Uv
        Run $uv @('tool','install','--force','--python',$python,'poetry==2.5.0')
        $poetry = "$tools\bin\poetry.exe"
    }
    Write-Host "[OK] $(& $python --version), $(& $poetry --version)"

    # 4. Copy example settings only when missing. Firebase is optional for startup.
    foreach ($directory in @('frontend','backend')) {
        if (!(Test-Path -LiteralPath "$directory/.env")) {
            [IO.File]::Copy("$root\$directory\.env.example", "$root\$directory\.env", $false)
            Write-Host "[INFO] Created $directory/.env from its example."
        }
    }
    Set-Location -LiteralPath "$root\frontend"
    $signature = "$( (Get-FileHash package.json).Hash ) $( (Get-FileHash package-lock.json).Hash ) $(& $node --version) $npmVersion"
    $stamp = "$tools\frontend-windows.sha256"
    $ready = !$Install -and (Test-Path -LiteralPath $stamp) -and (Get-Content -LiteralPath $stamp -Raw).Trim() -eq $signature
    if ($ready) {
        $ErrorActionPreference = 'Continue' # A failed dependency probe triggers npm ci.
        & $node $npm ls --all --silent *> $null
        $ready = $LASTEXITCODE -eq 0
        $ErrorActionPreference = 'Stop'
    }
    if (!$ready) { Run $node @($npm,'ci','--include=dev','--no-audit','--no-fund'); Set-Content -LiteralPath $stamp -Value $signature }
    else { Write-Host '[OK] Frontend dependencies already installed.' }
    Set-Location -LiteralPath "$root\backend"
    Run $poetry @('check','--lock')
    if (Test-Path -LiteralPath '.venv') {
        $venvCfg = if (Test-Path -LiteralPath '.venv/pyvenv.cfg') { Get-Content -LiteralPath '.venv/pyvenv.cfg' -Raw } else { '' }
        $venvHomeMatch = [regex]::Match($venvCfg, '(?m)^home\s*=\s*(.+)$')
        $venvHome = if ($venvHomeMatch.Success) { $venvHomeMatch.Groups[1].Value.Trim() } else { '' }
        if ($venvHome -and !(Test-Path -LiteralPath $venvHome)) {
            Write-Host '[WARN] Existing backend/.venv references a moved or missing Python path; recreating .venv...'
            Remove-Item -LiteralPath '.venv' -Recurse -Force
        } else {
            if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Existing .venv is incomplete or from Linux. Move it aside and rerun; it was preserved.' }
            & .venv/Scripts/python.exe -c 'import sys; sys.exit(not ((3,13) <= sys.version_info < (4,0)))'
            if ($LASTEXITCODE -ne 0) { throw 'Existing .venv needs Python 3.13+. Move it aside and rerun; it was preserved.' }
            $python = "$root\backend\.venv\Scripts\python.exe"
        }
    }
    Run $poetry @('env','use',$python)
    $plan = & $poetry install --with dev --no-root --no-ansi --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Cannot check backend dependencies.' }
    if ($Install -or ($plan -join "`n") -notmatch '0 installs, 0 updates, 0 removals|No dependencies to install or update') { Run $poetry @('install','--with','dev','--no-root','--no-ansi') }
    else { Write-Host '[OK] Backend dependencies already installed.' }
    @'
from src.configs.settings import get_settings
s = get_settings()
if s.api_prefix != '/api': raise SystemExit('[ERROR] Use API_PREFIX=/api in backend/.env.')
print('[OK] Firebase credentials found.' if s.firebase_credentials_file.is_file() else '[WARN] No Firebase credentials: app can start; Firebase features are disabled.')
'@ | & $poetry run python -
    if ($LASTEXITCODE -ne 0) { throw 'Invalid backend settings.' }

    # 5. Windows Job Object: closing one handle kills every server descendant.
    # The startup gate keeps children paused until they belong to the cleanup job.
    if (!('DevJob' -as [type])) { Add-Type @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class DevJob {
    [StructLayout(LayoutKind.Sequential)] struct Basic {
        public long ProcessTime, JobTime; public uint Flags;
        public UIntPtr Min, Max; public uint Count; public UIntPtr Affinity; public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct Limits {
        public Basic Basic;
        public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern SafeFileHandle CreateJobObject(IntPtr attrs, string name);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(SafeFileHandle job, int kind, ref Limits limits, int size);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    public static SafeFileHandle Create() {
        var job = CreateJobObject(IntPtr.Zero, null);
        var limits = new Limits(); limits.Basic.Flags = 0x2000; // KILL_ON_JOB_CLOSE
        if (job.IsInvalid || !SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(limits))) {
            job.Dispose(); throw new Win32Exception();
        }
        return job;
    }
    public static void Add(SafeFileHandle job, IntPtr process) {
        if (!AssignProcessToJobObject(job, process)) throw new Win32Exception();
    }
}
'@ }
    $job = [DevJob]::Create()
    foreach ($app in @(
        @{ Directory="$root\backend"; Exe=$poetry; Args=@('run','uvicorn','src.main:app','--reload','--host','127.0.0.1','--port','8000') },
        @{ Directory="$root\frontend"; Exe=$node; Args=@($npm,'start','--','--host','127.0.0.1','--port','4200') }
    )) {
        $gateName = 'Local\KasynoDev_' + [Guid]::NewGuid().ToString('N')
        $gate = New-Object Threading.EventWaitHandle($false,[Threading.EventResetMode]::ManualReset,$gateName)
        $gates += $gate
        $arguments = ($app.Args | ForEach-Object { "'" + $_.Replace("'","''") + "'" }) -join ' '
        $command = "[Threading.EventWaitHandle]::OpenExisting('$gateName').WaitOne() | Out-Null; Set-Location -LiteralPath '$($app.Directory.Replace("'","''"))'; & '$($app.Exe.Replace("'","''"))' $arguments; exit `$LASTEXITCODE"
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
        $process = Start-Process powershell.exe -ArgumentList '-NoProfile','-EncodedCommand',$encoded -NoNewWindow -PassThru
        $servers += $process
        [DevJob]::Add($job,$process.Handle)
        $gate.Set() | Out-Null
    }

    # 6. Wait for HTTP readiness, then monitor until Ctrl+C or a server failure.
    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    while (!(Servers-Healthy)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Startup timed out. Check the server logs above.' }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "`n[SUCCESS] Ready!`nFrontend: http://localhost:4200`nAPI: http://localhost:8000/api`nDocs: http://localhost:8000/docs`nPress Ctrl+C to stop both servers.`n"
    $unhealthySince = $null
    while ($true) {
        if (Servers-Healthy) { $unhealthySince = $null }
        elseif ($null -eq $unhealthySince) { $unhealthySince = [DateTime]::UtcNow }
        elseif (([DateTime]::UtcNow - $unhealthySince).TotalSeconds -ge 30) { throw 'A server has been unhealthy for 30 seconds. Check its logs above.' }
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($null -ne $job) { Write-Host '[INFO] Stopping both servers...'; $job.Dispose() }
    foreach ($process in $servers) {
        if (!$process.HasExited) { $process.Kill() } # Also covers a failed job assignment.
        $process.WaitForExit(10000) | Out-Null
        $process.Dispose()
    }
    foreach ($gate in $gates) { $gate.Dispose() }
    Pop-Location
}

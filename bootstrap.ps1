[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoBrowser,
    [switch]$Stop,
    [string]$SystemPython
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$StudioRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$StudioApp = Join-Path $StudioRoot 'app'
$StudioTools = Join-Path $StudioRoot 'tools'
$StudioRuntime = Join-Path $StudioRoot '.runtime'
$StudioCache = Join-Path $StudioRoot '.cache'
$StudioVenvPython = Join-Path $StudioApp '.venv\Scripts\python.exe'
$StudioMode = 'uv'
$StudioStatePath = Join-Path $StudioRuntime 'runtime.json'
$StudioRequirements = Join-Path $StudioApp 'yeu-cau-win.txt'
$StudioUtf8 = New-Object System.Text.UTF8Encoding($false)

function Write-StudioJson([string]$Path, $Value) {
    $Parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($Parent) | Out-Null
    $Temp = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($Temp, ($Value | ConvertTo-Json -Depth 8), $StudioUtf8)
    Move-Item -LiteralPath $Temp -Destination $Path -Force
}

function Find-StudioTool([string]$Name, [string[]]$Candidates = @()) {
    $LocalPath = Join-Path $StudioTools ($Name + '.exe')
    if (Test-Path -LiteralPath $LocalPath -PathType Leaf) { return $LocalPath }
    $Command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Command) { return $Command.Source }
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $Candidate }
    }
    return $null
}

function Test-StudioPolicyBlock($Value) {
    if ($Value -is [System.Management.Automation.ErrorRecord]) {
        if (Test-StudioPolicyBlock $Value.Exception) { return $true }
    }
    if ($Value -is [Exception]) {
        if ($Value -is [System.ComponentModel.Win32Exception] -and $Value.NativeErrorCode -eq 4551) { return $true }
        if ($Value.InnerException -and (Test-StudioPolicyBlock $Value.InnerException)) { return $true }
    }
    return [bool]([string]$Value -match '(?i)\b4551\b|STUDIO_APP_CONTROL_BLOCKED|Application Control.{0,80}block|block.{0,80}(Application Control|group policy)')
}

function Throw-StudioPolicyBlock([string]$Executable) {
    throw ('[STUDIO_APP_CONTROL_BLOCKED] Windows Application Control đang chặn: ' + $Executable +
           '. Bộ cài đã dừng và giữ nguyên môi trường hiện có. Nhờ quản trị viên kiểm tra chính sách và cung cấp bộ Python được phép chạy; sau đó mở lại start.bat. Không cần xóa môi trường hay tắt bảo vệ Windows.')
}

function Invoke-StudioCaptured([string]$Executable, [string[]]$Arguments) {
    # Read stderr as diagnostic data on Windows PowerShell 5.1 as well as newer versions.
    $ErrorActionPreference = 'Continue'
    try {
        $Lines = @(& $Executable @Arguments 2>&1)
        $Code = $LASTEXITCODE
    } catch {
        if (Test-StudioPolicyBlock $_) { Throw-StudioPolicyBlock $Executable }
        throw
    }
    foreach ($Line in $Lines) {
        if (Test-StudioPolicyBlock $Line) {
            $BlockedPath = $Executable
            $PathMatch = [regex]::Match(($Lines -join "`n"), '(?i)([A-Z]:\\[^`"\r\n]+?pythonw?\.exe)')
            if ($PathMatch.Success) { $BlockedPath = $PathMatch.Value }
            Throw-StudioPolicyBlock $BlockedPath
        }
    }
    return [pscustomobject]@{ exit_code = $Code; output = $Lines }
}

function Invoke-StudioCommand([string]$Executable, [string[]]$Arguments, [string]$Description) {
    $Completed = Invoke-StudioCaptured $Executable $Arguments
    foreach ($Line in $Completed.output) { Write-Host ([string]$Line) }
    if ($Completed.exit_code -ne 0) { throw ($Description + ' không thành công (mã ' + $Completed.exit_code + ').') }
}

function Get-StudioDownload([string]$Uri, [string]$Destination) {
    if (-not $Uri.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase)) { throw 'Chỉ tải qua HTTPS.' }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Destination)) | Out-Null
    $Partial = $Destination + '.' + [guid]::NewGuid().ToString('N') + '.download'
    Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Partial
    if ((Get-Item -LiteralPath $Partial).Length -eq 0) { throw 'Máy chủ trả về tệp rỗng.' }
    Move-Item -LiteralPath $Partial -Destination $Destination -Force
}

function Ensure-StudioUv {
    $Uv = Find-StudioTool 'uv' @((Join-Path $env:USERPROFILE '.local\bin\uv.exe'))
    if ($Uv) { return $Uv }
    Write-Host 'Đang tải uv từ nguồn chính thức của Astral...'
    $Installer = Join-Path $StudioCache 'downloads\uv-install.ps1'
    # Official installer, limited to this checkout; no shell/profile/PATH modification.
    Get-StudioDownload 'https://astral.sh/uv/install.ps1' $Installer
    $env:UV_UNMANAGED_INSTALL = $StudioTools
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Installer
    if ($LASTEXITCODE -ne 0) { throw 'Không cài được uv.' }
    $Uv = Join-Path $StudioTools 'uv.exe'
    if (-not (Test-Path -LiteralPath $Uv -PathType Leaf)) { throw 'Bộ cài uv chưa tạo uv.exe.' }
    return $Uv
}

function Read-StudioPython([string]$Executable) {
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    $MetadataCode = "import json,struct,sys;print(json.dumps({'version':list(sys.version_info[:3]),'bits':struct.calcsize('P')*8,'base':sys.base_prefix}))"
    try { $Completed = Invoke-StudioCaptured $Executable @('-I', '-c', $MetadataCode) } catch {
        if (Test-StudioPolicyBlock $_) { throw }
        return $null
    }
    if ($Completed.exit_code -ne 0) { return $null }
    $Metadata = $Completed.output
    try { $Result = ($Metadata | Select-Object -Last 1) | ConvertFrom-Json } catch { return $null }
    if ($Result.version[0] -ne 3 -or $Result.version[1] -ne 12 -or $Result.bits -ne 64) { return $null }
    $BasePython = Join-Path $Result.base 'python.exe'
    if (-not (Test-Path -LiteralPath $BasePython -PathType Leaf)) { return $null }
    return [pscustomobject]@{ executable = $BasePython; home = $Result.base; version = ($Result.version -join '.') }
}

function Get-StudioRuntimeSelection([string]$RequestedSystemPython) {
    $SystemVenvPython = Join-Path $StudioRuntime 'system-venv\Scripts\python.exe'
    if ($RequestedSystemPython) {
        return [pscustomobject]@{ mode = 'system'; base_python = $RequestedSystemPython; venv_python = $SystemVenvPython }
    }
    if (Test-Path -LiteralPath $StudioStatePath -PathType Leaf) {
        $Saved = Get-Content -LiteralPath $StudioStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Saved.mode -eq 'system') {
            if (-not $Saved.base_python -or -not $Saved.venv_python -or
                -not [IO.Path]::GetFullPath([string]$Saved.venv_python).Equals([IO.Path]::GetFullPath($SystemVenvPython), [StringComparison]::OrdinalIgnoreCase)) {
                throw '[STUDIO_SYSTEM_CONFIGURATION_INVALID] Cấu hình Python hệ thống không hợp lệ. Chạy lại setup-system-python.bat với đường dẫn Python đã được phép dùng.'
            }
            return [pscustomobject]@{ mode = 'system'; base_python = [string]$Saved.base_python; venv_python = $SystemVenvPython }
        }
    }
    return [pscustomobject]@{ mode = 'uv'; base_python = $null; venv_python = (Join-Path $StudioApp '.venv\Scripts\python.exe') }
}

function Assert-StudioPythonSignature([string]$Executable) {
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw ('Thiếu tệp trong bộ Python hệ thống: ' + $Executable) }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Executable
    if ([string]$Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch '(?i)(^|,\s*)(CN|O)=Python Software Foundation(,|$)') {
        throw ('[STUDIO_PYTHON_SIGNATURE_INVALID] Cần bộ CPython chính thức có chữ ký hợp lệ của Python Software Foundation: ' + $Executable)
    }
}

function Resolve-StudioSystemPython([string]$Executable) {
    $FullPath = [IO.Path]::GetFullPath($Executable)
    Assert-StudioPythonSignature $FullPath
    $Python = Read-StudioPython $FullPath
    if (-not $Python -or -not [IO.Path]::GetFullPath($Python.executable).Equals($FullPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Chọn python.exe gốc của CPython 3.12 x64 đã cài; không chọn một môi trường ảo hay phiên bản khác.'
    }
    foreach ($Name in @('python.exe', 'pythonw.exe')) {
        Assert-StudioPythonSignature (Join-Path $Python.home ('Lib\venv\scripts\nt\' + $Name))
    }
    Write-Host ('Dùng CPython hệ thống ' + $Python.version + ': ' + $Python.executable)
    if ([version]$Python.version -le [version]'3.12.10') {
        Write-Host 'Lưu ý: Python 3.12.10 là bản cuối có bộ cài Windows python.org, cũ hơn các bản vá 3.12 hiện hành. Bộ mở không tải hoặc tự hạ phiên bản Python.' -ForegroundColor Yellow
    }
    return $Python
}

function Resolve-StudioPython([string]$Uv) {
    if (Test-Path -LiteralPath $StudioStatePath -PathType Leaf) {
        try {
            $Saved = Get-Content -LiteralPath $StudioStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $Python = Read-StudioPython $Saved.base_python
            if ($Python) { return $Python }
        } catch {
            if (Test-StudioPolicyBlock $_) { throw }
        }
    }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $StudioRuntime 'python'
    $env:UV_PYTHON_BIN_DIR = Join-Path $StudioRuntime 'bin'
    try { $FindResult = Invoke-StudioCaptured $Uv @('python', 'find', '--no-config', '--no-project', '--no-python-downloads', '3.12') } catch {
        if (Test-StudioPolicyBlock $_) { throw }
        $FindResult = $null
    }
    if ($FindResult -and $FindResult.exit_code -eq 0) {
        $Found = $FindResult.output
        $Python = Read-StudioPython ($Found | Select-Object -Last 1)
        if ($Python) { return $Python }
    }
    Write-Host 'Đang tải Python 3.12 x64 vào thư mục .runtime...'
    Invoke-StudioCommand $Uv @('python', 'install', '3.12', '--no-config', '--no-bin', '--no-registry') 'Cài Python'
    $FindResult = Invoke-StudioCaptured $Uv @('python', 'find', '--no-config', '--no-project', '--no-python-downloads', '3.12')
    if ($FindResult.exit_code -ne 0) { throw 'Không tìm thấy Python 3.12 sau khi cài.' }
    $Found = $FindResult.output
    $Python = Read-StudioPython ($Found | Select-Object -Last 1)
    if (-not $Python) { throw 'Cần Python 3.12 bản Windows x64.' }
    return $Python
}

function Ensure-StudioFfmpeg {
    $Ffmpeg = Find-StudioTool 'ffmpeg'
    $Ffprobe = Find-StudioTool 'ffprobe'
    if ($Ffmpeg -and $Ffprobe) {
        $env:PATH = (Split-Path -Parent $Ffmpeg) + ';' + (Split-Path -Parent $Ffprobe) + ';' + $env:PATH
        return
    }
    Write-Host 'Đang tải FFmpeg/FFprobe Windows từ Gyan.dev...'
    $Archive = Join-Path $StudioCache 'downloads\ffmpeg-release-essentials.zip'
    $ChecksumPath = $Archive + '.sha256'
    Get-StudioDownload 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256' $ChecksumPath
    Get-StudioDownload 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $Archive
    $ChecksumText = [IO.File]::ReadAllText($ChecksumPath)
    $ChecksumMatch = [regex]::Match($ChecksumText, '(?i)\b[a-f0-9]{64}\b')
    if (-not $ChecksumMatch.Success) { throw 'Không đọc được SHA-256 của bộ FFmpeg.' }
    $Actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
    if (-not $Actual.Equals($ChecksumMatch.Value, [StringComparison]::OrdinalIgnoreCase)) { throw 'SHA-256 FFmpeg không khớp; chưa cài tệp tải về.' }
    $Extract = Join-Path $StudioCache ('ffmpeg-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $Archive -DestinationPath $Extract
    $FfmpegFiles = @(Get-ChildItem -LiteralPath $Extract -Recurse -File -Filter 'ffmpeg.exe')
    if ($FfmpegFiles.Count -ne 1) { throw 'Bộ FFmpeg không có cấu trúc mong đợi.' }
    $FfmpegBin = $FfmpegFiles[0].DirectoryName
    foreach ($Name in @('ffmpeg.exe', 'ffprobe.exe')) {
        $Source = Join-Path $FfmpegBin $Name
        if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw ('Thiếu ' + $Name + ' trong bộ FFmpeg.') }
        Copy-Item -LiteralPath $Source -Destination (Join-Path $StudioTools $Name) -Force
    }
    $LicenseDir = Join-Path $StudioTools 'licenses\ffmpeg'
    [IO.Directory]::CreateDirectory($LicenseDir) | Out-Null
    foreach ($Name in @('LICENSE', 'LICENSE.txt', 'README.txt')) {
        $Source = Join-Path (Split-Path -Parent $FfmpegBin) $Name
        if (Test-Path -LiteralPath $Source -PathType Leaf) { Copy-Item -LiteralPath $Source -Destination (Join-Path $LicenseDir $Name) -Force }
    }
}

function Initialize-StudioVenv([string]$Uv, $Python) {
    $Venv = if ($StudioMode -eq 'system') { Join-Path $StudioRuntime 'system-venv' } else { Join-Path $StudioApp '.venv' }
    if ($StudioMode -eq 'system' -and (Test-Path -LiteralPath $StudioVenvPython -PathType Leaf)) { Assert-StudioPythonSignature $StudioVenvPython }
    $Existing = Read-StudioPython $StudioVenvPython
    if ($StudioMode -eq 'system' -and $Existing -and
        -not [IO.Path]::GetFullPath($Existing.executable).Equals([IO.Path]::GetFullPath($Python.executable), [StringComparison]::OrdinalIgnoreCase)) {
        throw '[STUDIO_SYSTEM_BASE_MISMATCH] Môi trường system-venv đang dùng bộ Python khác. Giữ nguyên để quản trị viên kiểm tra; chưa cài thêm thư viện.'
    }
    if (-not $Existing) {
        if ($StudioMode -eq 'system' -and (Test-Path -LiteralPath $Venv)) {
            throw '[STUDIO_SYSTEM_VENV_INCOMPLETE] Môi trường system-venv đã có nhưng không chạy được. Giữ nguyên để kiểm tra; bộ mở không thay tệp thực thi.'
        }
        if (Test-Path -LiteralPath $Venv) {
            $Backup = Join-Path $StudioApp ('.venv.previous.' + (Get-Date -Format 'yyyyMMddHHmmss') + '.' + [guid]::NewGuid().ToString('N').Substring(0, 6))
            # Preserve a broken/mismatched environment rather than deleting it.
            Move-Item -LiteralPath $Venv -Destination $Backup
        }
        if ($StudioMode -eq 'system') {
            # Use CPython's standard creator in a separate environment. The original
            # app/.venv is never read, moved, patched or replaced by this mode.
            Invoke-StudioCommand $Python.executable @('-I', '-m', 'venv', '--without-pip', $Venv) 'Tạo môi trường bằng CPython hệ thống'
        } else {
            Invoke-StudioCommand $Uv @('venv', '--no-config', '--python', $Python.executable, $Venv) 'Tạo môi trường Python'
        }
        # Verify a newly created launcher before attempting any dependency installs.
        if ($StudioMode -eq 'system') { Assert-StudioPythonSignature $StudioVenvPython }
        $Created = Read-StudioPython $StudioVenvPython
        if (-not $Created) { throw 'Môi trường Python vừa tạo không khởi động được; chưa cài thư viện.' }
    }
}

function Ensure-StudioVenv([string]$Uv, $Python) {
    Initialize-StudioVenv $Uv $Python
    $RequirementsHash = (Get-FileHash -LiteralPath $StudioRequirements -Algorithm SHA256).Hash.ToLowerInvariant()
    $StampName = if ($StudioMode -eq 'system') { 'requirements-system.sha256' } else { 'requirements.sha256' }
    $StampPath = Join-Path $StudioRuntime $StampName
    $Stamp = if (Test-Path -LiteralPath $StampPath -PathType Leaf) { [IO.File]::ReadAllText($StampPath).Trim() } else { '' }
    $Probe = "import importlib;[importlib.import_module(n) for n in ['faster_whisper','av','mediapipe','numpy','PIL','scipy','fontTools','requests','cryptography','skia','onnxruntime']];import av;assert int(av.__version__.split('.')[0])<15"
    $ImportsReady = $false
    try {
        $ProbeResult = Invoke-StudioCaptured $StudioVenvPython @('-I', '-c', $Probe)
        $ImportsReady = $ProbeResult.exit_code -eq 0
    } catch {
        if (Test-StudioPolicyBlock $_) { throw }
        $ImportsReady = $false
    }
    if (-not $ImportsReady -or $Stamp -ne $RequirementsHash) {
        Write-Host 'Đang cài thư viện của Studio. Lần đầu có thể mất vài phút...'
        Invoke-StudioCommand $Uv @('pip', 'install', '--no-config', '--python', $StudioVenvPython, '-r', $StudioRequirements) 'Cài thư viện Studio'
        # Same DirectML reinstall used by the application's Windows doctor.
        Invoke-StudioCommand $Uv @('pip', 'install', '--no-config', '--python', $StudioVenvPython, '--reinstall', '--no-deps', 'onnxruntime-directml') 'Cài DirectML'
        Invoke-StudioCommand $StudioVenvPython @('-I', '-c', $Probe) 'Kiểm tra thư viện'
        [IO.File]::WriteAllText($StampPath, ($RequirementsHash + "`n"), $StudioUtf8)
    }
    $Mode = if ($StudioMode -eq 'system') { 'system' } else { 'uv' }
    Write-StudioJson $StudioStatePath @{ schema = 2; mode = $Mode; base_python = $Python.executable; venv_python = $StudioVenvPython; requirements_sha256 = $RequirementsHash }
}

try {
    if (-not ($env:PROCESSOR_ARCHITECTURE -eq 'AMD64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'AMD64')) { throw 'Bộ chạy này cần Windows x64.' }
    foreach ($Name in @('PYTHONHOME', 'PYTHONPATH', 'CAU_HINH', 'HO_SO', 'VIRTUAL_ENV', 'UV_PYTHON')) { [Environment]::SetEnvironmentVariable($Name, $null, 'Process') }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONNOUSERSITE = '1'
    $env:UV_CACHE_DIR = Join-Path $StudioCache 'uv'
    $env:UV_NO_CONFIG = '1'
    $env:PATH = $StudioTools + ';' + (Join-Path $env:USERPROFILE '.local\bin') + ';' + $env:PATH
    Set-Location -LiteralPath $StudioRoot
    if (-not (Test-Path -LiteralPath (Join-Path $StudioRoot 'launcher.py') -PathType Leaf)) { throw 'Thiếu launcher.py; hãy tải đầy đủ repository.' }

    if ($Stop -and $SystemPython) { throw 'Không dùng -Stop cùng -SystemPython.' }
    # Selection is explicit or previously saved only after successful setup. A
    # policy refusal never triggers selection of a different runtime.
    $Selection = Get-StudioRuntimeSelection $SystemPython
    $StudioMode = $Selection.mode
    $StudioVenvPython = $Selection.venv_python
    $SystemRuntime = if ($StudioMode -eq 'system') { Resolve-StudioSystemPython $Selection.base_python } else { $null }
    if ($StudioMode -eq 'system' -and (Test-Path -LiteralPath $StudioVenvPython -PathType Leaf)) { Assert-StudioPythonSignature $StudioVenvPython }

    if ($Stop) {
        # Stopping an absent/incomplete setup must never trigger an installation.
        $Python = Read-StudioPython $StudioVenvPython
        if (-not $Python -and (Test-Path -LiteralPath $StudioStatePath -PathType Leaf)) {
            $Saved = Get-Content -LiteralPath $StudioStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $Python = Read-StudioPython $Saved.base_python
        }
        if (-not $Python) { Write-Host 'Studio chưa được thiết lập trong thư mục này; không cài thêm gì.'; exit 0 }
    } else {
        if (-not (Test-Path -LiteralPath $StudioRequirements -PathType Leaf)) { throw 'Thiếu app\yeu-cau-win.txt; hãy tải đầy đủ repository.' }
        # A policy refusal is not a missing dependency: stop before downloading anything else.
        if (Test-Path -LiteralPath $StudioVenvPython -PathType Leaf) { $null = Read-StudioPython $StudioVenvPython }
        # Standard CPython needs no downloaded tool to create its environment.
        # Check its launcher before uv, FFmpeg or package installation begins.
        if ($StudioMode -eq 'system') { Initialize-StudioVenv $null $SystemRuntime }
        [IO.Directory]::CreateDirectory($StudioTools) | Out-Null
        [IO.Directory]::CreateDirectory($StudioRuntime) | Out-Null
        [IO.Directory]::CreateDirectory($StudioCache) | Out-Null
        $Claude = Find-StudioTool 'claude' @((Join-Path $env:USERPROFILE '.local\bin\claude.exe'))
        if (-not $Claude) {
            Write-Host 'Máy chưa có Claude Code. Cài bằng lệnh chính thức trong PowerShell:'
            Write-Host '  irm https://claude.ai/install.ps1 | iex'
            Write-Host 'Sau khi cài, đăng nhập Claude bằng tài khoản của anh rồi mở lại start.bat.'
            Write-Host 'Hướng dẫn: https://code.claude.com/docs/en/setup'
            throw 'Cần cài Claude Code trước khi mở Studio.'
        }
        $env:PATH = (Split-Path -Parent $Claude) + ';' + $env:PATH
        $Uv = Ensure-StudioUv
        $env:PATH = (Split-Path -Parent $Uv) + ';' + $env:PATH
        $Python = if ($StudioMode -eq 'system') { $SystemRuntime } else { Resolve-StudioPython $Uv }
        Ensure-StudioFfmpeg
        Ensure-StudioVenv $Uv $Python
    }
    $env:STUDIO_RUNTIME_HOME = $Python.home
    $env:STUDIO_PYTHON = $StudioVenvPython
    $env:STUDIO_RUNTIME_MODE = $StudioMode
    $env:STUDIO_TOOLS_DIR = $StudioTools
    $LaunchArguments = @('-I', (Join-Path $StudioRoot 'launcher.py'))
    if ($Stop) { $LaunchArguments += '--stop' }
    elseif ($Check) { $LaunchArguments += '--check' }
    elseif ($NoBrowser) { $LaunchArguments += '--no-browser' }
    & $Python.executable @LaunchArguments
    exit $LASTEXITCODE
} catch {
    Write-Host ('LỖI: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}

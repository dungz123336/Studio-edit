$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Source = Join-Path (Split-Path -Parent $PSScriptRoot) 'bootstrap.ps1'
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$Tokens, [ref]$ParseErrors)
if ($ParseErrors.Count) { throw ($ParseErrors -join "`n") }
# Import definitions only: no installers, downloads or executable probes run.
foreach ($Definition in $Ast.FindAll({ param($Node) $Node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    Invoke-Expression $Definition.Extent.Text
}
$script:Passed = 0
$script:Failed = 0
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Assert-Throws([scriptblock]$Body, [string]$Pattern) {
    $Caught = $null
    try { & $Body } catch { $Caught = $_ }
    Assert-True ($null -ne $Caught -and [string]$Caught -match $Pattern) ('Expected refusal matching ' + $Pattern)
    return [string]$Caught
}
function Test-Case([string]$Name, [scriptblock]$Body) {
    try { & $Body; $script:Passed++; Write-Host ('PASS ' + $Name) }
    catch { $script:Failed++; Write-Host ('FAIL ' + $Name + ': ' + $_.Exception.Message) }
}
$StudioApp = 'C:\Studio\app'
$StudioRuntime = 'C:\Studio\.runtime'
$StudioStatePath = 'C:\Studio\.runtime\runtime.json'
$StudioRequirements = 'C:\Studio\app\yeu-cau-win.txt'
$StudioVenvPython = 'C:\Studio\.runtime\system-venv\Scripts\python.exe'
$StudioMode = 'system'
$StudioUtf8 = New-Object System.Text.UTF8Encoding($false)
$Base = [pscustomobject]@{ executable = 'C:\Python312\python.exe'; home = 'C:\Python312'; version = '3.12.10' }

Test-Case 'Default selection stays uv and does not select another Python automatically' {
    function Test-Path { return $false }
    $Selected = Get-StudioRuntimeSelection
    Assert-True ($Selected.mode -eq 'uv' -and $Selected.venv_python -eq 'C:\Studio\app\.venv\Scripts\python.exe') 'Default changed.'
}

Test-Case 'Explicit selection ignores the old environment and uses only the separate system path' {
    function Test-Path { throw 'Must not inspect the old environment or saved state.' }
    $Selected = Get-StudioRuntimeSelection 'C:\Python312\python.exe'
    Assert-True ($Selected.mode -eq 'system' -and $Selected.base_python -eq 'C:\Python312\python.exe') 'Explicit runtime missing.'
    Assert-True ($Selected.venv_python -eq $StudioVenvPython) 'Unexpected new environment path.'
}

Test-Case 'Saved system selection is reused before any default interpreter preflight' {
    function Test-Path { return $true }
    function Get-Content { return '{"mode":"system","base_python":"C:\\Python312\\python.exe","venv_python":"C:\\Studio\\.runtime\\system-venv\\Scripts\\python.exe"}' }
    $Selected = Get-StudioRuntimeSelection
    Assert-True ($Selected.mode -eq 'system' -and $Selected.venv_python -eq $StudioVenvPython) 'Saved mode was ignored.'
}

Test-Case 'Saved selection outside the dedicated system environment is rejected' {
    function Test-Path { return $true }
    function Get-Content { return '{"mode":"system","base_python":"C:\\Python312\\python.exe","venv_python":"C:\\Other\\python.exe"}' }
    $null = Assert-Throws { Get-StudioRuntimeSelection } 'STUDIO_SYSTEM_CONFIGURATION_INVALID'
}

Test-Case 'Unsigned and differently signed executables are rejected without running Python' {
    function Test-Path { return $true }
    function Get-AuthenticodeSignature { return [pscustomobject]@{ Status='NotSigned'; SignerCertificate=$null } }
    $null = Assert-Throws { Resolve-StudioSystemPython 'C:\Python312\python.exe' } 'STUDIO_PYTHON_SIGNATURE_INVALID'
    function Get-AuthenticodeSignature { return [pscustomobject]@{ Status='Valid'; SignerCertificate=[pscustomobject]@{Subject='CN=Different Publisher, O=Another Company'} } }
    $null = Assert-Throws { Resolve-StudioSystemPython 'C:\Python312\python.exe' } 'STUDIO_PYTHON_SIGNATURE_INVALID'
}

Test-Case 'System runtime must be the compatible base rather than an arbitrary signed venv' {
    function Assert-StudioPythonSignature { }
    function Read-StudioPython { return $null }
    $null = Assert-Throws { Resolve-StudioSystemPython 'C:\Python313\python.exe' } 'CPython 3.12 x64'
    function Read-StudioPython { return $Base }
    $null = Assert-Throws { Resolve-StudioSystemPython 'C:\Other\python.exe' } 'CPython 3.12 x64'
}

Test-Case 'Valid base and both shipped stdlib launchers are checked' {
    $script:Checked = @()
    function Assert-StudioPythonSignature { param($Executable) $script:Checked += $Executable }
    function Read-StudioPython { return $Base }
    $Result = Resolve-StudioSystemPython 'C:\Python312\python.exe'
    Assert-True ($Result.executable -eq $Base.executable -and $script:Checked.Count -eq 3) 'Missing signature checks.'
    Assert-True ($script:Checked[1] -eq 'C:\Python312\Lib\venv\scripts\nt\python.exe') 'Wrong stdlib launcher.'
    Assert-True ($script:Checked[2] -eq 'C:\Python312\Lib\venv\scripts\nt\pythonw.exe') 'Missing GUI launcher check.'
}

Test-Case 'Base policy refusal never probes or downloads another Python' {
    $script:Commands = 0
    function Assert-StudioPythonSignature { }
    function Read-StudioPython { Throw-StudioPolicyBlock $Base.executable }
    function Invoke-StudioCommand { $script:Commands++ }
    $null = Assert-Throws { Resolve-StudioSystemPython 'C:\Python312\python.exe' } 'STUDIO_APP_CONTROL_BLOCKED'
    Assert-True ($script:Commands -eq 0) 'Fallback ran after refusal.'
}

Test-Case 'Stdlib creates separate environment and new launcher refusal stops before pip or saved state' {
    $script:Reads = 0; $script:Commands = @(); $script:Moves = 0; $script:Saves = 0
    function Test-Path { return $false }
    function Assert-StudioPythonSignature { }
    function Read-StudioPython {
        param($Executable)
        Assert-True ($Executable -eq $StudioVenvPython) 'Old blocked environment was probed.'
        $script:Reads++
        if ($script:Reads -eq 1) { return $null }
        Throw-StudioPolicyBlock $Executable
    }
    function Invoke-StudioCommand { param($Executable,$Arguments,$Description) $script:Commands += [pscustomobject]@{executable=$Executable; arguments=$Arguments} }
    function Move-Item { $script:Moves++ }
    function Write-StudioJson { $script:Saves++ }
    $null = Assert-Throws { Ensure-StudioVenv 'uv.exe' $Base } 'STUDIO_APP_CONTROL_BLOCKED'
    Assert-True ($script:Commands.Count -eq 1 -and $script:Moves -eq 0 -and $script:Saves -eq 0) 'Setup continued or modified old environment.'
    Assert-True ($script:Commands[0].executable -eq $Base.executable) 'uv created the system venv.'
    Assert-True (($script:Commands[0].arguments -join '|') -eq '-I|-m|venv|--without-pip|C:\Studio\.runtime\system-venv') 'Wrong venv creation command.'
}

Test-Case 'Incomplete existing system environment is preserved without rename or replacement' {
    $script:Commands = 0; $script:Moves = 0
    function Assert-StudioPythonSignature { }
    function Read-StudioPython { return $null }
    function Test-Path { return $true }
    function Invoke-StudioCommand { $script:Commands++ }
    function Move-Item { $script:Moves++ }
    $null = Assert-Throws { Ensure-StudioVenv 'uv.exe' $Base } 'STUDIO_SYSTEM_VENV_INCOMPLETE'
    Assert-True ($script:Commands -eq 0 -and $script:Moves -eq 0) 'Existing system environment was modified.'
}

Test-Case 'Existing environment with a different base is rejected before package installation' {
    $script:Commands = 0
    function Assert-StudioPythonSignature { }
    function Read-StudioPython { return [pscustomobject]@{executable='C:\Other\python.exe'} }
    function Test-Path { return $true }
    function Invoke-StudioCommand { $script:Commands++ }
    $null = Assert-Throws { Ensure-StudioVenv 'uv.exe' $Base } 'STUDIO_SYSTEM_BASE_MISMATCH'
    Assert-True ($script:Commands -eq 0) 'Different environment was overwritten.'
}

Test-Case 'Package probe refusal preserves mode and does not install or save partial setup' {
    $script:Commands = 0; $script:Saves = 0
    function Assert-StudioPythonSignature { }
    function Read-StudioPython { return $Base }
    function Get-FileHash { return [pscustomobject]@{Hash='ABCDEF'} }
    function Test-Path { return $false }
    function Invoke-StudioCaptured { Throw-StudioPolicyBlock $StudioVenvPython }
    function Invoke-StudioCommand { $script:Commands++ }
    function Write-StudioJson { $script:Saves++ }
    $null = Assert-Throws { Ensure-StudioVenv 'uv.exe' $Base } 'STUDIO_APP_CONTROL_BLOCKED'
    Assert-True ($script:Commands -eq 0 -and $script:Saves -eq 0) 'Policy refusal triggered installation or persisted partial mode.'
}

Test-Case 'Verified successful setup saves the chosen runtime and its separate requirements stamp' {
    $StudioRuntime = Join-Path $env:TEMP ('studio-system-test-' + [guid]::NewGuid().ToString('N'))
    $script:Commands = @(); $script:Saved = $null
    [IO.Directory]::CreateDirectory($StudioRuntime) | Out-Null
    try {
        function Assert-StudioPythonSignature { }
        function Read-StudioPython { return $Base }
        function Get-FileHash { return [pscustomobject]@{Hash='ABCDEF'} }
        function Test-Path { return $false }
        function Invoke-StudioCaptured { return [pscustomobject]@{exit_code=0;output=@()} }
        function Invoke-StudioCommand { param($Executable,$Arguments,$Description) $script:Commands += [pscustomobject]@{executable=$Executable; arguments=$Arguments} }
        function Write-StudioJson { param($Path,$Value) $script:Saved=$Value }
        Ensure-StudioVenv 'uv.exe' $Base
        Assert-True ($script:Commands.Count -eq 3) 'Dependencies were not verified.'
        Assert-True ($script:Commands[0].arguments[4] -eq $StudioVenvPython) 'Pip did not target selected Python.'
        Assert-True ($script:Commands[2].executable -eq $StudioVenvPython) 'Final dependency verification used another Python.'
        Assert-True ($script:Saved.mode -eq 'system' -and $script:Saved.venv_python -eq $StudioVenvPython -and $script:Saved.base_python -eq $Base.executable) 'Selected mode not persisted.'
        $Stamp = Join-Path $StudioRuntime 'requirements-system.sha256'
        Assert-True ([IO.File]::ReadAllText($Stamp).Trim() -eq 'abcdef') 'Separate environment stamp missing.'
    } finally {
        $Stamp = Join-Path $StudioRuntime 'requirements-system.sha256'
        if ([IO.File]::Exists($Stamp)) { [IO.File]::Delete($Stamp) }
        [IO.Directory]::Delete($StudioRuntime)
    }
}

Write-Host ("Results: {0} passed, {1} failed" -f $script:Passed, $script:Failed)
if ($script:Failed) { exit 1 }

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Source = Join-Path (Split-Path -Parent $PSScriptRoot) 'bootstrap.ps1'
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$Tokens, [ref]$ParseErrors)
if ($ParseErrors.Count) { throw ($ParseErrors -join "`n") }
# Import functions only. The bootstrap entry point, downloads and installations never run.
foreach ($Definition in $Ast.FindAll({ param($Node) $Node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    Invoke-Expression $Definition.Extent.Text
}
$script:Passed = 0
$script:Failed = 0
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Assert-ThrowsPolicy([scriptblock]$Body) {
    $Caught = $null
    try { & $Body } catch { $Caught = $_ }
    Assert-True ($null -ne $Caught -and (Test-StudioPolicyBlock $Caught)) 'Expected a policy refusal.'
    return [string]$Caught
}
function Test-Case([string]$Name, [scriptblock]$Body) {
    try { & $Body; $script:Passed++; Write-Host ('PASS ' + $Name) }
    catch { $script:Failed++; Write-Host ('FAIL ' + $Name + ': ' + $_.Exception.Message) }
}

Test-Case 'Recognizes Win32 4551 and native output without matching ordinary dependency errors' {
    Assert-True (Test-StudioPolicyBlock (New-Object ComponentModel.Win32Exception(4551))) 'Missing Win32 detection.'
    Assert-True (Test-StudioPolicyBlock 'An Application Control policy has blocked this file. (os error 4551)') 'Missing native diagnostic detection.'
    Assert-True (-not (Test-StudioPolicyBlock 'ModuleNotFoundError: numpy')) 'Dependency error misclassified.'
}

Test-Case 'Native uv refusal reports the Python path rather than blaming uv' {
    function Fake-StudioUv {
        Write-Output 'error: Failed to query Python interpreter at `C:\Studio\app\.venv\Scripts\python.exe`'
        Write-Output 'cause: An Application Control policy has blocked this file. (os error 4551)'
    }
    $Message = Assert-ThrowsPolicy { Invoke-StudioCaptured 'Fake-StudioUv' @('pip', 'install') }
    Assert-True ($Message.Contains('C:\Studio\app\.venv\Scripts\python.exe')) 'Blocked interpreter path is missing.'
}

Test-Case 'Compatible Python metadata still resolves its base interpreter' {
    function Test-Path { param($LiteralPath, $PathType) return $true }
    function Invoke-StudioCaptured { return [pscustomobject]@{exit_code=0;output=@('{"version":[3,12,16],"bits":64,"base":"C:\\Python312"}')} }
    $Result = Read-StudioPython 'C:\Studio\.venv\Scripts\python.exe'
    Assert-True ($Result.executable -eq 'C:\Python312\python.exe') 'Compatible metadata was rejected.'
}

Test-Case 'Incompatible metadata and ordinary query failures remain repairable' {
    function Test-Path { param($LiteralPath, $PathType) return $true }
    function Invoke-StudioCaptured { return [pscustomobject]@{exit_code=0;output=@('{"version":[3,13,0],"bits":64,"base":"C:\\Python313"}')} }
    Assert-True ($null -eq (Read-StudioPython 'C:\Python313\python.exe')) 'Wrong minor version accepted.'
    function Invoke-StudioCaptured { return [pscustomobject]@{exit_code=0;output=@('{"version":[3,12,0],"bits":32,"base":"C:\\Python312"}')} }
    Assert-True ($null -eq (Read-StudioPython 'C:\Python312\python.exe')) '32-bit Python accepted.'
    function Invoke-StudioCaptured { throw 'Missing DLL' }
    Assert-True ($null -eq (Read-StudioPython 'C:\Python312\python.exe')) 'Ordinary broken interpreter should return null.'
}

Test-Case 'Interpreter policy exception is propagated instead of returning missing Python' {
    function Test-Path { param($LiteralPath, $PathType) return $true }
    function Invoke-StudioCaptured { throw (New-Object ComponentModel.Win32Exception(4551)) }
    $null = Assert-ThrowsPolicy { Read-StudioPython 'C:\Studio\.venv\Scripts\python.exe' }
}

$StudioApp = 'C:\Studio\app'
$StudioVenvPython = 'C:\Studio\app\.venv\Scripts\python.exe'
$StudioStatePath = 'C:\Studio\.runtime\runtime.json'
$StudioRuntime = 'C:\Studio\.runtime'
$StudioRequirements = 'C:\Studio\app\yeu-cau-win.txt'

Test-Case 'Blocked existing environment is not renamed and no setup command runs' {
    $script:Moved = 0; $script:Commands = 0
    function Read-StudioPython { Throw-StudioPolicyBlock $StudioVenvPython }
    function Move-Item { $script:Moved++ }
    function Invoke-StudioCommand { $script:Commands++ }
    $null = Assert-ThrowsPolicy { Ensure-StudioVenv 'uv.exe' ([pscustomobject]@{executable='C:\Python312\python.exe'}) }
    Assert-True ($script:Moved -eq 0 -and $script:Commands -eq 0) 'A blocked environment was modified.'
}

Test-Case 'Newly created blocked launcher stops before dependency installation' {
    $script:Reads = 0; $script:Commands = @()
    function Read-StudioPython {
        $script:Reads++
        if ($script:Reads -eq 1) { return $null }
        Throw-StudioPolicyBlock $StudioVenvPython
    }
    function Test-Path { param($LiteralPath, $PathType) return $false }
    function Invoke-StudioCommand { param($Executable,$Arguments,$Description) $script:Commands += $Arguments[0] }
    $null = Assert-ThrowsPolicy { Ensure-StudioVenv 'uv.exe' ([pscustomobject]@{executable='C:\Python312\python.exe'}) }
    Assert-True ($script:Commands.Count -eq 1 -and $script:Commands[0] -eq 'venv') 'Dependency setup continued after refusal.'
}

Test-Case 'Policy refusal during package probe cannot trigger pip installation' {
    $script:Commands = 0
    function Read-StudioPython { return [pscustomobject]@{executable='C:\Python312\python.exe'} }
    function Get-FileHash { return [pscustomobject]@{Hash='ABCDEF'} }
    function Test-Path { param($LiteralPath,$PathType) return $false }
    function Invoke-StudioCaptured { Throw-StudioPolicyBlock $StudioVenvPython }
    function Invoke-StudioCommand { $script:Commands++ }
    $null = Assert-ThrowsPolicy { Ensure-StudioVenv 'uv.exe' ([pscustomobject]@{executable='C:\Python312\python.exe'}) }
    Assert-True ($script:Commands -eq 0) 'Package installation ran after policy refusal.'
}

Test-Case 'Saved blocked runtime is not replaced by an automatic download' {
    $script:Commands = 0
    function Test-Path { param($LiteralPath,$PathType) return $true }
    function Get-Content { return '{"base_python":"C:\\Python312\\python.exe"}' }
    function Read-StudioPython { Throw-StudioPolicyBlock 'C:\Python312\python.exe' }
    function Invoke-StudioCaptured { $script:Commands++; throw 'Should not probe another executable.' }
    function Invoke-StudioCommand { $script:Commands++ }
    $null = Assert-ThrowsPolicy { Resolve-StudioPython 'uv.exe' }
    Assert-True ($script:Commands -eq 0) 'Blocked saved runtime caused fallback execution.'
}

Write-Host ("Results: {0} passed, {1} failed" -f $script:Passed, $script:Failed)
if ($script:Failed) { exit 1 }

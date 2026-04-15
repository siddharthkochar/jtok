# jtok PreToolUse hook for Read tool
# Intercepts .json file reads: reads file, compresses via jtok, blocks Read and delivers compressed content
# Fail-open: all error paths exit 0

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$JTOK_PATH = "__JTOK_PATH__"

try {
    $json = [Console]::In.ReadToEnd()
    $data = $json | ConvertFrom-Json

    $file_path = $data.tool_input.file_path
    if (-not $file_path) { exit 0 }

    # Only process .json files
    if ($file_path -notmatch '\.json$') { exit 0 }

    # Normalize path for Windows (forward slashes to backslashes)
    $resolved = $file_path -replace '/', '\'

    # Check file exists
    if (-not (Test-Path $resolved)) { exit 0 }

    # Check file size - skip small files (avoid subprocess overhead)
    $file_size = (Get-Item $resolved).Length
    if ($file_size -lt 200) { exit 0 }

    # Run jtok on the file
    $result = & python $JTOK_PATH $resolved 2>$null
    if ($LASTEXITCODE -ne 0) { exit 0 }
    if (-not $result) { exit 0 }

    # Read raw file to compare
    $raw = [System.IO.File]::ReadAllText($resolved)

    # If jtok returned content same size or larger (skip case), let Read proceed
    $resultStr = ($result -join "`n")
    if ($resultStr.Length -ge $raw.Length) { exit 0 }

    $savingsPct = [math]::Round((1 - $resultStr.Length / $raw.Length) * 100)

    # Block Read and provide compressed content via additionalContext
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "PreToolUse"
            permissionDecision = "deny"
            permissionDecisionReason = "[jtok] File read OK, compressed $savingsPct%"
            additionalContext = $resultStr
        }
    } | ConvertTo-Json -Compress -Depth 5

    Write-Output $output
    exit 0
}
catch {
    # Fail-open: never break tool execution
    exit 0
}

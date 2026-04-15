# jtok PostToolUse hook for MCP tools
# Pipes MCP JSON responses through jtok, returns compressed via updatedMCPToolOutput
# Fail-open: all error paths exit 0

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$JTOK_PATH = "__JTOK_PATH__"

try {
    $json = [Console]::In.ReadToEnd()
    $data = $json | ConvertFrom-Json

    # Get tool response - try tool_response.output first, then tool_response as string
    $toolOutput = $null
    if ($data.tool_response -and $data.tool_response.output) {
        $toolOutput = $data.tool_response.output
    } elseif ($data.tool_response -is [string]) {
        $toolOutput = $data.tool_response
    }
    if (-not $toolOutput) { exit 0 }

    # Only process if output looks like JSON
    $trimmed = $toolOutput.Trim()
    if ($trimmed -notmatch '^\s*[\{\[]') { exit 0 }

    # Skip small outputs
    if ($trimmed.Length -lt 200) { exit 0 }

    # Pipe through jtok
    $result = $trimmed | & python $JTOK_PATH 2>$null
    if ($LASTEXITCODE -ne 0) { exit 0 }
    if (-not $result) { exit 0 }

    $resultStr = ($result -join "`n")

    # Check savings
    if ($resultStr.Length -ge $trimmed.Length) { exit 0 }

    # Return compressed output
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "PostToolUse"
            updatedMCPToolOutput = $resultStr
        }
    } | ConvertTo-Json -Compress -Depth 5

    Write-Output $output
    exit 0
}
catch {
    # Fail-open
    exit 0
}

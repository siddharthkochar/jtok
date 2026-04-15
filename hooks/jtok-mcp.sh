#!/usr/bin/env bash
# jtok PostToolUse hook for MCP tools
# Pipes MCP JSON responses through jtok, returns compressed via updatedMCPToolOutput
# Fail-open: all error paths exit 0

JTOK_PATH="__JTOK_PATH__"

{
    input=$(cat)

    # Extract tool output
    tool_output=$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tr = d.get('tool_response', '')
if isinstance(tr, dict):
    print(tr.get('output', ''))
elif isinstance(tr, str):
    print(tr)
else:
    print('')
" 2>/dev/null)

    [ -z "$tool_output" ] && exit 0

    # Only process JSON-looking output
    trimmed=$(echo "$tool_output" | sed 's/^[[:space:]]*//')
    case "$trimmed" in
        \{*|\[*) ;;
        *) exit 0 ;;
    esac

    # Skip small outputs
    [ ${#trimmed} -lt 200 ] && exit 0

    # Pipe through jtok
    result=$(echo "$trimmed" | python3 "$JTOK_PATH" 2>/dev/null)
    [ $? -ne 0 ] && exit 0
    [ -z "$result" ] && exit 0

    # Check savings
    [ ${#result} -ge ${#trimmed} ] && exit 0

    # Escape result for JSON
    escaped=$(echo "$result" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null)

    cat <<EOFJ
{"hookSpecificOutput":{"hookEventName":"PostToolUse","updatedMCPToolOutput":${escaped}}}
EOFJ
    exit 0
} 2>/dev/null

exit 0

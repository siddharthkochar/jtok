#!/usr/bin/env bash
# jtok PreToolUse hook for Read tool
# Intercepts .json file reads: compresses via jtok, blocks Read and delivers compressed content
# Fail-open: all error paths exit 0

JTOK_PATH="__JTOK_PATH__"

{
    input=$(cat)

    # Extract file_path (python is portable across macOS/Linux; BSD grep has no -P)
    file_path=$(printf '%s' "$input" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)
    [ -z "$file_path" ] && exit 0

    # Only process .json files
    case "$file_path" in
        *.json) ;;
        *) exit 0 ;;
    esac

    # Check file exists
    [ ! -f "$file_path" ] && exit 0

    # Skip small files
    file_size=$(wc -c < "$file_path")
    file_size=${file_size// /}
    [ "${file_size:-0}" -lt 200 ] && exit 0

    # Run jtok
    result=$(python3 "$JTOK_PATH" "$file_path" 2>/dev/null)
    [ $? -ne 0 ] && exit 0
    [ -z "$result" ] && exit 0

    result_len=${#result}

    # If no savings, let Read proceed
    [ "$result_len" -ge "$file_size" ] && exit 0

    savings_pct=$(( (file_size - result_len) * 100 / file_size ))

    # Build JSON output (python needed for safe JSON string encoding)
    python3 -c "
import json, sys
result = sys.stdin.read()
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': '[jtok] Compressed ${savings_pct}% (${file_size}B -> ${result_len}B)',
        'additionalContext': result
    }
}))" <<< "$result"
    exit 0
} 2>/dev/null

exit 0

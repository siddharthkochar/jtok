#!/usr/bin/env bash
# jtok PreToolUse hook for Read tool
# Intercepts .json file reads: reads file, compresses via jtok, blocks Read and delivers compressed content
# Fail-open: all error paths exit 0

JTOK_PATH="__JTOK_PATH__"

{
    input=$(cat)

    file_path=$(echo "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
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
    [ "$file_size" -lt 200 ] && exit 0

    # Run jtok
    result=$(python3 "$JTOK_PATH" "$file_path" 2>/dev/null)
    [ $? -ne 0 ] && exit 0
    [ -z "$result" ] && exit 0

    # Read raw file
    raw=$(cat "$file_path")

    result_len=${#result}
    raw_len=${#raw}

    # If no savings, let Read proceed
    [ "$result_len" -ge "$raw_len" ] && exit 0

    savings_pct=$(( (raw_len - result_len) * 100 / raw_len ))

    # Escape result for JSON
    escaped=$(echo "$result" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null)

    cat <<EOFJ
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[jtok] File read OK, compressed ${savings_pct}%","additionalContext":${escaped}}}
EOFJ
    exit 0
} 2>/dev/null

exit 0

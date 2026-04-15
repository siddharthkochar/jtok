# jtok - JSON Token Optimizer

Standalone utility that auto-detects JSON structure and converts to the most token-efficient format for LLM context windows. Saves 30-70% tokens on typical JSON payloads.

## Formats

| Format | Best For | Example |
|--------|----------|---------|
| **CSV** | Arrays of homogeneous objects | Option chains, time series, logs |
| **KV** | Flat dictionaries | Config, status, metadata |
| **TOON** | Nested/mixed structures | API responses, complex state |

## Usage

```bash
# Auto-detect format (pipe or file arg)
cat data.json | python jtok.py
python jtok.py data.json

# Force a specific format
python jtok.py --format csv data.json

# Show structure only (no values)
python jtok.py --schema data.json

# Sample large arrays (first/last N items)
python jtok.py --sample 5 large.json

# Show token savings stats
python jtok.py --stats data.json
```

## Claude Code Integration

jtok ships with hooks that automatically compress JSON for Claude Code:

- **PreToolUse (Read)** — intercepts `.json` file reads, delivers compressed content
- **PostToolUse (MCP)** — compresses MCP tool JSON responses

```bash
# Install hooks into ~/.claude/settings.json
python jtok.py install

# Check status
python jtok.py status

# Remove hooks
python jtok.py uninstall
```

Hooks are **fail-open** — if jtok errors or savings are below threshold, the original content passes through unchanged.

## How It Works

1. **Skip check** — files < 200 bytes or single scalars pass through unchanged
2. **Auto-detect** — analyzes structure to pick CSV, KV, or TOON format
3. **Compress** — converts JSON syntax (`{}`, `[]`, `""`, redundant keys) to compact notation
4. **Savings gate** — if compression saves < 15%, returns original unchanged

## Examples

**JSON input (array of objects):**
```json
[
  {"symbol": "NIFTY25APR24500CE", "ltp": 245.50, "oi": 1250000, "volume": 85000},
  {"symbol": "NIFTY25APR24500PE", "ltp": 120.75, "oi": 980000, "volume": 62000}
]
```

**jtok output (CSV):**
```
symbol,ltp,oi,volume
NIFTY25APR24500CE,245.5,1250000,85000
NIFTY25APR24500PE,120.75,980000,62000
```

**JSON input (flat dict):**
```json
{"status": "active", "balance": 50000.00, "trades_today": 3, "pnl": 1250.50}
```

**jtok output (KV):**
```
status=active balance=50000 trades_today=3 pnl=1250.5
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## License

MIT

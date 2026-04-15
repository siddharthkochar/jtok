# jtok - JSON Token Optimizer

Standalone utility that auto-detects JSON structure and converts to the most token-efficient format for LLM context windows. Saves 30-70% tokens on typical JSON payloads.

- **Zero dependencies** — Python 3.8+ stdlib only
- **Auto-detection** — picks the best format (CSV, KV, or TOON) based on structure
- **Fail-safe** — returns original content if savings < 15% or input < 200 bytes
- **Claude Code hooks** — automatic compression for file reads and MCP responses

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

## Formats

### CSV — Arrays of homogeneous objects

Best for: tables, logs, time series, any list of objects with the same keys.

**Auto-detected when:** input is an array of dicts with identical keys.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
[
  {
    "name": "Alice",
    "age": 30,
    "city": "Paris",
    "active": true
  },
  {
    "name": "Bob",
    "age": 25,
    "city": "Tokyo",
    "active": false
  },
  {
    "name": "Carol",
    "age": 35,
    "city": "Lima",
    "active": true
  }
]
```

</td>
<td>

```
name,age,city,active
Alice,30,Paris,T
Bob,25,Tokyo,F
Carol,35,Lima,T
```

</td>
</tr>
</table>

**Wrapper object with metadata + array:** When a dict contains a prominent array alongside scalar fields, the scalars become KV header lines and the array becomes CSV rows.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "total": 3,
  "page": 1,
  "results": [
    {"id": 1, "name": "Widget", "price": 9.99},
    {"id": 2, "name": "Gadget", "price": 24.50},
    {"id": 3, "name": "Gizmo", "price": 14.00}
  ]
}
```

</td>
<td>

```
total=3
page=1
id,name,price
1,Widget,9.99
2,Gadget,24.5
3,Gizmo,14
```

</td>
</tr>
</table>

### KV — Flat dictionaries

Best for: config, status, metadata, settings — any dict without deeply nested values.

**Auto-detected when:** input is a dict with no nested dicts and no large arrays.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "host": "localhost",
  "port": 8080,
  "debug": true,
  "workers": 4,
  "timeout": 30.0
}
```

</td>
<td>

```
host=localhost port=8080 debug=T workers=4 timeout=30
```

</td>
</tr>
</table>

**Long KV:** When key=value pairs exceed 120 characters, they wrap into multiple lines (max ~100 chars each).

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "app_name": "myservice",
  "version": "2.1.0",
  "environment": "production",
  "database_url": "postgres://db.example.com:5432/main",
  "cache_ttl": 3600,
  "max_connections": 100,
  "log_level": "info",
  "feature_flags": ["dark_mode", "beta_api"]
}
```

</td>
<td>

```
app_name=myservice version=2.1.0 environment=production
database_url=postgres://db.example.com:5432/main cache_ttl=3600
max_connections=100 log_level=info feature_flags=dark_mode,beta_api
```

</td>
</tr>
</table>

### TOON — Nested and mixed structures

Best for: API responses, complex configs, anything with mixed nesting. TOON (Token-Optimized Object Notation) combines KV lines for scalar fields with indented sections for nested data.

**Auto-detected when:** input has nested dicts, mixed types, or doesn't fit CSV/KV patterns.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "name": "myproject",
  "version": "1.0.0",
  "private": true,
  "author": {
    "name": "Alice",
    "email": "alice@example.com"
  },
  "dependencies": {
    "express": "4.18.0",
    "lodash": "4.17.21"
  },
  "scripts": {
    "start": "node index.js",
    "test": "jest"
  }
}
```

</td>
<td>

```
name=myproject version=1.0.0 private=T
author: name=Alice email=alice@example.com
dependencies: express=4.18.0 lodash=4.17.21
scripts: start=node index.js test=jest
```

</td>
</tr>
</table>

**Deeply nested with arrays of objects:** Nested arrays of homogeneous dicts are rendered as indented CSV tables.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "store": "Downtown",
  "open": true,
  "location": {
    "lat": 48.8566,
    "lng": 2.3522,
    "country": "FR"
  },
  "inventory": [
    {"item": "Laptop", "qty": 15, "price": 999.00},
    {"item": "Mouse", "qty": 200, "price": 25.50},
    {"item": "Monitor", "qty": 42, "price": 350.00}
  ]
}
```

</td>
<td>

```
store=Downtown open=T
location: lat=48.8566 lng=2.3522 country=FR
inventory:
  item,qty,price
  Laptop,15,999
  Mouse,200,25.5
  Monitor,42,350
```

</td>
</tr>
</table>

**Mixed lists:** Non-homogeneous lists render as bullet points.

<table>
<tr><th>JSON input</th><th>jtok output</th></tr>
<tr>
<td>

```json
{
  "app": "deploy-bot",
  "status": "running",
  "events": [
    {"type": "start", "time": "10:00"},
    "manual checkpoint",
    {"type": "end", "time": "10:30"}
  ]
}
```

</td>
<td>

```
app=deploy-bot status=running
events:
  - type=start time=10:00
  - manual checkpoint
  - type=end time=10:30
```

</td>
</tr>
</table>

## Value Formatting

jtok applies compact formatting to individual values:

| JSON value | jtok output | Rule |
|------------|-------------|------|
| `true` / `false` | `T` / `F` | Boolean shorthand |
| `null` | *(empty)* | Omitted |
| `25.00` | `25` | Trailing zeros dropped |
| `3.140000` | `3.14` | Up to 6 decimal places, trimmed |
| `"a long string..."` | `"a long str..."` | Truncated at 80 chars |
| `[1, 2, 3]` | `1,2,3` | Scalar lists joined |

## Other Features

### Schema mode

Show structure without values — useful for understanding large JSON files.

```bash
$ python jtok.py --schema data.json
[3 items]
  name: str
  age: int
  address: dict(3 keys)
    street: str
    city: str
    zip: str
```

### Sampling

For large arrays, show only the first and last N items:

```bash
$ python jtok.py --sample 2 large.json
name,age,city
Alice,30,Paris
Bob,25,Tokyo
...(996 rows omitted)
Yuki,28,Osaka
Zara,33,Dubai
```

### Stats mode

Show byte and token savings:

```bash
$ python jtok.py --stats data.json
format=csv raw=1250B compressed=480B savings=61.6%
tokens: raw~312 compressed~120 saved~61.5%
---
name,age,city
Alice,30,Paris
...
```

## Claude Code Integration

jtok ships with hooks that automatically compress JSON for [Claude Code](https://docs.anthropic.com/en/docs/claude-code):

- **PreToolUse (Read)** — intercepts `.json` file reads, delivers compressed content
- **PostToolUse (MCP)** — compresses MCP tool JSON responses

```bash
# Install hooks into ~/.claude/settings.json
python jtok.py install

# Check hook status
python jtok.py status

# Remove hooks
python jtok.py uninstall
```

Hooks are **fail-open** — if jtok errors or savings are below threshold, the original content passes through unchanged. Currently ships with PowerShell hooks (Windows); bash hooks for Linux/macOS coming soon.

## How It Works

1. **Skip check** — files < 200 bytes or single scalars pass through unchanged
2. **Auto-detect** — analyzes JSON structure to pick CSV, KV, or TOON
3. **Compress** — strips JSON syntax (`{}`, `[]`, `""`, repeated keys) into compact notation
4. **Savings gate** — if compression saves < 15%, returns original unchanged

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## License

MIT

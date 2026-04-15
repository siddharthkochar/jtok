#!/usr/bin/env python3
"""jtok - JSON to Token-Efficient Format Converter.

Standalone utility that auto-detects JSON structure and converts to the most
token-efficient format (CSV, KV, or TOON). Designed for LLM context windows.

Usage:
    cat data.json | jtok                    # auto-detect, pipe
    jtok file.json                          # file arg
    jtok --format csv data.json             # force format
    jtok --schema data.json                 # structure only
    jtok --sample 5 large.json              # first/last 5
    jtok --stats data.json                  # show savings % for file
    jtok --stats                             # show lifetime savings
    jtok install                            # install Claude Code hooks
    jtok uninstall                          # remove hooks
    jtok status                             # show hook status
"""

import json
import sys
import os
import shutil
import argparse
from pathlib import Path
from typing import Any, Optional, Union

VERSION = "0.1.0"
MIN_SIZE = 200          # bytes — skip files smaller than this
MIN_SAVINGS_PCT = 15    # skip if savings below this %
MAX_STR_LEN = 80        # truncate long strings in output


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token for English/code."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def format_number(v: Union[int, float]) -> str:
    """Format numbers: drop trailing zeros from floats."""
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        s = f"{v:.6f}".rstrip('0').rstrip('.')
        return s
    return str(v)


def format_value(v: Any, max_str_len: int = MAX_STR_LEN) -> str:
    """Format a single value for output."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "T" if v else "F"
    if isinstance(v, (int, float)):
        return format_number(v)
    s = str(v)
    if len(s) > max_str_len:
        s = s[:max_str_len] + "..."
    return s


# ---------------------------------------------------------------------------
# Dict flattening
# ---------------------------------------------------------------------------

def flatten_dict(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict with dot notation keys."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, key))
        elif isinstance(v, list) and v and all(isinstance(x, (str, int, float, bool)) for x in v):
            items[key] = ",".join(format_value(x) for x in v)
        elif isinstance(v, list):
            items[key] = f"[{len(v)} items]"
        else:
            items[key] = format_value(v)
    return items


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _is_flat_dict(d: dict) -> bool:
    """Check if dict has no nested dicts/lists (or only short scalar lists)."""
    for v in d.values():
        if isinstance(v, dict):
            return False
        if isinstance(v, list) and len(v) > 5:
            return False
    return True


def _find_prominent_array(d: dict) -> Optional[str]:
    """Find a key in dict whose value is a large array of homogeneous dicts."""
    best_key, best_len = None, 0
    for k, v in d.items():
        if isinstance(v, list) and len(v) >= 2:
            if all(isinstance(x, dict) for x in v):
                # Check homogeneity
                keys0 = set(v[0].keys())
                if all(set(x.keys()) == keys0 for x in v[:10]):
                    if len(v) > best_len:
                        best_key, best_len = k, len(v)
    return best_key


def detect_format(data: Any) -> str:
    """Auto-detect the best output format for the data.

    Returns: 'csv', 'kv', or 'toon'
    """
    # Array of homogeneous flat dicts -> CSV
    if isinstance(data, list) and len(data) >= 2:
        if all(isinstance(x, dict) for x in data):
            keys0 = set(data[0].keys())
            if all(set(x.keys()) == keys0 for x in data[:20]):
                return "csv"

    if isinstance(data, dict):
        # Flat dict -> KV
        if _is_flat_dict(data):
            return "kv"
        # Dict with prominent array-of-objects field -> CSV
        if _find_prominent_array(data) is not None:
            return "csv"

    # Everything else -> TOON
    return "toon"


# ---------------------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------------------

def should_skip(raw_text: str, data: Any) -> bool:
    """Determine if compression should be skipped for this data."""
    # Too small
    if len(raw_text) < MIN_SIZE:
        return True
    # Single scalar
    if isinstance(data, (str, int, float, bool)) or data is None:
        return True
    # Empty collection
    if isinstance(data, (list, dict)) and len(data) == 0:
        return True
    return False


def _check_savings(raw_text: str, compressed: str) -> bool:
    """Return True if savings meet minimum threshold."""
    if len(raw_text) == 0:
        return False
    savings = (1 - len(compressed) / len(raw_text)) * 100
    return savings >= MIN_SAVINGS_PCT


# ---------------------------------------------------------------------------
# Lifetime stats persistence
# ---------------------------------------------------------------------------

STATS_FILE = Path.home() / ".jtok" / "stats.json"


def _load_stats() -> dict:
    """Load lifetime stats from disk."""
    if not STATS_FILE.exists():
        return {"formats": {}, "total_raw": 0, "total_compressed": 0, "total_calls": 0}
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"formats": {}, "total_raw": 0, "total_compressed": 0, "total_calls": 0}


def _save_stats(stats: dict):
    """Write lifetime stats to disk."""
    try:
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATS_FILE.write_text(json.dumps(stats), encoding="utf-8")
    except OSError:
        pass  # fail-open: don't break compression if stats can't be saved


def record_stats(fmt: str, raw_bytes: int, compressed_bytes: int):
    """Record a single compression event to lifetime stats."""
    stats = _load_stats()
    stats["total_raw"] += raw_bytes
    stats["total_compressed"] += compressed_bytes
    stats["total_calls"] += 1
    entry = stats["formats"].setdefault(fmt, {"raw": 0, "compressed": 0, "calls": 0})
    entry["raw"] += raw_bytes
    entry["compressed"] += compressed_bytes
    entry["calls"] += 1
    _save_stats(stats)


def show_lifetime_stats():
    """Print lifetime savings summary by format and total."""
    stats = _load_stats()
    if stats["total_calls"] == 0:
        print("No compression stats recorded yet.")
        return

    print("jtok lifetime savings")
    print("=" * 50)

    for fmt in sorted(stats["formats"]):
        entry = stats["formats"][fmt]
        saved = entry["raw"] - entry["compressed"]
        pct = (1 - entry["compressed"] / entry["raw"]) * 100 if entry["raw"] else 0
        raw_tok = estimate_tokens("x" * entry["raw"])
        comp_tok = estimate_tokens("x" * entry["compressed"])
        print(f"  {fmt:5s}  {entry['calls']:>5} calls  "
              f"saved {_human_bytes(saved):>8s} ({pct:.1f}%)  "
              f"~{raw_tok - comp_tok} tokens saved")

    total_saved = stats["total_raw"] - stats["total_compressed"]
    total_pct = (1 - stats["total_compressed"] / stats["total_raw"]) * 100 if stats["total_raw"] else 0
    total_tok_saved = estimate_tokens("x" * stats["total_raw"]) - estimate_tokens("x" * stats["total_compressed"])
    print("-" * 50)
    print(f"  total  {stats['total_calls']:>5} calls  "
          f"saved {_human_bytes(total_saved):>8s} ({total_pct:.1f}%)  "
          f"~{total_tok_saved} tokens saved")


def _human_bytes(n: int) -> str:
    """Format byte count for display."""
    if n < 1024:
        return f"{n}B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    else:
        return f"{n / (1024 * 1024):.1f}MB"


# ---------------------------------------------------------------------------
# CSV format
# ---------------------------------------------------------------------------

def to_csv(data: Any, **opts) -> str:
    """Convert array-of-dicts to CSV format."""
    header_lines = []
    rows = None

    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        array_key = _find_prominent_array(data)
        if array_key:
            rows = data[array_key]
            # Build KV header from non-array fields
            for k, v in data.items():
                if k != array_key:
                    if isinstance(v, dict):
                        flat = flatten_dict(v, k)
                        header_lines.append(" ".join(f"{fk}={fv}" for fk, fv in flat.items()))
                    else:
                        header_lines.append(f"{k}={format_value(v)}")

    if not rows or not isinstance(rows, list):
        return to_toon(data, **opts)

    # Get columns from first row
    cols = list(rows[0].keys())

    lines = []
    if header_lines:
        lines.extend(header_lines)

    # Column header
    lines.append(",".join(cols))

    # Data rows
    for row in rows:
        vals = []
        for c in cols:
            v = row.get(c, "")
            vals.append(format_value(v))
        lines.append(",".join(vals))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# KV format
# ---------------------------------------------------------------------------

def to_kv(data: Any, **opts) -> str:
    """Convert flat dict to key=value format."""
    if not isinstance(data, dict):
        return format_value(data)

    flat = flatten_dict(data)
    # Group into lines of reasonable length
    parts = [f"{k}={v}" for k, v in flat.items()]

    # Try single line first
    single = " ".join(parts)
    if len(single) <= 120:
        return single

    # Multi-line: group related keys
    lines = []
    current = []
    current_len = 0
    for p in parts:
        if current_len + len(p) + 1 > 100 and current:
            lines.append(" ".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p) + 1
    if current:
        lines.append(" ".join(current))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOON format (Token-Optimized Object Notation)
# ---------------------------------------------------------------------------

def to_toon(data: Any, indent: int = 0, **opts) -> str:
    """Convert nested/mixed structures to TOON format."""
    prefix = "  " * indent

    if isinstance(data, (str, int, float, bool)) or data is None:
        return format_value(data)

    if isinstance(data, list):
        if not data:
            return "[]"
        # List of scalars
        if all(isinstance(x, (str, int, float, bool, type(None))) for x in data):
            return ",".join(format_value(x) for x in data)
        # List of dicts — try CSV-like
        if all(isinstance(x, dict) for x in data):
            keys0 = set(data[0].keys())
            if all(set(x.keys()) == keys0 for x in data[:10]):
                return to_csv(data, **opts)
        # Mixed list
        lines = []
        for item in data:
            lines.append(f"{prefix}- {to_toon(item, indent + 1, **opts)}")
        return "\n".join(lines)

    if isinstance(data, dict):
        lines = []
        # Separate scalar fields from complex fields
        scalars = {}
        complex_fields = {}
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                scalars[k] = v
            elif isinstance(v, list) and v and all(isinstance(x, (str, int, float, bool, type(None))) for x in v):
                scalars[k] = ",".join(format_value(x) for x in v)
            else:
                complex_fields[k] = v

        # Scalars as KV line
        if scalars:
            kv_parts = [f"{k}={format_value(v)}" for k, v in scalars.items()]
            kv_line = " ".join(kv_parts)
            if len(kv_line) <= 120:
                lines.append(f"{prefix}{kv_line}")
            else:
                # Split into multiple lines
                current = []
                current_len = 0
                for p in kv_parts:
                    if current_len + len(p) + 1 > 100 and current:
                        lines.append(f"{prefix}{' '.join(current)}")
                        current = []
                        current_len = 0
                    current.append(p)
                    current_len += len(p) + 1
                if current:
                    lines.append(f"{prefix}{' '.join(current)}")

        # Complex fields with labels
        for k, v in complex_fields.items():
            if isinstance(v, dict):
                inner_flat = flatten_dict(v)
                inner_parts = " ".join(f"{ik}={iv}" for ik, iv in inner_flat.items())
                if len(inner_parts) <= 100:
                    lines.append(f"{prefix}{k}: {inner_parts}")
                else:
                    lines.append(f"{prefix}{k}:")
                    lines.append(to_toon(v, indent + 1, **opts))
            elif isinstance(v, list):
                if len(v) >= 2 and all(isinstance(x, dict) for x in v):
                    lines.append(f"{prefix}{k}:")
                    csv_out = to_csv(v, **opts)
                    for csv_line in csv_out.split("\n"):
                        lines.append(f"{prefix}  {csv_line}")
                else:
                    lines.append(f"{prefix}{k}: {to_toon(v, indent + 1, **opts)}")
            else:
                lines.append(f"{prefix}{k}: {to_toon(v, indent + 1, **opts)}")

        return "\n".join(lines)

    return str(data)


# ---------------------------------------------------------------------------
# Schema format
# ---------------------------------------------------------------------------

def to_schema(data: Any, indent: int = 0) -> str:
    """Show structure only — types and counts, no values."""
    prefix = "  " * indent

    if isinstance(data, list):
        if not data:
            return f"{prefix}[] (empty)"
        sample = data[0]
        return f"{prefix}[{len(data)} items]\n{to_schema(sample, indent + 1)}"

    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"{prefix}{k}: dict({len(v)} keys)")
                lines.append(to_schema(v, indent + 1))
            elif isinstance(v, list):
                lines.append(f"{prefix}{k}: list({len(v)})")
                if v and isinstance(v[0], dict):
                    lines.append(to_schema(v[0], indent + 1))
            else:
                t = type(v).__name__
                lines.append(f"{prefix}{k}: {t}")
        return "\n".join(lines)

    return f"{prefix}{type(data).__name__}"


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def apply_sampling(data: Any, n: int) -> tuple:
    """Return first/last n items from arrays.

    Returns (sampled_data, omitted_count) so caller can insert separator.
    """
    if isinstance(data, list) and len(data) > n * 2:
        omitted = len(data) - n * 2
        return data[:n] + data[-n:], omitted
    if isinstance(data, dict):
        array_key = _find_prominent_array(data)
        if array_key and len(data[array_key]) > n * 2:
            result = dict(data)
            arr = data[array_key]
            omitted = len(arr) - n * 2
            result[array_key] = arr[:n] + arr[-n:]
            return result, omitted
    return data, 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compress_json(data: Any, raw_text: str = "", fmt: Optional[str] = None,
                  schema: bool = False, sample: int = 0) -> str:
    """Compress JSON data to token-efficient format.

    Args:
        data: Parsed JSON data
        raw_text: Original JSON text (for skip/savings check)
        fmt: Force format ('csv', 'kv', 'toon') or None for auto-detect
        schema: If True, return schema only
        sample: If >0, sample first/last N items

    Returns:
        Compressed string representation
    """
    if schema:
        return to_schema(data)

    omitted = 0
    if sample > 0:
        data, omitted = apply_sampling(data, sample)

    if not fmt:
        fmt = detect_format(data)

    if fmt == "csv":
        result = to_csv(data)
    elif fmt == "kv":
        result = to_kv(data)
    else:
        result = to_toon(data)

    if omitted > 0:
        # Insert separator after the first n data rows
        lines = result.split("\n")
        # Find insertion point: after header lines + n data rows
        # For CSV, header line is the column names row
        insert_idx = None
        for i, line in enumerate(lines):
            if "," in line and "=" not in line.split(",")[0]:
                # Found CSV header row — insert after it + sample rows
                insert_idx = i + sample + 1
                break
        if insert_idx and insert_idx < len(lines):
            lines.insert(insert_idx, f"...({omitted} rows omitted)")
        result = "\n".join(lines)

    return result


# ---------------------------------------------------------------------------
# Hook install / uninstall / status
# ---------------------------------------------------------------------------

def _get_hooks_dir() -> Path:
    """Return ~/.claude/hooks/ path."""
    return Path.home() / ".claude" / "hooks"


def _get_settings_path() -> Path:
    """Return ~/.claude/settings.json path."""
    return Path.home() / ".claude" / "settings.json"


def _get_jtok_path() -> str:
    """Return absolute path to this jtok.py file."""
    return str(Path(__file__).resolve())



def _read_settings() -> dict:
    """Read Claude Code settings.json."""
    path = _get_settings_path()
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _write_settings(settings: dict) -> None:
    """Write Claude Code settings.json (preserving formatting)."""
    path = _get_settings_path()
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def _jtok_hook_marker() -> str:
    return "jtok"


def cmd_install() -> None:
    """Install jtok hooks into Claude Code."""
    hooks_dir = _get_hooks_dir()
    hooks_dir.mkdir(parents=True, exist_ok=True)

    jtok_path = _get_jtok_path()

    # Always use bash hooks — Claude Code runs in bash on all platforms
    read_hook_name = "jtok-read.sh"
    mcp_hook_name = "jtok-mcp.sh"

    # Copy hook scripts
    src_hooks_dir = Path(__file__).resolve().parent / "hooks"
    for hook_name in [read_hook_name, mcp_hook_name]:
        src = src_hooks_dir / hook_name
        dst = hooks_dir / hook_name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {hook_name} -> {dst}")
        else:
            print(f"  WARNING: Source hook {src} not found, skipping")

    # Update settings.json
    settings = _read_settings()
    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks = settings["hooks"]

    # Convert hooks_dir to forward-slash path for cross-platform compat
    hooks_dir_str = str(hooks_dir).replace("\\", "/")

    # PreToolUse — Read hook (block Read, deliver compressed content)
    read_hook_entry = {
        "matcher": "Read",
        "hooks": [{
            "type": "command",
            "command": f"bash '{hooks_dir_str}/{read_hook_name}'"
        }],
        "_source": "jtok"
    }

    # PostToolUse — MCP hook
    mcp_hook_entry = {
        "matcher": "mcp__",
        "hooks": [{
            "type": "command",
            "command": f"bash '{hooks_dir_str}/{mcp_hook_name}'"
        }],
        "_source": "jtok"
    }

    # Add PreToolUse entry for Read (avoid duplicates)
    if "PreToolUse" not in hooks:
        hooks["PreToolUse"] = []
    hooks["PreToolUse"] = [h for h in hooks["PreToolUse"] if h.get("_source") != "jtok"]
    hooks["PreToolUse"].append(read_hook_entry)

    # Add PostToolUse entry for MCP
    if "PostToolUse" not in hooks:
        hooks["PostToolUse"] = []
    hooks["PostToolUse"] = [h for h in hooks["PostToolUse"] if h.get("_source") != "jtok"]
    hooks["PostToolUse"].append(mcp_hook_entry)

    # Write jtok path into hook scripts so they can find the tool
    for hook_name in [read_hook_name, mcp_hook_name]:
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            content = hook_path.read_text()
            content = content.replace("__JTOK_PATH__", jtok_path.replace("\\", "/"))
            hook_path.write_text(content)

    _write_settings(settings)
    print(f"\njtok hooks installed successfully!")
    print(f"  jtok.py: {jtok_path}")
    print(f"  Hooks dir: {hooks_dir}")
    print(f"  Settings: {_get_settings_path()}")


def cmd_uninstall() -> None:
    """Remove jtok hooks from Claude Code."""
    hooks_dir = _get_hooks_dir()

    # Remove hook scripts
    for name in ["jtok-read.ps1", "jtok-mcp.ps1", "jtok-read.sh", "jtok-mcp.sh"]:
        p = hooks_dir / name
        if p.exists():
            p.unlink()
            print(f"  Removed {p}")

    # Clean settings.json
    settings = _read_settings()
    hooks = settings.get("hooks", {})
    changed = False

    for phase in ["PreToolUse", "PostToolUse"]:
        if phase in hooks:
            before = len(hooks[phase])
            hooks[phase] = [h for h in hooks[phase] if h.get("_source") != "jtok"]
            if len(hooks[phase]) < before:
                changed = True
            if not hooks[phase]:
                del hooks[phase]

    if changed:
        _write_settings(settings)

    print("\njtok hooks uninstalled successfully!")


def cmd_status() -> None:
    """Show jtok hook status."""
    hooks_dir = _get_hooks_dir()
    settings = _read_settings()
    hooks = settings.get("hooks", {})

    print(f"jtok v{VERSION} status")
    print(f"  jtok.py: {_get_jtok_path()}")
    print()

    # Check hook files
    for name in ["jtok-read.sh", "jtok-mcp.sh"]:
        p = hooks_dir / name
        status = "installed" if p.exists() else "not found"
        print(f"  {name}: {status}")

    # Check settings entries
    has_read = any(h.get("_source") == "jtok" for h in hooks.get("PreToolUse", []))
    has_mcp = any(h.get("_source") == "jtok" for h in hooks.get("PostToolUse", []))
    print(f"\n  PreToolUse (Read): {'registered' if has_read else 'not registered'}")
    print(f"  PostToolUse (MCP): {'registered' if has_mcp else 'not registered'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="jtok",
        description="JSON to Token-Efficient Format Converter"
    )
    parser.add_argument("input", nargs="?", help="JSON file path or subcommand (install/uninstall/status)")
    parser.add_argument("--format", "-f", choices=["csv", "kv", "toon"], help="Force output format")
    parser.add_argument("--schema", "-s", action="store_true", help="Show structure only")
    parser.add_argument("--sample", "-n", type=int, default=0, help="Sample first/last N items")
    parser.add_argument("--stats", action="store_true", help="Show savings statistics")
    parser.add_argument("--version", "-v", action="version", version=f"jtok {VERSION}")

    args = parser.parse_args()

    # Handle subcommands
    if args.input in ("install", "uninstall", "status"):
        {"install": cmd_install, "uninstall": cmd_uninstall, "status": cmd_status}[args.input]()
        return

    # --stats without input: show lifetime stats
    if args.stats and not args.input and sys.stdin.isatty():
        show_lifetime_stats()
        return

    # Read input
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        raw_text = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    # Parse JSON
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Not JSON — passthrough
        print(raw_text, end="")
        return

    # Skip check
    if should_skip(raw_text, data):
        if args.stats:
            print(f"SKIP: size={len(raw_text)}B (min {MIN_SIZE}B) | scalar={isinstance(data, (str, int, float, bool, type(None)))}")
        else:
            print(raw_text, end="")
        return

    # Compress
    compressed = compress_json(data, raw_text=raw_text, fmt=args.format,
                                schema=args.schema, sample=args.sample)

    # Savings check (unless forced format, schema, or stats mode)
    if not args.format and not args.schema and not args.stats:
        if not _check_savings(raw_text, compressed):
            print(raw_text, end="")
            return

    fmt_used = args.format or detect_format(data)

    # Record to lifetime stats
    if not args.schema:
        record_stats(fmt_used, len(raw_text), len(compressed))

    if args.stats:
        raw_tokens = estimate_tokens(raw_text)
        comp_tokens = estimate_tokens(compressed)
        savings_pct = (1 - len(compressed) / len(raw_text)) * 100 if raw_text else 0
        token_savings = (1 - comp_tokens / raw_tokens) * 100 if raw_tokens else 0
        print(f"format={fmt_used} raw={len(raw_text)}B compressed={len(compressed)}B savings={savings_pct:.1f}%")
        print(f"tokens: raw~{raw_tokens} compressed~{comp_tokens} saved~{token_savings:.1f}%")
        print("---")
        print(compressed)
    else:
        print(compressed)


if __name__ == "__main__":
    main()

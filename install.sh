#!/usr/bin/env bash
# jtok installer — downloads and configures jtok for Claude Code
# Usage: curl -fsSL https://raw.githubusercontent.com/siddharthkochar/jtok/main/install.sh | bash
set -e

REPO="https://raw.githubusercontent.com/siddharthkochar/jtok/main"
INSTALL_DIR="$HOME/.claude/jtok"

echo "Installing jtok..."

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required. Install it from https://python.org" >&2
    exit 1
fi

# Create install directory
mkdir -p "$INSTALL_DIR/hooks"

# Download files
echo "  Downloading jtok.py..."
curl -fsSL "$REPO/jtok.py" -o "$INSTALL_DIR/jtok.py"

echo "  Downloading hooks..."
curl -fsSL "$REPO/hooks/jtok-read.sh" -o "$INSTALL_DIR/hooks/jtok-read.sh"
curl -fsSL "$REPO/hooks/jtok-mcp.sh" -o "$INSTALL_DIR/hooks/jtok-mcp.sh"
chmod +x "$INSTALL_DIR/hooks/jtok-read.sh" "$INSTALL_DIR/hooks/jtok-mcp.sh"

# Run install
echo "  Configuring Claude Code hooks..."
python3 "$INSTALL_DIR/jtok.py" install

echo ""
echo "Done! jtok is now active in Claude Code."
echo "Run 'jtok status' to verify."
